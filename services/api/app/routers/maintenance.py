"""Housekeeping the scheduler calls, not the app.

These sweep every workspace in one pass, which is why they authenticate on the dataplane
shared secret alone and take no workspace scope. A tenant token must never reach them:
pruning is deletion, and a tenant pruning all workspaces is a tenant deleting other
people's data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from .. import retention
from ..config import get_settings
from ..db import get_db

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def require_machine(x_dataplane_secret: str | None = Header(default=None)) -> None:
    """Machine-to-machine only. Deliberately not `current_workspace_id`, which falls back
    to a header-supplied id when AUTH_PROVIDER=none and would let anyone in."""
    secret = get_settings().dataplane_shared_secret
    if not secret or x_dataplane_secret != secret:
        raise HTTPException(401, "maintenance endpoints require the dataplane secret")


@router.post("/prune-snapshots", summary="Drop stale snapshot payloads, keep the rows")
def prune_snapshots(
    keep_runs: int = Query(
        default=retention.DEFAULT_KEEP_RUNS,
        ge=retention.MIN_KEEP_RUNS,
        le=200,
        description="recent successful runs per watchlist whose payload is kept",
    ),
    db: Session = Depends(get_db),
    _: None = Depends(require_machine),
):
    """`snapshots` is the only table with unbounded per-run growth; nothing pruned it.

    The row survives — only `raw` is dropped. The metadata is the record that a fetch
    happened, and it is a few bytes against roughly 27 kB for a Google Search payload.
    """
    return retention.prune_snapshots(db, keep_runs=keep_runs)


@router.get("/snapshots", summary="What the snapshots table currently costs")
def snapshot_footprint(db: Session = Depends(get_db), _: None = Depends(require_machine)):
    """So the decision to prune is measured rather than guessed."""
    return retention.snapshot_footprint(db)
