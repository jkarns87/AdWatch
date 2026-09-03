"""Snapshot retention.

snapshots is the only table with unbounded per-run growth. Measured on the live
database: 1256 kB total, five times the next table, with search_ads payloads at ~27 kB
per row against ~0.9 kB for ads_transparency. It grows linearly with runs x keywords,
forever.

The payload is also the replay asset, so this drops `raw` and KEEPS the row. The
metadata — what was fetched, when, which SerpApi search id, whether it came from cache —
is a few bytes and is the audit trail for a run. Deleting the row would lose the record
that the fetch happened at all.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import models as m
from app import retention
from app.db import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _watchlist_with_runs(db, *, wl_id: int, runs: int) -> list[m.Run]:
    db.add(m.Workspace(id=wl_id, name=f"ws{wl_id}"))
    db.flush()
    w = m.Watchlist(id=wl_id, workspace_id=wl_id, name=f"W{wl_id}", vertical="v", geo="US")
    db.add(w)
    db.flush()
    base = datetime(2026, 9, 1, tzinfo=UTC)
    out = []
    for i in range(runs):
        r = m.Run(watchlist_id=w.id, status="done", started_at=base + timedelta(days=i))
        db.add(r)
        db.flush()
        db.add(m.Snapshot(run_id=r.id, watchlist_id=w.id, kind="search_ads",
                          subject_type="keyword", subject_id=1,
                          serpapi_search_id=f"s{i}", raw={"big": "x" * 100}))
        out.append(r)
    db.flush()
    return out


def _with_raw(db, wl_id: int) -> int:
    rows = db.scalars(select(m.Snapshot).where(m.Snapshot.watchlist_id == wl_id)).all()
    return len([r for r in rows if r.raw is not None])


def test_recent_runs_keep_their_payload(db):
    _watchlist_with_runs(db, wl_id=1, runs=5)
    retention.prune_snapshots(db, keep_runs=3)
    assert _with_raw(db, 1) == 3


def test_the_rows_survive_even_when_the_payload_goes(db):
    """The metadata is the audit trail: what was fetched, when, which search id."""
    _watchlist_with_runs(db, wl_id=1, runs=5)
    retention.prune_snapshots(db, keep_runs=3)
    rows = db.scalars(select(m.Snapshot).where(m.Snapshot.watchlist_id == 1)).all()
    assert len(rows) == 5
    pruned = [r for r in rows if r.raw is None]
    assert all(r.serpapi_search_id for r in pruned), "the record of the fetch must remain"


def test_a_watchlist_with_fewer_runs_than_the_limit_is_untouched(db):
    _watchlist_with_runs(db, wl_id=1, runs=2)
    retention.prune_snapshots(db, keep_runs=10)
    assert _with_raw(db, 1) == 2


def test_retention_is_per_watchlist_not_global(db):
    """A busy watchlist must not prune a quiet one's only two runs."""
    _watchlist_with_runs(db, wl_id=1, runs=8)
    _watchlist_with_runs(db, wl_id=2, runs=2)
    retention.prune_snapshots(db, keep_runs=3)
    assert _with_raw(db, 1) == 3
    assert _with_raw(db, 2) == 2


def test_running_it_twice_changes_nothing_more(db):
    _watchlist_with_runs(db, wl_id=1, runs=5)
    first = retention.prune_snapshots(db, keep_runs=3)
    second = retention.prune_snapshots(db, keep_runs=3)
    assert first["snapshots_pruned"] == 2
    assert second["snapshots_pruned"] == 0, "idempotent, or a nightly job re-does its work forever"


def test_it_reports_what_it_did(db):
    _watchlist_with_runs(db, wl_id=1, runs=6)
    out = retention.prune_snapshots(db, keep_runs=2)
    assert out["snapshots_pruned"] == 4
    assert out["watchlists_examined"] == 1
    assert out["bytes_freed"] > 0, "a maintenance job nobody can measure gets turned off"


def test_keep_runs_must_be_at_least_two(db):
    """The diff engine compares run N to N-1. Keeping one would break replay of the
    comparison that produced the current changes."""
    _watchlist_with_runs(db, wl_id=1, runs=5)
    with pytest.raises(ValueError):
        retention.prune_snapshots(db, keep_runs=1)


def test_failed_runs_do_not_count_toward_the_kept_window(db):
    """A run that failed has no useful payload; letting it occupy a slot would evict a
    good one."""
    runs = _watchlist_with_runs(db, wl_id=1, runs=4)
    runs[-1].status = "failed"
    db.flush()
    retention.prune_snapshots(db, keep_runs=2)
    kept = {r.run_id for r in db.scalars(select(m.Snapshot).where(m.Snapshot.raw.is_not(None))).all()}
    assert runs[-1].id not in kept
    assert {runs[1].id, runs[2].id} == kept
