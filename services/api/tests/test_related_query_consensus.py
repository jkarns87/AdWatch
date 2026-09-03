"""Rising related-queries are a random sample, so one draw is not evidence.

Measured 2026-09-03, four back-to-back RELATED_QUERIES calls for "espresso machine"
with `no_cache=true` (four distinct search_ids, so genuinely fresh):

    draw       0    1    2    3
    rising     9   11   12    9
    breakout   2    1    0    2

    pairwise Jaccard 0.10 - 0.25
    23 unique queries: 1 in all four draws, 13 in exactly one
    the breakout flag was stable in 0 of 2 cases

`diff_related_queries` compares one draw from the previous run against one draw from
this run and emits `rising_query` for anything new, so most of what it emitted was
sampling noise rather than demand.

A first attempt at this measurement showed Jaccard 1.00 and looked like proof of
stability. It was measuring SerpApi's one-hour server-side cache: `fresh=True` only
bypassed our local disk cache and never sent `no_cache`, so all four calls replayed
one stored record. Consensus sampling is worthless without that flag, which is why
`test_fresh_forces_a_live_pull_rather_than_replaying_the_server_cache` exists.
"""

from app.collectors.normalize import consensus_rising
from app.collectors.serpapi_client import SerpApiClient


def _r(query: str, *, bucket: str = "rising", value_text: str = "+400%", value_num: float | None = 400.0) -> dict:
    return {"query": query, "bucket": bucket, "value_text": value_text, "value_num": value_num}


def test_a_query_seen_in_only_one_draw_is_dropped():
    """13 of 23 observed queries were single-draw artifacts."""
    draws = [[_r("stable one"), _r("noise a")], [_r("stable one"), _r("noise b")], [_r("stable one"), _r("noise c")]]
    out = consensus_rising(draws, min_draws=2)
    assert [r["query"] for r in out] == ["stable one"]


def test_a_query_in_two_of_three_draws_survives():
    draws = [[_r("real")], [_r("real")], [_r("other")]]
    assert {r["query"] for r in consensus_rising(draws, min_draws=2)} == {"real"}


def test_matching_is_case_insensitive_like_the_diff():
    """diff_related_queries lowercases before comparing; consensus must agree or a
    query could pass consensus under one casing and be re-alerted under another."""
    draws = [[_r("Espresso Machine")], [_r("espresso machine")], [_r("unrelated")]]
    assert len(consensus_rising(draws, min_draws=2)) == 1


def test_breakout_needs_consensus_too():
    """The breakout flag was the least stable field measured: 0 of 2 survived all
    four draws, and one draw reported no breakouts at all. A query flagged breakout
    once fires `rising_query` through the breakout branch regardless of its
    percentage, so the flag itself has to clear the threshold."""
    draws = [
        [_r("q", value_text="Breakout", value_num=None)],
        [_r("q", value_text="+250%", value_num=250.0)],
        [_r("q", value_text="+250%", value_num=250.0)],
    ]
    out = consensus_rising(draws, min_draws=2)
    assert len(out) == 1
    assert "breakout" not in out[0]["value_text"].lower()


def test_a_breakout_confirmed_by_a_majority_is_kept():
    draws = [
        [_r("q", value_text="Breakout", value_num=None)],
        [_r("q", value_text="Breakout", value_num=None)],
        [_r("q", value_text="+250%", value_num=250.0)],
    ]
    out = consensus_rising(draws, min_draws=2)
    assert out[0]["value_text"].lower() == "breakout"


def test_the_top_bucket_is_carried_through():
    """Only `rising` is unstable; `top` measured Jaccard 0.61-1.00 and is what the
    UI renders. Dropping it would empty the related-queries panel."""
    draws = [[_r("a", bucket="top", value_text="100", value_num=100.0)]] * 3
    assert [r["bucket"] for r in consensus_rising(draws, min_draws=2)] == ["top"]


def test_a_single_draw_is_returned_unchanged():
    """min_draws=1 keeps the old one-sample behaviour available for tests and for
    any caller that cannot afford three searches."""
    draws = [[_r("a"), _r("b")]]
    assert len(consensus_rising(draws, min_draws=1)) == 2


def test_no_draws_is_not_an_error():
    assert consensus_rising([], min_draws=2) == []


def test_fresh_forces_a_live_pull_rather_than_replaying_the_server_cache():
    """SerpApi serves an identical stored record for an hour on matching params, so
    without `no_cache` three "draws" are one draw repeated and consensus is
    circular. The docstring already promised fresh=True forces a live pull."""
    captured: dict = {}

    class _Capture(SerpApiClient):
        def __init__(self, cache_dir):
            self.api_key = "k"
            self.cache_dir = cache_dir
            self.timeout_s = 1.0
            self.searches_used = 0

        def _get(self, params):  # type: ignore[override]
            captured.update(params)
            return {}

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path

        c = _Capture(Path(d))
        c.search({"engine": "google_trends", "q": "x"}, fresh=True)
    assert str(captured.get("no_cache", "")).lower() == "true"


def test_a_normal_call_does_not_pay_to_bypass_the_server_cache():
    """SerpApi serves cached responses free, so `no_cache` must be opt-in — sending
    it unconditionally would bill every repeat we currently get for nothing."""
    captured: dict = {}

    class _Capture(SerpApiClient):
        def __init__(self, cache_dir):
            self.api_key = "k"
            self.cache_dir = cache_dir
            self.timeout_s = 1.0
            self.searches_used = 0

        def _get(self, params):  # type: ignore[override]
            captured.update(params)
            return {}

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        _Capture(Path(d)).search({"engine": "google_trends", "q": "x"}, fresh=False)
    assert "no_cache" not in captured


def test_every_consensus_draw_is_requested_fresh():
    """Consensus needs samples of one moment, not one sample plus history.

    The first draw was taken with the run's own `fresh` flag, which defaults to
    False, so it could be served from our local disk cache while the other two went
    live — observed in production logs as `serpapi cache hit google_trends-...`
    immediately before two `no_cache=true` fetches of the same term. Averaging an
    hours-old record with two fresh ones is not a majority vote, and the stale draw
    silently anchors the result.
    """
    from app.engine.collect import RELATED_QUERY_DRAWS, _related_query_draws

    calls: list[bool] = []

    class _Client:
        def trends_related_queries(self, *, q, geo, fresh=False):
            calls.append(fresh)

            class _R:
                data = {"related_queries": {"rising": [{"query": "a", "value": "+400%"}]}}

            return _R()

    first, draws = _related_query_draws(_Client(), q="x", geo="US")
    assert len(calls) == RELATED_QUERY_DRAWS
    assert all(calls), "a draw was served from cache; consensus over it is circular"
    assert len(draws) == RELATED_QUERY_DRAWS
    assert first is not None, "the snapshot still needs the first response"
