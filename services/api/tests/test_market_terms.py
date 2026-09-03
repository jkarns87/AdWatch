"""Per-watchlist market vocabulary — the drift guard, generalised.

in_market() stops a keyword scan wandering into an adjacent market: "espresso
machine" must not drag it into "machine learning". That fence existed only for five
hand-curated markets, so a watchlist created from onboarding had none at all.

Claude already reads the company's site; it can supply the terms, and vocabulary()
already turns terms into a matcher. Nothing new is invented.
"""

import sys
from types import SimpleNamespace

import pytest

from app import market
from app import models as m
from app.coffee.engine import in_market
from app.onboarding import analyze as ana


def test_terms_from_a_watchlist_build_a_working_fence():
    w = m.Watchlist(name="Mattresses", market_terms=["mattress", "bed frame", "memory foam"])
    pattern = market.for_watchlist(w)
    assert in_market("best memory foam mattress", pattern)
    assert not in_market("machine learning course", pattern)


def test_a_watchlist_without_terms_has_no_fence_rather_than_a_wrong_one():
    """None means "do not filter". Falling back to the coffee vocabulary would throw
    away every keyword for any company that does not sell coffee."""
    assert market.for_watchlist(m.Watchlist(name="X", market_terms=None)) is None
    assert market.for_watchlist(m.Watchlist(name="X", market_terms=[])) is None


def test_matching_is_case_insensitive_and_word_bounded():
    w = m.Watchlist(name="Tea", market_terms=["tea"])
    pattern = market.for_watchlist(w)
    assert in_market("Loose Leaf TEA", pattern)
    assert not in_market("steak", pattern), "word boundaries, or 'tea' matches inside 'steak'"


def test_junk_terms_are_dropped():
    w = m.Watchlist(name="X", market_terms=["  mattress ", "", None, 42, "a"])
    pattern = market.for_watchlist(w)
    assert in_market("mattress sale", pattern)
    # single characters would match almost anything
    assert not in_market("a quick brown fox", pattern)


def test_a_terms_list_is_bounded():
    w = m.Watchlist(name="X", market_terms=[f"term{i}" for i in range(500)])
    assert len(market.clean_terms(w.market_terms)) <= market.MAX_TERMS


# ---- the analysis has to actually supply them -------------------------------------


def _run(monkeypatch, payload):
    import json

    class Messages:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                usage=SimpleNamespace(input_tokens=1, output_tokens=1,
                                      cache_read_input_tokens=0, cache_creation_input_tokens=0),
            )

    class Client:
        def __init__(self, **kw):
            self.messages = Messages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=Client))
    return ana.analyze_company(name="Casper", domain="casper.com", description="mattresses",
                               api_key="k", model="claude-sonnet-5")


BASE = {"vertical_id": 71, "keywords": ["memory foam mattress"], "competitors": [], "assets": [], "site_read": True}


def test_the_analysis_returns_market_terms(monkeypatch):
    out = _run(monkeypatch, {**BASE, "market_terms": ["mattress", "bed frame"]})
    assert out["market_terms"] == ["mattress", "bed frame"]


def test_missing_market_terms_is_an_empty_list_not_a_crash(monkeypatch):
    out = _run(monkeypatch, BASE)
    assert out["market_terms"] == []


@pytest.mark.parametrize("bad", ["mattress", {"a": 1}, 42, None])
def test_market_terms_of_the_wrong_shape_are_ignored(monkeypatch, bad):
    out = _run(monkeypatch, {**BASE, "market_terms": bad})
    assert out["market_terms"] == []
