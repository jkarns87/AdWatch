"""Seed the demo watchlist.

  synthetic  -> fictitious advertisers via SyntheticSerpApiClient; two runs so diffs + insights exist. No quota.
  live       -> reads seed/demo_config.json (git-ignored) for real domains/keywords; ONE run (baseline).
                Run `make collect` again later for the second run. Spends quota.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import ensure_workspace
from ..engine.analyze import run_analyze
from ..engine.collect import run_collect
from .synthetic import FICTIONAL_COMPETITORS, FICTIONAL_KEYWORDS, SyntheticSerpApiClient

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "seed" / "demo_config.json"


def reset(db: Session, *, workspace_id: int) -> None:
    """Delete one workspace's data. Scoped deliberately: this previously issued an
    unqualified DELETE against every table, so any caller wiped every tenant.

    Order follows the foreign keys — children before parents. Changes go before
    Insights (Change.insight_id references them), and LlmCall before Run and
    Watchlist. Everything reaches the workspace through Watchlist except LlmCall,
    which carries workspace_id directly.
    """
    watchlists = select(m.Watchlist.id).where(m.Watchlist.workspace_id == workspace_id)
    competitors = select(m.Competitor.id).where(m.Competitor.watchlist_id.in_(watchlists))
    keywords = select(m.Keyword.id).where(m.Keyword.watchlist_id.in_(watchlists))
    insights = select(m.Insight.id).where(m.Insight.watchlist_id.in_(watchlists))

    statements = (
        delete(m.Alert).where(m.Alert.insight_id.in_(insights)),
        delete(m.Change).where(m.Change.watchlist_id.in_(watchlists)),
        delete(m.Insight).where(m.Insight.watchlist_id.in_(watchlists)),
        delete(m.RelatedQuery).where(m.RelatedQuery.keyword_id.in_(keywords)),
        delete(m.TrendPoint).where(m.TrendPoint.keyword_id.in_(keywords)),
        delete(m.SerpAd).where(m.SerpAd.keyword_id.in_(keywords)),
        delete(m.ProductListing).where(m.ProductListing.keyword_id.in_(keywords)),
        delete(m.Creative).where(m.Creative.competitor_id.in_(competitors)),
        delete(m.Snapshot).where(m.Snapshot.watchlist_id.in_(watchlists)),
        delete(m.LlmCall).where(m.LlmCall.workspace_id == workspace_id),
        delete(m.Run).where(m.Run.watchlist_id.in_(watchlists)),
        delete(m.Keyword).where(m.Keyword.watchlist_id.in_(watchlists)),
        delete(m.Competitor).where(m.Competitor.watchlist_id.in_(watchlists)),
        delete(m.Watchlist).where(m.Watchlist.workspace_id == workspace_id),
    )
    for stmt in statements:
        db.execute(stmt, execution_options={"synchronize_session": False})
    db.commit()


def _ensure_watchlist(db: Session, workspace_id: int, name: str, vertical: str, geo: str, competitors: list[dict], keywords: list[str], location: str | None = None) -> m.Watchlist:
    ensure_workspace(db, workspace_id)
    w = db.scalar(select(m.Watchlist).where(m.Watchlist.workspace_id == workspace_id, m.Watchlist.name == name))
    if w is None:
        w = m.Watchlist(workspace_id=workspace_id, name=name, vertical=vertical, geo=geo, location=location)
        db.add(w)
        db.flush()
        for c in competitors:
            db.add(m.Competitor(watchlist_id=w.id, name=c["name"], domain=c["domain"].lower(), advertiser_id=c.get("advertiser_id")))
        for k in keywords:
            db.add(m.Keyword(watchlist_id=w.id, term=k))
        db.commit()
        db.refresh(w)
    return w


def seed_synthetic(db: Session, *, workspace_id: int = 1, vertical: str | None = None) -> dict:
    w = _ensure_watchlist(db, workspace_id, "Specialty Coffee — Bay Area", vertical or "specialty coffee", "US", FICTIONAL_COMPETITORS, FICTIONAL_KEYWORDS, location="San Francisco, California, United States")
    run_ids: list[int] = []
    n_changes = 0
    for idx in (0, 1):
        run, _, changes = run_collect(db, w, client=SyntheticSerpApiClient(run_index=idx))
        run_ids.append(run.id)
        n_changes += len(changes)
    insights, _ = run_analyze(db, w)
    return {"watchlist_id": w.id, "runs": run_ids, "changes": n_changes, "insights": len(insights)}


def seed_live(db: Session, *, workspace_id: int = 1, vertical: str | None = None) -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"{CONFIG_PATH} missing — copy demo_config.example.json and fill in real domains/keywords")
    cfg = json.loads(CONFIG_PATH.read_text())
    w = _ensure_watchlist(db, workspace_id, cfg["name"], vertical or cfg.get("vertical", ""), cfg.get("geo", "US"), cfg["competitors"], cfg["keywords"], location=cfg.get("location"))
    run, _, changes = run_collect(db, w)
    insights, _ = run_analyze(db, w)
    return {"watchlist_id": w.id, "runs": [run.id], "changes": len(changes), "insights": len(insights)}
