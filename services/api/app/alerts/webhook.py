"""Webhook alerts (data-plane fallback when ALERT_DISPATCHER=webhook).

Slack incoming webhooks (hooks.slack.com) get a Block Kit message; everything else (Discord,
generic) gets a plain payload with both `text` (Slack-style) and `content` (Discord-style).
When ALERT_DISPATCHER=xano the control plane does the fan-out instead (see alerts/xano.py)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from .. import models as m
from ..config import get_settings
from ..redact import redact

log = logging.getLogger(__name__)

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
SEVERITY_ICON = {"high": ":red_circle:", "medium": ":large_orange_circle:", "low": ":large_green_circle:"}


def _top_severity(changes: list[m.Change]) -> str:
    return max((c.severity for c in changes), key=lambda s: SEVERITY_ORDER.get(s, 0), default="medium")


def _dashboard_link(watchlist: m.Watchlist) -> str:
    return f"{get_settings().dashboard_url.rstrip('/')}/watchlists/{watchlist.id}"


def format_insight(watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change]) -> str:
    """Plain-text rendering (Discord / generic / Slack fallback `text`)."""
    top = _top_severity(changes)
    lines = [f"*AdWatch · {watchlist.name}* — {top.upper()} ({len(changes)} change{'s' if len(changes) != 1 else ''})", insight.summary]
    if insight.why_it_matters:
        lines.append(f"_Why it matters:_ {insight.why_it_matters}")
    for a in (insight.recommended_actions or [])[:3]:
        lines.append(f"• [{a.get('urgency', '')}/{a.get('effort', '')}] {a.get('action', '')}")
    lines.append(_dashboard_link(watchlist))
    return "\n".join(lines)


def slack_blocks(watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change]) -> dict[str, Any]:
    """Slack Block Kit payload. `text` is the notification fallback; `blocks` is what renders."""
    top = _top_severity(changes)
    kinds: dict[str, int] = {}
    for c in changes:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    kind_line = " · ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])) or "no changes"
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"AdWatch · {watchlist.name}", "emoji": True}},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{SEVERITY_ICON.get(top, ':white_circle:')} *{top.upper()}* severity · {len(changes)} change{'s' if len(changes) != 1 else ''} · {kind_line}"}],
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": insight.summary[:2900] or "_(no summary)_"}},
    ]
    if insight.why_it_matters:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"_Why it matters:_ {insight.why_it_matters[:2800]}"}})
    actions = (insight.recommended_actions or [])[:3]
    if actions:
        body = "\n".join(f"• *{a.get('action', '')}*  `{a.get('urgency', '').replace('_', ' ')}` · effort {a.get('effort', '')}" for a in actions)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Recommended actions*\n{body}"[:2900]}})
    blocks.append(
        {
            "type": "actions",
            "elements": [{"type": "button", "text": {"type": "plain_text", "text": "Open in AdWatch", "emoji": True}, "url": _dashboard_link(watchlist), "style": "primary"}],
        }
    )
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"insight #{insight.id} · confidence {int((insight.confidence or 0) * 100)}% · {insight.model or 'analyst'}"}]})
    return {"text": f"AdWatch · {watchlist.name} — {top.upper()}: {insight.summary[:200]}", "blocks": blocks}


def build_payload(url: str, watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change]) -> dict[str, Any]:
    if "hooks.slack.com" in url:
        return slack_blocks(watchlist, insight, changes)
    text = format_insight(watchlist, insight, changes)
    return {"text": text, "content": text[:1900]}


def dispatch_insight(db: Session, watchlist: m.Watchlist, insight: m.Insight, changes: list[m.Change], *, min_severity: str = "medium") -> bool:
    url = get_settings().webhook_url
    if not url:
        return False
    top = max((SEVERITY_ORDER.get(c.severity, 0) for c in changes), default=0)
    if top < SEVERITY_ORDER.get(min_severity, 1):
        return False
    payload = build_payload(url, watchlist, insight, changes)
    channel = "slack" if "hooks.slack.com" in url else "webhook"
    alert = m.Alert(insight_id=insight.id, channel=channel, target=url[:60] + "…")
    db.add(alert)
    try:
        r = httpx.post(url, json=payload, timeout=10)
        r.raise_for_status()
        alert.status, alert.sent_at = "sent", datetime.now(UTC)
        return True
    except Exception as e:  # noqa: BLE001
        # httpx puts the full request URL — token included — in its message.
        detail = redact(str(e))[:500]
        log.warning("webhook failed: %s", detail)
        alert.status, alert.error = "failed", detail
        return False
