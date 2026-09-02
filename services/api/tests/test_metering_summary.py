"""The aggregate the usage page renders. Kept a pure function over rows so it can be
tested without standing up the router or a Postgres."""

from datetime import UTC

from app import metering


def _call(db, **kw):
    defaults = dict(workspace_id=1, model="claude-sonnet-5", feature="analyst", usage=None)
    defaults.update(kw)
    return metering.record_call(db, **defaults)


class Usage:
    def __init__(self, i=0, o=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


def test_empty_workspace_summarises_to_zero(db):
    s = metering.summarize(db, workspace_id=1)
    assert s["calls"] == 0
    assert s["cost_usd"] == 0.0
    assert s["unpriced_calls"] == 0
    assert s["by_feature"] == []


def test_totals_sum_across_calls(db):
    _call(db, usage=Usage(i=1_000_000))          # $2.00
    _call(db, usage=Usage(o=1_000_000))          # $10.00
    s = metering.summarize(db, workspace_id=1)
    assert s["calls"] == 2
    assert s["input_tokens"] == 1_000_000
    assert s["output_tokens"] == 1_000_000
    assert s["cost_usd"] == 12.00


def test_split_by_feature(db):
    _call(db, feature="analyst", usage=Usage(i=1_000_000))
    _call(db, feature="report", usage=Usage(i=500_000))
    s = metering.summarize(db, workspace_id=1)
    by = {r["feature"]: r for r in s["by_feature"]}
    assert by["analyst"]["calls"] == 1
    assert by["analyst"]["cost_usd"] == 2.00
    assert by["report"]["cost_usd"] == 1.00


def test_split_by_model(db):
    _call(db, model="claude-sonnet-5", usage=Usage(i=1_000_000))
    _call(db, model="claude-opus-5", usage=Usage(i=1_000_000))
    s = metering.summarize(db, workspace_id=1)
    by = {r["model"]: r["cost_usd"] for r in s["by_model"]}
    assert by["claude-sonnet-5"] == 2.00
    assert by["claude-opus-5"] == 5.00


def test_unpriced_calls_are_counted_separately(db):
    _call(db, model="claude-sonnet-4-5", usage=Usage(i=1_000_000))
    s = metering.summarize(db, workspace_id=1)
    assert s["unpriced_calls"] == 1
    assert s["cost_usd"] == 0.0, "an unpriced model must not silently contribute cost"


def test_other_workspaces_are_excluded(db):
    _call(db, workspace_id=1, usage=Usage(i=1_000_000))
    _call(db, workspace_id=2, usage=Usage(i=1_000_000))
    assert metering.summarize(db, workspace_id=1)["calls"] == 1


def test_cost_by_watchlist_attributes_spend(db):
    _call(db, watchlist_id=10, usage=Usage(i=1_000_000))
    _call(db, watchlist_id=10, usage=Usage(i=500_000))
    _call(db, watchlist_id=11, usage=Usage(i=500_000))
    got = metering.cost_by_watchlist(db, workspace_id=1)
    assert got[10] == 3.00
    assert got[11] == 1.00


def test_metering_since_is_the_first_recorded_call(db):
    """The usage page must state when metering began rather than implying the
    historical zero is real spend."""
    assert metering.summarize(db, workspace_id=1)["metering_since"] is None
    row = _call(db, usage=Usage(i=10))
    since = metering.summarize(db, workspace_id=1)["metering_since"]
    # SQLite has no timestamptz, so DateTime(timezone=True) round-trips naive here while
    # the in-session object keeps its aware value. Same instant; Postgres returns aware
    # and they compare equal directly. Assert the instant, not the tzinfo.
    assert since.replace(tzinfo=UTC) == row.created_at
