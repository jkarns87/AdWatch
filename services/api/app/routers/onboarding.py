"""Onboarding: three fields in, a verified watchlist out.

Two endpoints on purpose. `analyze` spends Anthropic tokens and no SerpApi quota;
`create` spends one Ads Transparency search per kept competitor. The user therefore
sees the proposal before any quota is spent, and a slow verification pass does not
hold up the analysis screen.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models as m
from .. import taxonomy
from ..auth import current_workspace_id, ensure_workspace
from ..collectors.serpapi_client import SerpApiClient
from ..config import get_settings
from ..db import get_db
from ..metering import record_call
from ..onboarding import analyze as ana
from ..onboarding import verify as ver
from ..workspace_secrets import resolve_key

log = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class AnalyzeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=4000)


class AssetIn(BaseModel):
    kind: str
    key: str
    value: str = ""


class CreateIn(AnalyzeIn):
    vertical_id: int | None = None
    keywords: list[str] = []
    competitors: list[str] = []
    assets: list[AssetIn] = []


@router.get("/verticals", summary="Search the Google Trends taxonomy")
def verticals(q: str = "", limit: int = 20):
    """Backs the typeahead. Served from the API rather than shipping 1,133 rows to the
    client, and bounded so a one-letter query stays cheap."""
    return taxonomy.search(q, limit=min(limit, 50))


@router.post("/analyze", summary="Read the company's site and propose a watchlist")
def analyze(
    body: AnalyzeIn = Body(...),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
):
    s = get_settings()
    proposal = ana.analyze_company(
        name=body.name,
        domain=body.domain,
        description=body.description,
        api_key=resolve_key(db, workspace_id=workspace_id, kind="anthropic", fallback=s.anthropic_api_key),
        model=s.anthropic_model,
    )
    # Pop before returning: the marker is transport to the ledger, never a response field.
    usage = proposal.pop("_usage", None)
    record_call(
        db, workspace_id=workspace_id, model=s.anthropic_model, feature="onboarding",
        usage=usage, status="ok" if usage else "fallback",
    )
    db.commit()
    return proposal


@router.post("/create", status_code=201, summary="Verify the confirmed competitors and build the watchlist")
def create(
    body: CreateIn = Body(...),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
):
    if body.vertical_id is not None and not taxonomy.is_valid(body.vertical_id):
        raise HTTPException(400, f"unknown Google Trends category {body.vertical_id}")

    ensure_workspace(db, workspace_id)
    own = ana.clean_domain(body.domain) or body.domain.strip()

    watchlist = m.Watchlist(
        workspace_id=workspace_id,
        name=body.name,
        vertical=taxonomy.name_for(body.vertical_id) or "" if body.vertical_id else "",
        geo="US",
        trends_category_id=body.vertical_id,
        company_domain=own,
        company_description=body.description or None,
    )
    db.add(watchlist)
    db.flush()

    # The company itself, first and always tracked.
    db.add(m.Competitor(watchlist_id=watchlist.id, name=body.name, domain=own, is_self=True))

    for term in body.keywords:
        t = term.strip()
        if t:
            db.add(m.Keyword(watchlist_id=watchlist.id, term=t))

    for a in body.assets:
        db.add(m.CompanyAsset(watchlist_id=watchlist.id, kind=a.kind, key=a.key, value=a.value))

    kept: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    client = SerpApiClient(
        api_key=resolve_key(db, workspace_id=workspace_id, kind="serpapi", fallback=get_settings().serpapi_api_key)
    )
    for raw in body.competitors:
        domain = ana.clean_domain(raw) or ""
        if not domain or domain == own:
            continue
        try:
            advertising = ver.domain_advertises(client, domain)
        except Exception as e:  # noqa: BLE001
            # SerpApi being unreachable is not evidence the company does not advertise,
            # and it must not throw away a watchlist the user just confirmed.
            log.warning("verification unavailable for %s: %s", domain, e.__class__.__name__)
            skipped.append({"domain": domain, "reason": "could not be checked"})
            continue
        if advertising:
            db.add(m.Competitor(watchlist_id=watchlist.id, name=domain, domain=domain))
            kept.append({"domain": domain, "verified": True})
        else:
            skipped.append({"domain": domain, "reason": "no advertiser found"})

    db.commit()
    return {
        "watchlist_id": watchlist.id,
        "competitors": kept,
        "skipped": skipped,
        "searches_used": getattr(client, "searches_used", 0),
    }
