"""Coffee keyword routes, and CSV in/out for a watchlist.

Additive: these live on their own router, so `routers/watchlists.py` and the
rest of the framework are untouched. Registered with one line in `main.py`.

`GET /coffee/keywords` is the only endpoint in the service that queries SerpApi
live - it answers "what is the paid block for this term right now", which no
stored run can. It is bounded rather than unbounded: an off-market seed is
rejected before a search is spent, `depth` caps the fan-out, the client's disk
cache makes a repeat free, and `searches_used` reports what the request cost.
"""

from __future__ import annotations

import csv
import io
import re

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import current_workspace_id, ensure_workspace, get_watchlist
from ..collectors.serpapi_client import SerpApiClient, SerpApiError
from ..db import get_db
from . import engine as ck
from . import schemas as cs
from .render import to_csv, to_html, to_markdown

router = APIRouter(tags=["coffee"])

# One CSV shape both ways, so a file exported here can be edited in a spreadsheet and imported
# back:
#     type,name,domain,term
#     competitor,BeanLoop,beanloop.example,
#     keyword,,,coffee subscription
CSV_COLUMNS = ["type", "name", "domain", "term"]
MAX_IMPORT_COMPETITORS = 50
MAX_IMPORT_KEYWORDS = 100   # a run costs competitors + 3 x keywords searches, so this is a quota guard
MAX_IMPORT_BYTES = 1_000_000


# ---- keyword discovery ---------------------------------------------------------------------


@router.get(
    "/coffee/keywords",
    response_model=cs.KeywordsOut,
    summary="Top coffee keywords for a seed term",
    responses={
        200: {"content": {"application/json": {}, "text/markdown": {}, "text/html": {}, "text/csv": {}}},
        400: {"description": "Invalid request, or a keyword outside the coffee market"},
        401: {"description": "Invalid SerpApi key"},
        429: {"description": "SerpApi rate limit or quota exceeded"},
    },
)
def coffee_keywords(
    keywords: str = Query(description="Coffee-related seed term, e.g. 'coffee nearby'", max_length=120),
    output: str = Query(default="json", pattern="^(json|md|html|csv)$"),
    location: str | None = Query(default=None, description=f"SerpApi location; ads are local. Default {ck.DEFAULT_LOCATION!r}."),
    gl: str = Query(default="us", max_length=5),
    depth: int = Query(default=4, ge=0, le=ck.MAX_DEPTH, description="Expansion queries to scan; each costs one SerpApi search"),
    limit: int = Query(default=25, ge=1, le=ck.MAX_LIMIT),
    refresh: bool = Query(default=False, description="Bypass the disk cache and re-query SerpApi"),
    _: int = Depends(current_workspace_id),
) -> Response:
    """Ranked by observed advertiser competition, with the evidence for each row.

    Costs `1 + depth` SerpApi searches, plus up to 3 more if the seed itself has
    no advertisers and the scan escalates to the commercial terms behind it.
    """
    client = SerpApiClient()
    try:
        report = ck.discover(client, keywords, location=location, gl=gl, depth=depth, limit=limit, fresh=refresh)
    except ValueError as e:                      # off-market or empty seed - nothing was spent
        raise HTTPException(400, str(e)) from e
    except SerpApiError as e:
        status = ck.upstream_status(e)
        if status in (401, 403) or "API_KEY" in str(e):
            raise HTTPException(401, "invalid or missing SerpApi key") from e
        if status == 429:
            raise HTTPException(429, "SerpApi rate limit or quota exceeded") from e
        raise HTTPException(502, f"SerpApi request failed: {e}") from e

    if output == "md":
        return PlainTextResponse(to_markdown(report), media_type="text/markdown; charset=utf-8")
    if output == "html":
        return HTMLResponse(to_html(report))
    if output == "csv":
        return _csv_response(to_csv(report), f"coffee-keywords-{_slug(keywords)}.csv")
    return Response(cs.KeywordsOut.model_validate(report).model_dump_json(indent=2), media_type="application/json")


# ---- watchlist CSV -------------------------------------------------------------------------


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "export"


