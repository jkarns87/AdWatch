from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..auth import current_workspace_id, ensure_workspace, get_watchlist
from ..db import get_db

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _last_run(db: Session, watchlist_id: int) -> m.Run | None:
    return db.scalar(select(m.Run).where(m.Run.watchlist_id == watchlist_id).order_by(m.Run.id.desc()).limit(1))


@router.get("", response_model=list[s.WatchlistSummary])
def list_watchlists(db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    ensure_workspace(db, workspace_id)
    rows = db.scalars(select(m.Watchlist).where(m.Watchlist.workspace_id == workspace_id).order_by(m.Watchlist.id)).all()
    out = []
    for w in rows:
        lr = _last_run(db, w.id)
        open_changes = db.scalar(select(func.count(m.Change.id)).where(m.Change.watchlist_id == w.id, m.Change.insight_id.is_(None))) or 0
        out.append(
            s.WatchlistSummary(
                id=w.id,
                name=w.name,
                vertical=w.vertical,
                geo=w.geo,
                competitor_count=len(w.competitors),
                keyword_count=len(w.keywords),
                last_run_at=lr.finished_at if lr else None,
                open_changes=open_changes,
            )
        )
    return out


@router.post("", response_model=s.WatchlistDetail, status_code=201)
def create_watchlist(body: s.WatchlistCreate, db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    ensure_workspace(db, workspace_id)
    w = m.Watchlist(workspace_id=workspace_id, name=body.name, vertical=body.vertical, geo=body.geo or "US")
    db.add(w)
    db.commit()
    return _detail(db, w)


def _detail(db: Session, w: m.Watchlist) -> s.WatchlistDetail:
    comps = []
    for c in w.competitors:
        active = db.scalar(select(func.count(m.Creative.id)).where(m.Creative.competitor_id == c.id, m.Creative.active.is_(True))) or 0
        comps.append(s.CompetitorOut(id=c.id, name=c.name, domain=c.domain, advertiser_id=c.advertiser_id, active_creatives=active))
    lr = _last_run(db, w.id)
    return s.WatchlistDetail(
        id=w.id,
        name=w.name,
        vertical=w.vertical,
        geo=w.geo,
        created_at=w.created_at,
        competitors=comps,
        keywords=[s.KeywordOut.model_validate(k) for k in w.keywords],
        last_run=s.RunOut.model_validate(lr) if lr else None,
    )


@router.get("/{watchlist_id}", response_model=s.WatchlistDetail)
def get_one(w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    return _detail(db, w)


@router.post("/{watchlist_id}/competitors", response_model=s.CompetitorOut, status_code=201)
def add_competitor(body: s.CompetitorCreate, w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    c = m.Competitor(watchlist_id=w.id, name=body.name, domain=body.domain.lower().removeprefix("www."), advertiser_id=body.advertiser_id)
    db.add(c)
    db.commit()
    return s.CompetitorOut(id=c.id, name=c.name, domain=c.domain, advertiser_id=c.advertiser_id, active_creatives=0)


@router.delete("/{watchlist_id}/competitors/{competitor_id}", status_code=204)
def delete_competitor(competitor_id: int, w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    c = db.get(m.Competitor, competitor_id)
    if c is None or c.watchlist_id != w.id:
        raise HTTPException(404, "competitor not found")
    db.delete(c)
    db.commit()
    return Response(status_code=204)


@router.post("/{watchlist_id}/keywords", response_model=s.KeywordOut, status_code=201)
def add_keyword(body: s.KeywordCreate, w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    k = m.Keyword(watchlist_id=w.id, term=body.term.strip())
    db.add(k)
    db.commit()
    return s.KeywordOut.model_validate(k)


@router.delete("/{watchlist_id}/keywords/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int, w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    k = db.get(m.Keyword, keyword_id)
    if k is None or k.watchlist_id != w.id:
        raise HTTPException(404, "keyword not found")
    db.delete(k)
    db.commit()
    return Response(status_code=204)
