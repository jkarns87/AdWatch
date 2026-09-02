"""Webhook alerts. Works for Slack and Discord incoming webhooks (both accept a plain JSON body;
Slack reads `text`, Discord reads `content`, so we send both)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from .. import models as m
from ..config import get_settings

log = logging.getLogger(__name__)

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def format_insight(watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change]) -> str:
    top = max((c.severity for c in changes), key=lambda s: SEVERITY_ORDER.get(s, 0), default="medium")
    lines = [f"*AdWatch · {watchlist.name}* — {top.upper()} ({len(changes)} change{'s' if len(changes) != 1 else ''})", insight.summary]
    if insight.why_it_matters:
        lines.append(f"_Why it matters:_ {insight.why_it_matters}")
    for a in (insight.recommended_actions or [])[:3]:
        lines.append(f"• [{a.get('urgency', '')}/{a.get('effort', '')}] {a.get('action', '')}")
    return "\n".join(lines)


def dispatch_insight(db: Session, watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change], *, min_severity: str = "medium") -> bool:
    url = get_settings().webhook_url
    if not url:
        return False
    top = max((SEVERITY_ORDER.get(c.severity, 0) for c in changes), default=0)
    if top < SEVERITY_ORDER.get(min_severity, 1):
        return False
    text = format_insight(watchlist, insight, changes)
    alert = m.Alert(insight_id=insight.id, channel="webhook", target=url[:60] + "…")
    db.add(alert)
    try:
        r = httpx.post(url, json={"text": text, "content": text[:1900]}, timeout=10)
        r.raise_for_status()
        alert.status, alert.sent_at = "sent", datetime.now(UTC)
        return True
    except Exception as e:
        log.warning("webhook failed: %s", e)
        alert.status, alert.error = "failed", str(e)[:500]
        return False
