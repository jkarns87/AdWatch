"""The report path is the call site that columns-on-Insight would have missed: it calls
Claude without producing an Insight. If it doesn't reach the ledger, the usage page
under-reports by exactly the feature most likely to be expensive."""

import sys
from types import SimpleNamespace

from app.reports import data as report_data


class FakeMessage:
    content = [SimpleNamespace(text='{"headline":"h","paragraphs":[],"decisions":[]}')]
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=200_000,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )


def _report_data():
    """The minimum assembled payload executive_summary reads."""
    return {
        "audience": "marketing",
        "watchlist": {"name": "Coffee", "vertical": "specialty coffee", "geo": "US"},
        "period": {"days": 7},
        "kpis": {"runs_in_period": 2, "competitors": 3, "keywords": 5, "changes": 0, "high": 0, "medium": 0, "low": 0},
        "changes_by_kind": [],
        "changes": [],
        "insights": [],
        "actions": [],
        "competitors": [],
        "keywords": [],
    }


def _fake_anthropic_module():
    class Messages:
        @staticmethod
        def create(**kwargs):
            return FakeMessage()

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()

    return SimpleNamespace(Anthropic=Client)


def test_executive_summary_surfaces_usage_for_the_ledger(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic_module())
    monkeypatch.setattr(
        report_data, "get_settings", lambda: SimpleNamespace(anthropic_api_key="k", anthropic_model="claude-sonnet-5")
    )

    out = report_data.executive_summary(_report_data())

    assert out["model"] == "claude-sonnet-5"
    assert out["_usage"].input_tokens == 1_000_000


def test_fallback_summary_carries_no_usage(monkeypatch):
    """No key means no call. It must not appear as Claude spend."""
    monkeypatch.setattr(report_data, "get_settings", lambda: SimpleNamespace(anthropic_api_key="", anthropic_model="claude-sonnet-5"))
    out = report_data.executive_summary(_report_data())
    assert out.get("_usage") is None
