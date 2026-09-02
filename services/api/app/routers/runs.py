"""collect / analyze / collect-and-analyze."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..auth import get_watchlist
from ..db import get_db
from ..engine.analyze import run_analyze
from ..engine.collect import run_collect
from .reads import insight_out

router = APIRouter(prefix="/watchlists", tags=["runs"])


@router.post("/{watchlist_id}/collect", response_model=s.CollectOut)
def collect(
    fresh: bool = Query(default=False, description="bypass the local SerpApi cache"),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    if not w.competitors and not w.keywords:
        raise HTTPException(400, "add at least one competitor or keyword first")
    run, n, changes = run_collect(db, w, fresh=fresh)
    if run.status == "failed":
        raise HTTPException(502, f"collect failed: {run.error}")
    return s.CollectOut(run=s.RunOut.model_validate(run), snapshots=n, changes=[s.ChangeOut.model_validate(c) for c in changes])


@router.post("/{watchlist_id}/analyze", response_model=s.AnalyzeOut)
def analyze(w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    insights, sent = run_analyze(db, w)
    return s.AnalyzeOut(insights=[insight_out(db, i) for i in insights], alerts_sent=sent)


@router.post("/{watchlist_id}/collect-and-analyze", response_model=s.CollectAnalyzeOut)
def collect_and_analyze(
    fresh: bool = Query(default=False),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    if not w.competitors and not w.keywords:
        raise HTTPException(400, "add at least one competitor or keyword first")
    run, n, changes = run_collect(db, w, fresh=fresh)
    if run.status == "failed":
        raise HTTPException(502, f"collect failed: {run.error}")
    insights, sent = run_analyze(db, w)
    return s.CollectAnalyzeOut(
        run=s.RunOut.model_validate(run),
        snapshots=n,
        changes=[s.ChangeOut.model_validate(c) for c in changes],
        insights=[insight_out(db, i) for i in insights],
        alerts_sent=sent,
    )
