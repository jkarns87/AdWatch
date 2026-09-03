"""Read models: creatives, serp, trends, changes, insights."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..auth import get_watchlist
from ..db import get_db

router = APIRouter(prefix="/watchlists", tags=["reads"])


def tracked_domains(w: m.Watchlist) -> set[str]:
    """Domains that count as ours in a paid block, the workspace's own included —
    otherwise the SERP table marks every rival as tracked and the user as a stranger."""
    return {c.domain.lower() for c in w.competitors}


def _latest_run_id(db: Session, watchlist_id: int) -> int | None:
    return db.scalar(select(m.Run.id).where(m.Run.watchlist_id == watchlist_id, m.Run.status == "done").order_by(m.Run.id.desc()).limit(1))


def insight_out(db: Session, i: m.Insight) -> s.InsightOut:
    changes = db.scalars(select(m.Change).where(m.Change.insight_id == i.id).order_by(m.Change.id)).all()
    return s.InsightOut(
        id=i.id,
        run_id=i.run_id,
        created_at=i.created_at,
        model=i.model,
        confidence=i.confidence,
        summary=i.summary,
        why_it_matters=i.why_it_matters,
        recommended_actions=i.recommended_actions or [],
        change_ids=[c.id for c in changes],
        changes=[s.ChangeOut.model_validate(c) for c in changes],
    )


@router.get("/{watchlist_id}/creatives", response_model=list[s.CreativeOut])
def creatives(
    competitor_id: int | None = None,
    active: bool | None = True,
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    comp_ids = [c.id for c in w.competitors]
    if competitor_id is not None:
        if competitor_id not in comp_ids:
            raise HTTPException(404, "competitor not in watchlist")
        comp_ids = [competitor_id]
    q = select(m.Creative).where(m.Creative.competitor_id.in_(comp_ids))
    if active is not None:
        q = q.where(m.Creative.active.is_(active))
    rows = db.scalars(q.order_by(m.Creative.last_seen_run_id.desc(), m.Creative.id.desc())).all()
    return [s.CreativeOut.model_validate(r) for r in rows]


@router.get("/{watchlist_id}/serp", response_model=s.SerpOut)
def serp(keyword_id: int, w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    kw = next((k for k in w.keywords if k.id == keyword_id), None)
    if kw is None:
        raise HTTPException(404, "keyword not in watchlist")
    run_id = _latest_run_id(db, w.id)
    tracked = {c.domain.lower(): c.id for c in w.competitors}  # self included: see tracked_domains
    ads: list[s.SerpAdOut] = []
    if run_id:
        # block.desc() puts 'top' before 'bottom'
        rows = db.scalars(
            select(m.SerpAd)
            .where(m.SerpAd.keyword_id == kw.id, m.SerpAd.run_id == run_id)
            .order_by(m.SerpAd.block.desc(), m.SerpAd.position)
        ).all()
        for r in rows:
            ads.append(
                s.SerpAdOut(
                    position=r.position,
                    block=r.block,
                    advertiser_domain=r.advertiser_domain,
                    title=r.title,
                    description=r.description,
                    displayed_link=r.displayed_link,
                    is_tracked_competitor=r.advertiser_domain.lower() in tracked,
                    competitor_id=tracked.get(r.advertiser_domain.lower()),
                )
            )
    # share of voice across all runs for this keyword
    agg: dict[str, list[int]] = defaultdict(list)
    for r in db.scalars(select(m.SerpAd).where(m.SerpAd.keyword_id == kw.id)).all():
        agg[r.advertiser_domain].append(r.position)
    sov = sorted(
        (s.ShareOfVoice(advertiser_domain=d, appearances=len(p), avg_position=round(sum(p) / len(p), 2)) for d, p in agg.items()),
        key=lambda x: (-x.appearances, x.avg_position),
    )
    return s.SerpOut(keyword=s.KeywordOut.model_validate(kw), run_id=run_id, ads=ads, share_of_voice=sov)


@router.get("/{watchlist_id}/trends", response_model=s.TrendsOut)
def trends(keyword_id: int, w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    kw = next((k for k in w.keywords if k.id == keyword_id), None)
    if kw is None:
        raise HTTPException(404, "keyword not in watchlist")
    run_id = db.scalar(
        select(m.TrendPoint.run_id).where(m.TrendPoint.keyword_id == kw.id).order_by(m.TrendPoint.run_id.desc()).limit(1)
    )
    timeline = []
    rising, top = [], []
    if run_id:
        timeline = [
            s.TrendPointOut(date=p.date, value=p.value)
            for p in db.scalars(select(m.TrendPoint).where(m.TrendPoint.keyword_id == kw.id, m.TrendPoint.run_id == run_id).order_by(m.TrendPoint.date)).all()
        ]
        rq_run = db.scalar(select(m.RelatedQuery.run_id).where(m.RelatedQuery.keyword_id == kw.id).order_by(m.RelatedQuery.run_id.desc()).limit(1))
        if rq_run:
            for r in db.scalars(select(m.RelatedQuery).where(m.RelatedQuery.keyword_id == kw.id, m.RelatedQuery.run_id == rq_run)).all():
                (rising if r.bucket == "rising" else top).append(s.RelatedOut(query=r.query, value_text=r.value_text, value_num=r.value_num))
    return s.TrendsOut(keyword=s.KeywordOut.model_validate(kw), run_id=run_id, timeline=timeline, related_rising=rising, related_top=top)


@router.get("/{watchlist_id}/changes", response_model=list[s.ChangeOut])
def changes(
    since: datetime | None = None,
    kind: str | None = None,
    limit: int = Query(default=50, le=500),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    q = select(m.Change).where(m.Change.watchlist_id == w.id)
    if since:
        q = q.where(m.Change.detected_at >= since)
    if kind:
        q = q.where(m.Change.kind == kind)
    rows = db.scalars(q.order_by(m.Change.id.desc()).limit(limit)).all()
    return [s.ChangeOut.model_validate(r) for r in rows]


@router.get("/{watchlist_id}/insights", response_model=list[s.InsightOut])
def insights(limit: int = Query(default=20, le=200), w: m.Watchlist = Depends(get_watchlist), db: Session = Depends(get_db)):
    rows = db.scalars(select(m.Insight).where(m.Insight.watchlist_id == w.id).order_by(m.Insight.id.desc()).limit(limit)).all()
    return [insight_out(db, i) for i in rows]
