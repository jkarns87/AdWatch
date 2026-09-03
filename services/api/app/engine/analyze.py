from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..alerts.webhook import dispatch_insight
from ..alerts.xano import dispatch_via_xano
from ..config import get_settings
from ..metering import record_call
from ..workspace_secrets import resolve_key
from .analyst import Analyst


def watchlist_context(w: m.Watchlist) -> dict:
    return {
        "watchlist": w.name,
        "vertical": w.vertical,
        "geo": w.geo,
        "tracked_competitors": [{"name": c.name, "domain": c.domain} for c in w.competitors if not c.is_self],
        "our_domain": next((c.domain for c in w.competitors if c.is_self), None),
        "tracked_keywords": [k.term for k in w.keywords],
    }


def run_analyze(db: Session, watchlist: m.Watchlist, *, analyst: Analyst | None = None) -> tuple[list[m.Insight], int]:
    analyst = analyst or Analyst(
        api_key=resolve_key(
            db, workspace_id=watchlist.workspace_id, kind="anthropic",
            fallback=get_settings().anthropic_api_key,
        )
    )
    pending = db.scalars(
        select(m.Change).where(m.Change.watchlist_id == watchlist.id, m.Change.insight_id.is_(None)).order_by(m.Change.id)
    ).all()
    if not pending:
        return [], 0
    latest_run_id = max(c.run_id for c in pending)
    as_dicts = [
        {
            "id": c.id,
            "kind": c.kind,
            "severity": c.severity,
            "subject_type": c.subject_type,
            "subject_id": c.subject_id,
            "subject_label": c.subject_label,
            "payload": c.payload,
        }
        for c in pending
    ]
    by_id = {c.id: c for c in pending}
    insights: list[m.Insight] = []
    sent = 0
    for change_ids, result in analyst.analyze(watchlist_context(watchlist), as_dicts):
        # Pop before building the Insight so the marker cannot reach a persisted field.
        usage = result.pop("_usage", None)
        model = result.get("model", "")
        record_call(
            db,
            workspace_id=watchlist.workspace_id,
            model=model,
            feature="analyst",
            usage=usage,
            watchlist_id=watchlist.id,
            run_id=latest_run_id,
            status="fallback" if model == "fallback" else "ok",
        )
        ins = m.Insight(
            watchlist_id=watchlist.id,
            run_id=latest_run_id,
            model=result.get("model", ""),
            summary=result.get("summary", ""),
            why_it_matters=result.get("why_it_matters", ""),
            recommended_actions=result.get("recommended_actions", []),
            confidence=result.get("confidence", 0.0),
        )
        db.add(ins)
        db.flush()
        linked = []
        for cid in change_ids:
            by_id[cid].insight_id = ins.id
            linked.append(by_id[cid])
        insights.append(ins)
        dispatcher = get_settings().alert_dispatcher
        if dispatcher == "xano":
            ok = dispatch_via_xano(db, watchlist, ins, linked)
        elif dispatcher == "webhook":
            ok = dispatch_insight(db, watchlist, ins, linked)
        else:
            ok = False
        if ok:
            sent += 1
    db.commit()
    return insights, sent
