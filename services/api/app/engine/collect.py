"""Collection orchestration: one `run` per watchlist -> snapshots -> normalized rows -> changes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..collectors.normalize import (
    creatives_from_ads_transparency,
    related_queries_from_trends,
    serp_ads_from_google,
    trend_points_from_timeseries,
)
from ..collectors.serpapi_client import SerpApiClient, SerpApiError
from ..redact import redact
from . import diff

log = logging.getLogger(__name__)


def _previous_run(db: Session, watchlist_id: int, before_run_id: int) -> m.Run | None:
    return db.scalar(
        select(m.Run)
        .where(m.Run.watchlist_id == watchlist_id, m.Run.id < before_run_id, m.Run.status == "done")
        .order_by(m.Run.id.desc())
        .limit(1)
    )


def _snapshot(db: Session, run: m.Run, kind: str, subject_type: str, subject_id: int, res) -> m.Snapshot:
    snap = m.Snapshot(
        run_id=run.id,
        watchlist_id=run.watchlist_id,
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        serpapi_search_id=res.search_id,
        from_cache=res.from_cache,
        raw=res.data,
    )
    db.add(snap)
    return snap


def active_creatives_view(db: Session, competitor_id: int, run_id: int | None) -> list[dict] | None:
    """Creatives that were active as of `run_id` (i.e. last_seen_run_id >= run_id and first_seen <= run_id).
    None if the competitor had never been collected before that run."""
    if run_id is None:
        return None
    collected_before = db.scalar(
        select(m.Snapshot.id).where(
            m.Snapshot.run_id == run_id,
            m.Snapshot.subject_type == "competitor",
            m.Snapshot.subject_id == competitor_id,
            m.Snapshot.kind == "ads_transparency",
        )
    )
    if collected_before is None:
        return None
    rows = db.scalars(
        select(m.Creative).where(
            m.Creative.competitor_id == competitor_id,
            m.Creative.first_seen_run_id <= run_id,
            m.Creative.last_seen_run_id >= run_id,
        )
    ).all()
    return [
        {"creative_id": r.creative_id, "format": r.format, "details_url": r.details_url, "image_url": r.image_url, "text": r.text}
        for r in rows
    ]


def serp_view(db: Session, keyword_id: int, run_id: int | None) -> list[dict] | None:
    if run_id is None:
        return None
    rows = db.scalars(select(m.SerpAd).where(m.SerpAd.keyword_id == keyword_id, m.SerpAd.run_id == run_id)).all()
    if not rows:
        # distinguish "no ads that run" from "never collected": check any snapshot for this keyword/run
        snap = db.scalar(
            select(m.Snapshot.id).where(
                m.Snapshot.run_id == run_id, m.Snapshot.subject_type == "keyword", m.Snapshot.subject_id == keyword_id, m.Snapshot.kind == "search_ads"
            )
        )
        return [] if snap else None
    return [
        {"advertiser_domain": r.advertiser_domain, "position": r.position, "block": r.block, "title": r.title}
        for r in rows
    ]


def related_view(db: Session, keyword_id: int, run_id: int | None) -> list[dict] | None:
    if run_id is None:
        return None
    rows = db.scalars(select(m.RelatedQuery).where(m.RelatedQuery.keyword_id == keyword_id, m.RelatedQuery.run_id == run_id)).all()
    if not rows:
        snap = db.scalar(
            select(m.Snapshot.id).where(
                m.Snapshot.run_id == run_id, m.Snapshot.subject_type == "keyword", m.Snapshot.subject_id == keyword_id, m.Snapshot.kind == "related_queries"
            )
        )
        return [] if snap else None
    return [{"query": r.query, "bucket": r.bucket, "value_text": r.value_text, "value_num": r.value_num} for r in rows]


def upsert_creatives(db: Session, competitor: m.Competitor, run: m.Run, rows: list[dict]) -> None:
    existing = {c.creative_id: c for c in db.scalars(select(m.Creative).where(m.Creative.competitor_id == competitor.id)).all()}
    seen: set[str] = set()
    for r in rows:
        cid = r["creative_id"]
        seen.add(cid)
        c = existing.get(cid)
        if c is None:
            c = m.Creative(
                competitor_id=competitor.id,
                creative_id=cid,
                format=r["format"],
                platform=r.get("platform"),
                target_domain=r.get("target_domain"),
                image_url=r.get("image_url"),
                details_url=r.get("details_url"),
                first_shown=r.get("first_shown"),
                last_shown=r.get("last_shown"),
                text=r.get("text"),
                first_seen_run_id=run.id,
                last_seen_run_id=run.id,
                active=True,
            )
            db.add(c)
        else:
            c.last_seen_run_id = run.id
            c.last_shown = r.get("last_shown") or c.last_shown
            c.image_url = r.get("image_url") or c.image_url
            c.active = True
    for cid, c in existing.items():
        if cid not in seen and c.active:
            c.active = False


def run_collect(db: Session, watchlist: m.Watchlist, *, client: SerpApiClient | None = None, fresh: bool = False) -> tuple[m.Run, int, list[m.Change]]:
    client = client or SerpApiClient()
    run = m.Run(watchlist_id=watchlist.id, status="running")
    db.add(run)
    db.flush()
    prev_run = _previous_run(db, watchlist.id, run.id)
    prev_id = prev_run.id if prev_run else None
    tracked = {c.domain.lower() for c in watchlist.competitors}
    changes: list[m.Change] = []
    n_snapshots = 0

    try:
        for comp in watchlist.competitors:
            previous = active_creatives_view(db, comp.id, prev_id)
            res = client.ads_transparency(domain=comp.domain, advertiser_id=comp.advertiser_id, fresh=fresh)
            _snapshot(db, run, "ads_transparency", "competitor", comp.id, res)
            n_snapshots += 1
            rows = creatives_from_ads_transparency(res.data)
            upsert_creatives(db, comp, run, rows)
            for ch in diff.diff_creatives(previous, rows, competitor_id=comp.id, label=comp.name):
                changes.append(m.Change(watchlist_id=watchlist.id, run_id=run.id, **ch))

        gl = (watchlist.geo or "US").lower()
        for kw in watchlist.keywords:
            # paid block
            prev_serp = serp_view(db, kw.id, prev_id)
            res = client.google_search(q=kw.term, gl=gl, location=watchlist.location, fresh=fresh)
            _snapshot(db, run, "search_ads", "keyword", kw.id, res)
            n_snapshots += 1
            ads = serp_ads_from_google(res.data)
            for a in ads:
                db.add(m.SerpAd(keyword_id=kw.id, run_id=run.id, **a))
            for ch in diff.diff_serp_ads(prev_serp, ads, keyword_id=kw.id, label=kw.term, tracked_domains=tracked):
                changes.append(m.Change(watchlist_id=watchlist.id, run_id=run.id, **ch))

            # demand
            res = client.trends_timeseries(q=kw.term, geo=watchlist.geo or "US", fresh=fresh)
            _snapshot(db, run, "trends", "keyword", kw.id, res)
            n_snapshots += 1
            pts = trend_points_from_timeseries(res.data)
            for p in pts:
                db.add(m.TrendPoint(keyword_id=kw.id, run_id=run.id, **p))
            for ch in diff.diff_trends(pts, keyword_id=kw.id, label=kw.term, had_previous_run=prev_id is not None):
                changes.append(m.Change(watchlist_id=watchlist.id, run_id=run.id, **ch))

            prev_rel = related_view(db, kw.id, prev_id)
            res = client.trends_related_queries(q=kw.term, geo=watchlist.geo or "US", fresh=fresh)
            _snapshot(db, run, "related_queries", "keyword", kw.id, res)
            n_snapshots += 1
            rel = related_queries_from_trends(res.data)
            for r in rel:
                db.add(m.RelatedQuery(keyword_id=kw.id, run_id=run.id, **r))
            for ch in diff.diff_related_queries(prev_rel, rel, keyword_id=kw.id, label=kw.term):
                changes.append(m.Change(watchlist_id=watchlist.id, run_id=run.id, **ch))

        for ch in changes:
            db.add(ch)
        run.status = "done"
    except SerpApiError as e:
        log.exception("collect failed")
        run.status = "failed"
        run.error = redact(str(e))
    finally:
        run.searches_used = client.searches_used
        run.finished_at = datetime.now(UTC)
        db.commit()
    return run, n_snapshots, changes
