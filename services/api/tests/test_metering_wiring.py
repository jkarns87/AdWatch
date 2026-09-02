"""Both Claude call sites must write the ledger. Unit-testing pricing proves the maths;
these prove the maths is actually reached from the code paths that spend money."""

from dataclasses import dataclass
from types import SimpleNamespace

from sqlalchemy import select

from app import models as m
from app.engine import analyze as analyze_mod


@dataclass
class FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class StubAnalyst:
    """Returns one insight per call, carrying the usage a real response would."""

    def __init__(self, result):
        self._result = result

    def analyze(self, context, changes):
        return [([c["id"] for c in changes], self._result)]


def _watchlist_with_a_change(db):
    ws = m.Workspace(name="acme")
    db.add(ws)
    db.flush()
    w = m.Watchlist(workspace_id=ws.id, name="Coffee", vertical="specialty coffee", geo="US")
    db.add(w)
    db.flush()
    run = m.Run(watchlist_id=w.id, status="done", searches_used=4)
    db.add(run)
    db.flush()
    db.add(
        m.Change(
            watchlist_id=w.id,
            run_id=run.id,
            kind="creative_launched",
            severity="high",
            subject_type="competitor",
            subject_id=1,
            subject_label="Blue Bottle",
            payload={},
        )
    )
    db.flush()
    return w, run


def test_analyze_writes_one_ledger_row_per_claude_call(db, monkeypatch):
    monkeypatch.setattr(analyze_mod, "get_settings", lambda: SimpleNamespace(alert_dispatcher="none"))
    w, run = _watchlist_with_a_change(db)
    analyst = StubAnalyst(
        {
            "summary": "s",
            "why_it_matters": "w",
            "recommended_actions": [],
            "confidence": 0.5,
            "model": "claude-sonnet-5",
            "_usage": FakeUsage(input_tokens=1_000_000, output_tokens=100_000),
        }
    )

    analyze_mod.run_analyze(db, w, analyst=analyst)

    row = db.scalars(select(m.LlmCall)).one()
    assert row.feature == "analyst"
    assert row.model == "claude-sonnet-5"
    assert row.workspace_id == w.workspace_id
    assert row.watchlist_id == w.id
    assert row.run_id == run.id
    assert row.cost_usd == 3.00
    assert row.status == "ok"


def test_a_fallback_insight_is_recorded_but_costs_nothing(db, monkeypatch):
    """The analyst degrades to a deterministic fallback when Claude is unavailable.
    That must appear in the ledger as status=fallback, not as Claude spend."""
    monkeypatch.setattr(analyze_mod, "get_settings", lambda: SimpleNamespace(alert_dispatcher="none"))
    w, _ = _watchlist_with_a_change(db)
    analyst = StubAnalyst(
        {"summary": "s", "why_it_matters": "", "recommended_actions": [], "confidence": 0.0, "model": "fallback"}
    )

    analyze_mod.run_analyze(db, w, analyst=analyst)

    row = db.scalars(select(m.LlmCall)).one()
    assert row.status == "fallback"
    assert row.cost_usd == 0.0
    assert row.input_tokens == 0


def test_the_usage_marker_never_leaks_into_the_stored_insight(db, monkeypatch):
    """_usage is transport between the analyst and the ledger. It must not end up in
    recommended_actions or any other persisted insight field."""
    monkeypatch.setattr(analyze_mod, "get_settings", lambda: SimpleNamespace(alert_dispatcher="none"))
    w, _ = _watchlist_with_a_change(db)
    analyst = StubAnalyst(
        {
            "summary": "s",
            "why_it_matters": "w",
            "recommended_actions": [{"action": "a", "rationale": "r", "effort": "low", "urgency": "now"}],
            "confidence": 0.5,
            "model": "claude-sonnet-5",
            "_usage": FakeUsage(input_tokens=10),
        }
    )

    analyze_mod.run_analyze(db, w, analyst=analyst)

    ins = db.scalars(select(m.Insight)).one()
    assert "_usage" not in str(ins.recommended_actions)
    assert ins.model == "claude-sonnet-5"
