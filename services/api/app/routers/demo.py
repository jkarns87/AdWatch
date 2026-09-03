from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas as s
from ..auth import current_workspace_id
from ..config import get_settings
from ..db import get_db
from ..seed.demo import reset, seed_live, seed_synthetic

router = APIRouter(prefix="/demo", tags=["demo"])


def _guard():
    if not get_settings().demo_enabled:
        raise HTTPException(404, "demo endpoints disabled")


@router.post("/seed", response_model=s.SeedOut)
def seed(body: s.SeedIn, db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    _guard()
    try:
        if body.mode == "live":
            return seed_live(db, workspace_id=workspace_id, vertical=body.vertical)
        return seed_synthetic(db, workspace_id=workspace_id, vertical=body.vertical)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/reset", status_code=204)
def reset_all(db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    """Auth is not optional here: reset() DELETEs twelve tables including every
    Snapshot.raw row, which cost real SerpApi quota to collect and is not recoverable.
    _guard() alone only checks that demo mode is on — it authenticates nobody."""
    _guard()
    reset(db, workspace_id=workspace_id)
