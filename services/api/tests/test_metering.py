"""The llm_calls ledger: one row per Claude call, cost frozen at write time.

Both Claude call sites must land here — analyst.py and reports/data.py — or the
usage page under-reports by exactly the feature most likely to be expensive.
"""

from dataclasses import dataclass

from sqlalchemy import select

from app import metering
from app import models as m


@dataclass
class FakeUsage:
    """Stands in for the Anthropic SDK's usage object, which is a plain data holder."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


def test_records_tokens_and_freezes_cost(db):
    metering.record_call(
        db,
        workspace_id=1,
        model="claude-sonnet-5",
        feature="analyst",
        usage=FakeUsage(input_tokens=1_000_000, output_tokens=100_000),
        watchlist_id=7,
        run_id=3,
    )
    row = db.scalars(select(m.LlmCall)).one()
    assert row.input_tokens == 1_000_000
    assert row.output_tokens == 100_000
    assert row.cost_usd == 3.00  # 1M in at $2 + 100k out at $10/1M
    assert row.feature == "analyst"
    assert row.watchlist_id == 7
    assert row.run_id == 3
    assert row.status == "ok"


def test_unknown_model_records_tokens_but_flags_unpriced(db):
    metering.record_call(
        db,
        workspace_id=1,
        model="claude-sonnet-4-5",
        feature="analyst",
        usage=FakeUsage(input_tokens=500_000),
    )
    row = db.scalars(select(m.LlmCall)).one()
    assert row.input_tokens == 500_000
    assert row.cost_usd == 0.0
    assert row.priced is False


def test_known_model_is_marked_priced(db):
    metering.record_call(db, workspace_id=1, model="claude-sonnet-5", feature="report", usage=FakeUsage(input_tokens=10))
    assert db.scalars(select(m.LlmCall)).one().priced is True


def test_cache_tokens_are_recorded(db):
    metering.record_call(
        db,
        workspace_id=1,
        model="claude-sonnet-5",
        feature="analyst",
        usage=FakeUsage(cache_read_input_tokens=1_000_000, cache_creation_input_tokens=1_000_000),
    )
    row = db.scalars(select(m.LlmCall)).one()
    assert row.cache_read_tokens == 1_000_000
    assert row.cache_write_tokens == 1_000_000
    assert row.cost_usd == 2.70  # 0.1x$2 read + 1.25x$2 write


def test_a_fallback_records_no_tokens_and_no_cost(db):
    """The analyst degrades to a deterministic fallback when the key is missing or
    the call fails. Claude never answered, so it must not show as Claude spend."""
    metering.record_call(db, workspace_id=1, model="fallback", feature="analyst", usage=None, status="fallback")
    row = db.scalars(select(m.LlmCall)).one()
    assert row.status == "fallback"
    assert row.input_tokens == 0
    assert row.cost_usd == 0.0


def test_usage_object_missing_cache_fields_does_not_explode(db):
    """Not every SDK version or response populates the cache counters."""

    class Bare:
        input_tokens = 100
        output_tokens = 5

    metering.record_call(db, workspace_id=1, model="claude-sonnet-5", feature="report", usage=Bare())
    row = db.scalars(select(m.LlmCall)).one()
    assert row.cache_read_tokens == 0
    assert row.cache_write_tokens == 0


def test_report_calls_carry_no_run_id(db):
    """reports/data.py calls Claude without producing an Insight or a Run — the
    reason this is a ledger table and not columns on Insight."""
    metering.record_call(db, workspace_id=1, model="claude-sonnet-5", feature="report", usage=FakeUsage(input_tokens=1), watchlist_id=4)
    row = db.scalars(select(m.LlmCall)).one()
    assert row.run_id is None
    assert row.watchlist_id == 4
