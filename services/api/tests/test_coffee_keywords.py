"""Coffee keyword discovery. A stub client stands in for SerpApi — no network, no quota."""

from urllib.parse import quote

import pytest

from app.coffee import engine as ck
from app.collectors.serpapi_client import SerpApiError, SerpResult

LANDING = "https://drinktrade.example/trial?utm_source=google&utm_medium=cpc&utm_term=coffee subscription&matchtype=e"

AD = {
    "position": 1,
    "block_position": "top",
    "title": "Trade Coffee — Roasted To Order",
    "description": "Coffee subscription from top roasters. Cold brew too.",
    "displayed_link": "http://www.drinktrade.example",
    "link": "https://www.google.com/goto?url=CAESaAHrOzAV",
    "tracking_link": "https://www.google.com/aclk?sa=L&ai=DChs&adurl=" + quote(LANDING, safe=""),
}
BARE_AD = {  # this advertiser strips the macro: an advertiser, but no keyword
    "position": 2,
    "block_position": "top",
    "title": "Atlas Coffee Club",
    "description": "Coffee of the month club.",
    "displayed_link": "https://www.atlascoffeeclub.example",
}


class StubClient:
    """Canned SerpApi responses, through the same `search(params)` the real client exposes."""

    def __init__(self, ads_by_query=None, suggestions=(), fail=()):
        self.ads_by_query = ads_by_query or {}
        self.suggestions = list(suggestions)
        self.fail = dict(fail)
        self.queried: list[str] = []
        self.locations: list[str] = []
        self.searches_used = 0

    def search(self, params, *, fresh=False):
        q = params["q"]
        if params["engine"] == "google_autocomplete":
            self.searches_used += 1
            return SerpResult({"suggestions": self.suggestions}, from_cache=False)
        if q in self.fail:
            raise self.fail[q]
        assert params.get("location"), "google_ads rejects a request with no location"
        self.locations.append(params["location"])
        self.queried.append(q)
        self.searches_used += 1
        return SerpResult({"ads": self.ads_by_query.get(q, []), "related_searches": []}, from_cache=False)


# ---- scope ---------------------------------------------------------------------------------


def test_the_coffee_market_is_recognised_broadly():
    for q in ("coffee nearby", "ESPRESSO machine", "cold brew delivery", "k-cups", "nespresso pods", "best cafe near me"):
        assert ck.is_coffee(q), q


def test_neighbouring_markets_are_not_coffee():
    for q in ("running shoes", "tea subscription", "brewery tours", "black beans", "machine learning"):
        assert not ck.is_coffee(q), q


def test_an_off_market_seed_is_rejected_before_a_search_is_spent():
    client = StubClient()
    with pytest.raises(ValueError, match="coffee"):
        ck.discover(client, "running shoes")
    assert client.searches_used == 0


def test_an_empty_seed_is_rejected():
    with pytest.raises(ValueError):
        ck.discover(StubClient(), "a")


# ---- expansion -----------------------------------------------------------------------------


def test_head_term_strips_local_and_question_framing():
    assert ck.head_term("coffee nearby") == "coffee"
    assert ck.head_term("what is the best coffee subscription") == "best coffee subscription"


def test_the_ladder_does_not_repeat_a_word_the_seed_already_has():
    assert "best best coffee" not in ck.commercial_ladder("best coffee")
    assert "buy best coffee online" in ck.commercial_ladder("best coffee")


def test_expansion_stays_inside_the_coffee_market():
    client = StubClient(suggestions=[{"value": "coffee machine deals", "relevance": 900}, {"value": "machine learning", "relevance": 800}])
    queries, _, _ = ck.plan_queries(client, "coffee machine", depth=4)
    assert "coffee machine deals" in queries
    assert "machine learning" not in queries


def test_depth_zero_scans_only_the_seed():
    queries, _, reserve = ck.plan_queries(StubClient(), "coffee", depth=0)
    assert queries == ["coffee"]
    assert reserve  # still available if the seed turns out to have no advertisers


# ---- recovery ------------------------------------------------------------------------------


def test_recovers_the_keyword_and_match_type_from_the_click_url():
    assert ck.targeting_from_ad(AD) == (["coffee subscription"], ["exact"])


def test_an_ad_that_strips_the_macro_exposes_nothing():
    assert ck.targeting_from_ad(BARE_AD) == ([], [])


def test_google_ids_and_unexpanded_macros_are_not_keywords():
    for junk in ("{keyword}", "kwd-12345678", "1234", "e"):
        assert ck.clean_keyword(junk) is None
    assert ck.clean_keyword("Coffee%20Subscription") == "coffee subscription"


def test_advertiser_falls_back_through_googles_redirector():
    assert ck.advertiser_of(AD) == "drinktrade.example"
    assert ck.advertiser_of(dict(AD, displayed_link=None)) == "drinktrade.example"


def test_a_breadcrumb_display_link_is_one_advertiser_not_two():
    # Google renders these as "vervecoffee.com › coffee-beans"; both forms are one advertiser.
    bare = {"displayed_link": "https://www.vervecoffee.com"}
    crumb = {"displayed_link": "vervecoffee.com › coffee-beans"}
    assert ck.advertiser_of(bare) == ck.advertiser_of(crumb) == "vervecoffee.com"

    report = ck.discover(StubClient({"coffee beans": [dict(AD, **bare), dict(AD, **crumb)]}), "coffee beans", depth=0)
    assert report["summary"]["advertisers"] == 1


