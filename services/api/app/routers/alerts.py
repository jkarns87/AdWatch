"""GET /alerts — the workspace-wide notification feed.

Replaces the frontend's 1+N (api.watchlists() then api.insights() per watchlist).

The feed is insight-centric because that is what the page renders and what a person
reads. The alerts table is a *delivery log*, so it hangs off each item rather than
driving the list: alerts only dispatch above min_severity, and an insight nobody was
paged about is still something the user should see.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..auth import current_workspace_id
from ..db import get_db
from ..redact import redact

router = APIRouter(prefix="/alerts", tags=["alerts"])

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@router.get("", response_model=list[s.AlertFeedItem], summary="Notification feed across every watchlist")
def feed(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
):
    rows = db.execute(
        select(m.Insight, m.Watchlist)
        .join(m.Watchlist, m.Insight.watchlist_id == m.Watchlist.id)
        .where(m.Watchlist.workspace_id == workspace_id)
        .order_by(m.Insight.created_at.desc(), m.Insight.id.desc())
        .limit(limit)
    ).all()
    if not rows:
        return []

    insight_ids = [i.id for i, _ in rows]

    # Two grouped lookups rather than a query per row — this endpoint exists to
    # remove an N+1, so it should not introduce one.
    severities: dict[int, list[str]] = defaultdict(list)
    for iid, sev in db.execute(
        select(m.Change.insight_id, m.Change.severity).where(m.Change.insight_id.in_(insight_ids))
    ).all():
        severities[iid].append(sev)

    deliveries: dict[int, m.Alert] = {}
    for alert in db.scalars(
        select(m.Alert).where(m.Alert.insight_id.in_(insight_ids)).order_by(m.Alert.id)
    ).all():
        deliveries[alert.insight_id] = alert  # last write wins: the most recent attempt

    out: list[s.AlertFeedItem] = []
    for insight, watchlist in rows:
        linked = severities.get(insight.id, [])
        worst = min(linked, key=lambda x: SEVERITY_RANK.get(x, 9), default="low")
        alert = deliveries.get(insight.id)
        out.append(
            s.AlertFeedItem(
                id=insight.id,
                watchlist_id=watchlist.id,
                watchlist_name=watchlist.name,
                severity=worst,
                summary=insight.summary,
                why_it_matters=insight.why_it_matters,
                created_at=insight.created_at,
                delivery=(
                    s.AlertDelivery(
                        channel=alert.channel,
                        status=alert.status,
                        target=redact(alert.target),
                        sent_at=alert.sent_at,
                        error=redact(alert.error) or None,
                    )
                    if alert
                    else None
                ),
            )
        )
    return out
