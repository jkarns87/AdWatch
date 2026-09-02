"""Workspace resolution.

AUTH_PROVIDER=none  -> X-Workspace-Id header (default 1). Dev / Xano-cut fallback.
AUTH_PROVIDER=xano  -> Bearer token is introspected against the Xano control plane
                       (GET {XANO_BASE_URL}/auth/me -> {workspace_id}); results cached briefly.
Either mode: a request carrying X-Dataplane-Secret == DATAPLANE_SHARED_SECRET may set
X-Workspace-Id directly (used by Xano's scheduled collector task).
"""

from __future__ import annotations

import time

import httpx
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .config import get_settings
from .db import get_db

_introspect_cache: dict[str, tuple[float, int]] = {}
_CACHE_TTL_S = 300


def _introspect_xano(token: str) -> int:
    s = get_settings()
    hit = _introspect_cache.get(token)
    if hit and hit[0] > time.time():
        return hit[1]
    if not s.xano_base_url:
        raise HTTPException(500, "XANO_BASE_URL not configured")
    try:
        r = httpx.get(f"{s.xano_base_url.rstrip('/')}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"auth introspection failed: {e.__class__.__name__}") from e
    if r.status_code != 200:
        raise HTTPException(401, "invalid or expired token")
    wid = (r.json() or {}).get("workspace_id")
    if not wid:
        raise HTTPException(401, "token has no workspace_id")
    _introspect_cache[token] = (time.time() + _CACHE_TTL_S, int(wid))
    return int(wid)


def current_workspace_id(
    authorization: str | None = Header(default=None),
    x_workspace_id: int | None = Header(default=None),
    x_dataplane_secret: str | None = Header(default=None),
) -> int:
    s = get_settings()
    # machine-to-machine (Xano scheduled task, ops scripts)
    if s.dataplane_shared_secret and x_dataplane_secret == s.dataplane_shared_secret and x_workspace_id:
        return int(x_workspace_id)
    if s.auth_provider == "xano":
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "missing bearer token")
        return _introspect_xano(authorization.split(" ", 1)[1].strip())
    return int(x_workspace_id or 1)


def ensure_workspace(db: Session, workspace_id: int) -> m.Workspace:
    ws = db.get(m.Workspace, workspace_id)
    if ws is None:
        ws = m.Workspace(id=workspace_id, name=f"workspace-{workspace_id}")
        db.add(ws)
        db.commit()
    return ws


def get_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
) -> m.Watchlist:
    w = db.scalar(select(m.Watchlist).where(m.Watchlist.id == watchlist_id, m.Watchlist.workspace_id == workspace_id))
    if w is None:
        raise HTTPException(404, "watchlist not found")
    return w
