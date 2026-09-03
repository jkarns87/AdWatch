"""Reads across runs, rather than pinned to the latest one.

serp_ads, trend_points and the creative flight columns are all stored per run and cost
real SerpApi quota to collect, but every existing endpoint filters to _latest_run_id.
The run_id foreign keys existed only so the diff engine could compare run N to N-1, so
none of that history was reachable: you could not ask what a competitor's position on a
keyword had been over the last eight runs, or when a creative started and stopped.

No new data is collected here. This reads what is already stored.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import get_watchlist
from ..db import get_db

router = APIRouter(prefix="/watchlists", tags=["history"])


@router.get("/{watchlist_id}/history/creatives", summary="Creative flights, including ones that have stopped")
def creative_flights(
    competitor_id: int | None = None,
    limit: int = Query(default=200, le=1000),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    """Every creative ever seen, with when it started and stopped.

    The latest-run view shows only what is live now, so a creative that ran for a
    fortnight and stopped is invisible there — which is exactly the thing worth seeing.
    """
    comps = {c.id: c for c in w.competitors}
    if competitor_id is not None:
        if competitor_id not in comps:
            raise HTTPException(404, "competitor not in watchlist")
        wanted = [competitor_id]
    else:
        wanted = list(comps)
    if not wanted:
        return []

    rows = db.scalars(
        select(m.Creative)
        .where(m.Creative.competitor_id.in_(wanted))
        .order_by(m.Creative.last_shown.desc().nulls_last(), m.Creative.id.desc())
        .limit(limit)
    ).all()

    out = []
    for r in rows:
        comp = comps[r.competitor_id]
        # Inclusive of both ends: a creative first and last seen on the same day ran
        # for a day, not zero.
        days = (r.last_shown - r.first_shown).days + 1 if r.first_shown and r.last_shown else None
        out.append({
            "creative_id": r.creative_id,
            "competitor_id": r.competitor_id,
            "competitor_name": comp.name,
            "is_self": comp.is_self,
            "format": r.format,
            "platform": r.platform,
            "first_shown": r.first_shown,
            "last_shown": r.last_shown,
            "days_live": days,
            "active": r.active,
            "first_seen_run_id": r.first_seen_run_id,
            "last_seen_run_id": r.last_seen_run_id,
            "details_url": r.details_url,
            "image_url": r.image_url,
            "text": r.text,
            "total_days_shown": r.total_days_shown,
        })
    return out


@router.get("/{watchlist_id}/history/serp", summary="A keyword's paid block across runs")
def serp_history(
    keyword_id: int,
    runs: int = Query(default=12, le=60, description="how many recent runs to include"),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    """Position per advertiser, per run — the series a chart needs."""
    kw = next((k for k in w.keywords if k.id == keyword_id), None)
    if kw is None:
        raise HTTPException(404, "keyword not in watchlist")

    recent = db.scalars(
        select(m.Run)
        .where(m.Run.watchlist_id == w.id, m.Run.status == "done")
        .order_by(m.Run.id.desc())
        .limit(runs)
    ).all()
    recent = list(reversed(recent))  # oldest first: a series reads left to right
    if not recent:
        return {"keyword": {"id": kw.id, "term": kw.term}, "runs": [], "series": []}

    run_ids = [r.id for r in recent]
    ads = db.scalars(
        select(m.SerpAd).where(m.SerpAd.keyword_id == kw.id, m.SerpAd.run_id.in_(run_ids))
    ).all()

    tracked = {c.domain.lower(): c for c in w.competitors}
    points: dict[str, list[dict]] = defaultdict(list)
    for a in ads:
        points[a.advertiser_domain].append(
            {"run_id": a.run_id, "position": a.position, "block": a.block}
        )

    order = {rid: i for i, rid in enumerate(run_ids)}
    series = []
    for domain, pts in points.items():
        # An advertiser absent from a run simply has no point for it. Emitting a zero
        # would draw a drop to the top of the page instead of a gap.
        pts.sort(key=lambda p: order[p["run_id"]])
        comp = tracked.get(domain.lower())
        series.append({
            "advertiser_domain": domain,
            "tracked": comp is not None,
            "is_self": bool(comp and comp.is_self),
            "competitor_id": comp.id if comp else None,
            "appearances": len(pts),
            "points": pts,
        })
    # Most-present first, then best average position — the ones worth charting.
    series.sort(key=lambda s: (-s["appearances"], sum(p["position"] for p in s["points"]) / len(s["points"])))

    return {
        "keyword": {"id": kw.id, "term": kw.term},
        "runs": [{"run_id": r.id, "finished_at": r.finished_at, "searches_used": r.searches_used} for r in recent],
        "series": series,
    }
