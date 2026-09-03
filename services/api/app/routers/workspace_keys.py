"""Per-workspace API key management.

Keys are validated with the provider before they are stored. This session began with
`SERPAPI_API_KEY=apiworld2026` passing a `bool()` check, 502-ing every collect while
/health stayed green — rejecting a bad key at the point of entry is the cheapest place
to catch that.

Nothing here ever returns key material: the response carries `kind` and `last4` only.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import crypto
from .. import providers as prov
from .. import workspace_secrets as sec
from ..auth import current_workspace_id
from ..db import get_db

router = APIRouter(prefix="/workspace/keys", tags=["workspace"])


class KeyIn(BaseModel):
    key: str = Field(min_length=1, max_length=500)


class KeyOut(BaseModel):
    kind: str
    last4: str
    verified: bool  # False when the provider could not be reached to confirm it


@router.get("", summary="Which providers this workspace has its own key for")
def list_keys(db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    return sec.list_secrets(db, workspace_id=workspace_id)


@router.put("/{kind}", response_model=KeyOut, summary="Store or replace a provider key")
def put_key(
    kind: str,
    body: KeyIn = Body(...),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
):
    if kind not in sec.KINDS:
        raise HTTPException(400, f"unknown provider {kind!r}; expected one of {', '.join(sec.KINDS)}")

    key = body.key.strip()
    if not key:
        raise HTTPException(400, "key is empty")

    # Refuse before touching the database — storing an unencrypted credential would be
    # worse than not accepting it at all.
    if not crypto.available():
        raise HTTPException(503, "secret encryption is not configured on this deployment")

    verdict = prov.validate_key(kind, key)
    if verdict == "invalid":
        raise HTTPException(400, f"{kind} rejected this key as invalid")

    row = sec.set_secret(db, workspace_id=workspace_id, kind=kind, plaintext=key)
    db.commit()
    # Stale status for the previous key would otherwise linger for the cache TTL.
    prov._cache.clear()
    return KeyOut(kind=row.kind, last4=row.last4, verified=verdict == "ok")


@router.delete("/{kind}", status_code=204, summary="Remove a key and fall back to the platform key")
def delete_key(kind: str, db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    if kind not in sec.KINDS:
        raise HTTPException(400, f"unknown provider {kind!r}")
    sec.delete_secret(db, workspace_id=workspace_id, kind=kind)
    db.commit()
    prov._cache.clear()
