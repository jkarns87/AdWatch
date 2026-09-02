"""Writes the llm_calls ledger.

Deliberately not a method on Analyst: that class is pure and testable, and threading a
Session through it would couple the engine to the database for no gain. Call sites hand
this their own session and the ids they already hold.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import pricing

log = logging.getLogger(__name__)


def _tokens(usage: Any) -> tuple[int, int, int, int]:
    """Read the four counters off an Anthropic usage object. Not every SDK version or
    response populates the cache fields, so each is optional."""
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
        getattr(usage, "cache_read_input_tokens", 0) or 0,
        getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )


def record_call(
    db: Session,
    *,
    workspace_id: int,
    model: str,
    feature: str,
    usage: Any = None,
    watchlist_id: int | None = None,
    run_id: int | None = None,
    status: str = "ok",
) -> m.LlmCall:
    """Persist one Claude call. `usage` is the SDK's usage object, or None when no call
    reached the model (fallback or pre-flight failure)."""
    inp, out, cache_read, cache_write = _tokens(usage) if usage is not None else (0, 0, 0, 0)
    total = inp + out + cache_read + cache_write

    cost = pricing.cost_usd(
        model,
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )
    # No tokens means nothing to price — that is not a pricing failure, so it must not
    # inflate the unpriced count the dashboard surfaces.
    priced = cost is not None or total == 0
    if cost is None and total:
        log.warning("no published rate for model %r — %d tokens recorded unpriced", model, total)

    row = m.LlmCall(
        workspace_id=workspace_id,
        watchlist_id=watchlist_id,
        run_id=run_id,
        feature=feature,
        model=model,
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        cost_usd=cost or 0.0,
        priced=priced,
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def _scope(workspace_id: int, since: datetime | None):
    where = [m.LlmCall.workspace_id == workspace_id]
    if since is not None:
        where.append(m.LlmCall.created_at >= since)
    return where


def summarize(db: Session, *, workspace_id: int, since: datetime | None = None) -> dict[str, Any]:
    """Aggregate Claude spend for one workspace, in the shape the usage page renders."""
    where = _scope(workspace_id, since)

    totals = db.execute(
        select(
            func.count(m.LlmCall.id),
            func.coalesce(func.sum(m.LlmCall.input_tokens), 0),
            func.coalesce(func.sum(m.LlmCall.output_tokens), 0),
            func.coalesce(func.sum(m.LlmCall.cache_read_tokens), 0),
            func.coalesce(func.sum(m.LlmCall.cache_write_tokens), 0),
            func.coalesce(func.sum(m.LlmCall.cost_usd), 0.0),
            func.min(m.LlmCall.created_at),
        ).where(*where)
    ).one()
    calls, inp, out, cread, cwrite, cost, first_at = totals

    unpriced = db.scalar(select(func.count(m.LlmCall.id)).where(*where, m.LlmCall.priced.is_(False))) or 0

    by_feature = [
        {"feature": f, "calls": n, "cost_usd": round(c or 0.0, 6)}
        for f, n, c in db.execute(
            select(m.LlmCall.feature, func.count(m.LlmCall.id), func.sum(m.LlmCall.cost_usd))
            .where(*where)
            .group_by(m.LlmCall.feature)
            .order_by(m.LlmCall.feature)
        ).all()
    ]
    by_model = [
        {"model": mo, "calls": n, "cost_usd": round(c or 0.0, 6)}
        for mo, n, c in db.execute(
            select(m.LlmCall.model, func.count(m.LlmCall.id), func.sum(m.LlmCall.cost_usd))
            .where(*where)
            .group_by(m.LlmCall.model)
            .order_by(m.LlmCall.model)
        ).all()
    ]

    return {
        "calls": int(calls or 0),
        "cost_usd": round(float(cost or 0.0), 6),
        "unpriced_calls": int(unpriced),
        "input_tokens": int(inp or 0),
        "output_tokens": int(out or 0),
        "cache_read_tokens": int(cread or 0),
        "cache_write_tokens": int(cwrite or 0),
        "by_feature": by_feature,
        "by_model": by_model,
        # Existing insights predate the ledger. State when metering began rather than
        # letting a historical zero read as "we spent nothing".
        "metering_since": first_at,
    }


def cost_by_watchlist(db: Session, *, workspace_id: int, since: datetime | None = None) -> dict[int, float]:
    """Claude spend per watchlist, so the usage table becomes true cost per watchlist."""
    rows = db.execute(
        select(m.LlmCall.watchlist_id, func.sum(m.LlmCall.cost_usd))
        .where(*_scope(workspace_id, since), m.LlmCall.watchlist_id.is_not(None))
        .group_by(m.LlmCall.watchlist_id)
    ).all()
    return {int(wid): round(float(c or 0.0), 6) for wid, c in rows}
