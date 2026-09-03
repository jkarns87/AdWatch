"""Snapshot retention.

`snapshots` is the only table with unbounded per-run growth. Measured on the live
database: 1256 kB, five times the next table, with Google Search payloads at roughly
27 kB per row against 0.9 kB for ads_transparency. It grows with runs x keywords,
forever, and nothing pruned it.

What this does NOT do is delete the row. `raw` is the bulk; the rest of a Snapshot —
kind, subject, fetched_at, serpapi_search_id, from_cache — is a few bytes and is the
audit trail proving a fetch happened and what it cost. Dropping the payload while
keeping the record reclaims almost all of the space and loses almost none of the value.

Retention is per watchlist and counted in *runs*, not days: a watchlist collected daily
and one collected monthly should both keep the same number of comparable snapshots.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m

log = logging.getLogger(__name__)

# collect_all_watchlists runs every 6 hours, so 20 runs is about five days of payloads —
# a working week's debugging window. Counted in runs rather than days so a watchlist
# collected on a slower cadence keeps the same number of comparable snapshots.
DEFAULT_KEEP_RUNS = 20
MIN_KEEP_RUNS = 2


def prune_snapshots(db: Session, *, keep_runs: int = DEFAULT_KEEP_RUNS) -> dict[str, Any]:
    """Drop `raw` for all but the most recent `keep_runs` successful runs per watchlist.

    Idempotent: rows already pruned are skipped, so a nightly job does not re-do its own
    work and report phantom savings.
    """
    if keep_runs < MIN_KEEP_RUNS:
        # The diff engine compares run N to N-1; keeping one would make the comparison
        # that produced the current changes unreplayable.
        raise ValueError(f"keep_runs must be at least {MIN_KEEP_RUNS}, got {keep_runs}")

    watchlist_ids = db.scalars(select(m.Watchlist.id)).all()
    pruned = 0
    freed = 0

    for wl_id in watchlist_ids:
        # Failed runs hold no useful payload; letting one occupy a slot would evict a
        # good run from the window.
        keep_ids = db.scalars(
            select(m.Run.id)
            .where(m.Run.watchlist_id == wl_id, m.Run.status == "done")
            .order_by(m.Run.id.desc())
            .limit(keep_runs)
        ).all()

        stale = db.scalars(
            select(m.Snapshot).where(
                m.Snapshot.watchlist_id == wl_id,
                m.Snapshot.raw.is_not(None),
                m.Snapshot.run_id.notin_(keep_ids) if keep_ids else True,
            )
        ).all()

        for snap in stale:
            # Approximate: enough to tell whether the job is worth running, which is all
            # a size figure needs to do.
            freed += len(str(snap.raw))
            snap.raw = None
            pruned += 1

    db.commit()
    log.info("snapshot retention: pruned %d payloads across %d watchlists", pruned, len(watchlist_ids))
    return {
        "watchlists_examined": len(watchlist_ids),
        "keep_runs": keep_runs,
        "snapshots_pruned": pruned,
        "bytes_freed": freed,
    }


def snapshot_footprint(db: Session) -> dict[str, Any]:
    """What the table currently costs, so the decision to prune is informed rather than
    a guess."""
    total, with_raw = db.execute(
        select(func.count(m.Snapshot.id), func.count(m.Snapshot.raw))
    ).one()
    by_kind = [
        {"kind": k, "rows": n}
        for k, n in db.execute(
            select(m.Snapshot.kind, func.count(m.Snapshot.id)).group_by(m.Snapshot.kind)
        ).all()
    ]
    return {"snapshots": int(total or 0), "with_payload": int(with_raw or 0), "by_kind": by_kind}