def test_copy_phrases_stay_on_topic_and_do_not_cross_a_sentence():
    got = ck.copy_phrases({"title": "Cold brew coffee delivered", "description": "Free shipping. Buy coffee online or pick up in store."}, {"coffee"})
    assert "cold brew coffee" in got
    assert "free shipping" not in got
    assert "coffee online or pick" not in got


# ---- scoring -------------------------------------------------------------------------------


def test_the_published_formula_reproduces_every_score():
    report = ck.discover(StubClient({"coffee subscription": [AD, BARE_AD]}), "coffee subscription", depth=0)
    w = report["scoring"]["weights"]
    for row in report["keywords"]:
        sig = row["signals"]
        raw = (
            w["targeting_keyword_advertisers"] * sig["targeting_keyword_advertisers"]
            + w["sponsored_query_advertisers"] * sig["sponsored_query_advertisers"]
            + w["ad_copy_advertisers"] * sig["ad_copy_advertisers"]
            + w["autocomplete_relevance_share"] * (sig["autocomplete_relevance_share"] or 0)
            + w["related_search"] * (1 if sig["related_search"] else 0)
        )
        assert row["score"] == round(min(100.0, 100 * raw / report["scoring"]["reference"]), 1)


def test_a_recovered_keyword_outranks_an_autocomplete_suggestion():
    client = StubClient({"coffee subscription": [AD, BARE_AD]}, suggestions=[{"value": "coffee subscription reviews", "relevance": 900}])
    report = ck.discover(client, "coffee subscription", depth=1)
    top = report["keywords"][0]
    assert top["keyword"] == "coffee subscription"
    assert top["evidence"] == "targeting_keyword" and top["recovered_from_ad"] is True
    assert top["match_types"] == ["exact"]
    suggested = next(k for k in report["keywords"] if k["keyword"] == "coffee subscription reviews")
    assert suggested["evidence"] == "autocomplete" and suggested["score"] < top["score"]


def test_coverage_is_reported_not_assumed():
    report = ck.discover(StubClient({"coffee subscription": [AD, BARE_AD]}), "coffee subscription", depth=0)
    s = report["summary"]
    assert s["ads_seen"] == 2 and s["ads_exposing_a_keyword"] == 1 and s["advertisers"] == 2
    assert s["confidence"] == "high"


def test_off_market_keywords_never_reach_the_report():
    ad = dict(AD, description="Coffee subscription boxes and gift boxes.")
    report = ck.discover(StubClient({"coffee subscription": [ad, dict(ad, displayed_link="https://beanbox.example")]}), "coffee subscription", depth=0)
    assert all(ck.is_coffee(k["keyword"]) for k in report["keywords"])
    assert "subscription boxes" not in [k["keyword"] for k in report["keywords"]]


# ---- the scan ------------------------------------------------------------------------------


def test_a_seed_with_no_advertisers_escalates_up_the_commercial_ladder():
    # Nobody buys clicks on "coffee nearby", but "best coffee" is a real market.
    client = StubClient({"best coffee": [AD]}, suggestions=[{"value": "coffee nearby open now", "relevance": 600}])
    report = ck.discover(client, "coffee nearby", depth=1)
    assert "best coffee" in report["summary"]["escalated_to"] or "best coffee" in client.queried
    assert report["summary"]["confidence"] == "high"


def test_a_seed_that_sells_does_not_escalate():
    ads = [AD, dict(AD, displayed_link="https://beanbox.example"), dict(AD, displayed_link="https://peets.example")]
    report = ck.discover(StubClient({"coffee subscription": ads}), "coffee subscription", depth=0)
    assert report["summary"]["escalated_to"] == [] and report["summary"]["advertisers"] == 3


def test_every_query_failing_is_an_error_not_an_empty_report():
    client = StubClient(fail={"coffee": SerpApiError("SerpApi 500: boom")})
    with pytest.raises(SerpApiError, match="every query failed"):
        ck.discover(client, "coffee", depth=0)


def test_a_query_with_no_paid_block_is_still_a_valid_report():
    # No ads is real data: plenty of coffee queries carry no sponsored results.
    report = ck.discover(StubClient({}), "coffee subscription", depth=0)
    assert report["summary"]["ads_seen"] == 0 and report["summary"]["confidence"] == "low"
    assert report["warnings"] == []


def test_one_failing_query_is_a_warning_but_a_bad_key_fails_the_request():
    client = StubClient({"coffee": [AD]}, fail={"best coffee": SerpApiError("SerpApi 500: boom")})
    report = ck.discover(client, "coffee", depth=2)
    assert "best coffee" in [w["query"] for w in report["warnings"]]
    assert report["keywords"]

    dead = StubClient(fail={"coffee": SerpApiError("SerpApi 401: bad key")})
    with pytest.raises(SerpApiError):
        ck.discover(dead, "coffee", depth=0)


def test_a_scan_always_names_a_market():
    # engine=google_ads 400s without one, and ads are local.
    client = StubClient({"coffee subscription": [AD]})
    ck.discover(client, "coffee subscription", depth=0)
    assert client.locations == [ck.DEFAULT_LOCATION]

    client = StubClient({"coffee subscription": [AD]})
    ck.discover(client, "coffee subscription", depth=0, location="San Francisco, California, United States")
    assert client.locations == ["San Francisco, California, United States"]


def test_searches_used_is_reported():
    client = StubClient({"coffee subscription": [AD]})
    report = ck.discover(client, "coffee subscription", depth=2)
    assert report["searches_used"] == client.searches_used > 0