def _csv_response(body: str, filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def parse_watchlist_csv(text: str) -> tuple[list[dict], list[str]]:
    """(competitors, keywords) from a CSV. Forgiving about columns, strict about content.

    A `type` column is honoured when present; without one, a row with a domain is
    a competitor and a row with a term is a keyword. Duplicates are dropped and
    order is kept, so an exported file can be edited and imported back.
    """
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except csv.Error as e:
        raise HTTPException(400, f"could not parse CSV: {e}") from e
    if not rows:
        raise HTTPException(400, f"CSV has no data rows; expected columns {', '.join(CSV_COLUMNS)}")

    competitors: list[dict] = []
    keywords: list[str] = []
    seen_domains: set[str] = set()
    seen_terms: set[str] = set()

    for i, raw in enumerate(rows, 2):   # row 1 is the header
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        kind = row.get("type", "").lower()
        domain = (row.get("domain") or "").lower()
        domain = domain.removeprefix("http://").removeprefix("https://").removeprefix("www.").split("/")[0]
        term = row.get("term") or row.get("keyword") or ""

        if kind == "competitor" or (not kind and domain):
            if not domain:
                raise HTTPException(400, f"row {i}: competitor needs a domain")
            if "." not in domain:
                raise HTTPException(400, f"row {i}: {domain!r} is not a domain")
            if domain not in seen_domains:
                seen_domains.add(domain)
                competitors.append({"name": row.get("name") or domain.split(".")[0].title(), "domain": domain})
        elif kind == "keyword" or (not kind and term):
            if not term:
                raise HTTPException(400, f"row {i}: keyword needs a term")
            if term.lower() not in seen_terms:
                seen_terms.add(term.lower())
                keywords.append(term)
        elif kind:
            raise HTTPException(400, f"row {i}: unknown type {kind!r} (expected competitor or keyword)")

    if not competitors and not keywords:
        raise HTTPException(400, f"CSV had no competitors or keywords; expected columns {', '.join(CSV_COLUMNS)}")
    if len(competitors) > MAX_IMPORT_COMPETITORS or len(keywords) > MAX_IMPORT_KEYWORDS:
        raise HTTPException(400, f"too large: max {MAX_IMPORT_COMPETITORS} competitors and {MAX_IMPORT_KEYWORDS} keywords")
    return competitors, keywords


@router.get("/watchlists/{watchlist_id}/export.csv", summary="Watchlist competitors and keywords as CSV")
def export_watchlist_csv(w: m.Watchlist = Depends(get_watchlist)) -> PlainTextResponse:
    """The shape `POST /watchlists/import.csv` accepts, so a watchlist round-trips."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for c in w.competitors:
        writer.writerow(["competitor", c.name, c.domain, ""])
    for k in w.keywords:
        writer.writerow(["keyword", "", "", k.term])
    return _csv_response(buf.getvalue(), f"{_slug(w.name) or f'watchlist-{w.id}'}.csv")


@router.post("/watchlists/import.csv", response_model=cs.ImportedWatchlist, status_code=201, summary="Build a watchlist from a CSV")
def import_watchlist_csv(
    body: str = Body(media_type="text/csv", description="CSV with columns: type,name,domain,term"),
    name: str = Query(description="Watchlist name"),
    vertical: str = Query(default=""),
    geo: str = Query(default="US"),
    location: str = Query(default=""),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
):
    """Post the CSV as the request body (`Content-Type: text/csv`) - no upload encoding needed.

        curl -X POST 'localhost:8000/api/v1/watchlists/import.csv?name=Specialty%20Coffee' \\
             -H 'Content-Type: text/csv' --data-binary @coffee.csv
    """
    if len(body.encode("utf-8", "ignore")) > MAX_IMPORT_BYTES:
        raise HTTPException(400, "CSV too large (1 MB max)")
    competitors, keywords = parse_watchlist_csv(body.lstrip("﻿"))

    ensure_workspace(db, workspace_id)
    w = m.Watchlist(workspace_id=workspace_id, name=name, vertical=vertical, geo=geo or "US", location=location or None)
    db.add(w)
    db.flush()
    for c in competitors:
        db.add(m.Competitor(watchlist_id=w.id, name=c["name"], domain=c["domain"]))
    for term in keywords:
        db.add(m.Keyword(watchlist_id=w.id, term=term))
    db.commit()
    return cs.ImportedWatchlist(
        watchlist_id=w.id, name=w.name, competitors=[c["domain"] for c in competitors], keywords=keywords
    )
