"""Route an insight through the Xano control plane, which fans it out to the workspace's
alert_pref destinations (webhook / email) and logs each delivery in alert_log."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from .. import models as m
from ..config import get_settings
from .webhook import SEVERITY_ORDER

log = logging.getLogger(__name__)


def dispatch_via_xano(db: Session, watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change]) -> bool:
    s = get_settings()
    if not (s.xano_base_url and s.dataplane_shared_secret):
        return False
    top = max((c.severity for c in changes), key=lambda x: SEVERITY_ORDER.get(x, 0), default="medium")
    payload = {
        "workspace_id": watchlist.workspace_id,
        "insight_id": insight.id,
        "watchlist_id": watchlist.id,
        "severity": top,
        "title": watchlist.name,
        "summary": insight.summary,
        "why_it_matters": insight.why_it_matters or "",
        "actions": insight.recommended_actions or [],
        "dashboard_url": f"{s.dashboard_url.rstrip('/')}/w/{watchlist.id}",
    }
    alert = m.Alert(insight_id=insight.id, channel="xano", target="control-plane")
    db.add(alert)
    try:
        r = httpx.post(
            f"{s.xano_base_url.rstrip('/')}/internal/dispatch",
            json=payload,
            headers={"X-Dataplane-Secret": s.dataplane_shared_secret},
            timeout=20,
        )
        r.raise_for_status()
        sent = int((r.json() or {}).get("sent", 0))
        alert.status = "sent" if sent else "failed"
        alert.sent_at = datetime.now(UTC)
        alert.error = None if sent else "no destinations accepted it"
        return sent > 0
    except Exception as e:  # noqa: BLE001
        log.warning("xano dispatch failed: %s", e)
        alert.status, alert.error = "failed", str(e)[:500]
        return False
