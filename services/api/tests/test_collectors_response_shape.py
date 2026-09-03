"""The collectors, tested against SerpApi's ACTUAL response shape.

There was no test on the normalizers, which is how two silent collectors shipped:

  1. `creatives_from_ads_transparency` looked for `id` / `creative_id`. SerpApi
     returns `ad_creative_id`. Every creative failed the `if not cid: continue`
     guard, so a 40-creative response normalized to an empty list.

  2. `search_google` used `engine=google`, whose `ads` array is empty on
     commercial queries. Measured 2026-09-03: `google` returned 0 ads on 6 of 6
     high-intent queries where `google_ads` returned 2-6, same query, same
     location, same minute. AdWatch is a paid-search product and was reading the
     engine that omits the paid block.

Both failed the way the analyst `temperature` bug failed: no exception, no failing
assertion, an empty list flowing downstream into a diff that found nothing to
report. A run "succeeded" every time.

The fixtures are real responses captured from the live API and redacted, so these
tests pin the shape SerpApi actually sends. A hand-written fixture using the field
names we *expected* would have passed throughout.
"""

import json
from pathlib import Path
from typing import Any

from app.collectors.normalize import creatives_from_ads_transparency, domain_of, serp_ads_from_google
from app.collectors.serpapi_client import SerpApiClient

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ---- Ads Transparency Center ------------------------------------------------------------------


def test_creatives_are_extracted_from_a_real_response():
    """The bug: 40 creatives in, 0 out. Nothing raised, nothing logged."""
    raw = _load("serpapi_ads_transparency.json")
    assert raw["ad_creatives"], "fixture is empty; recapture it"
    out = creatives_from_ads_transparency(raw)
    assert len(out) == len(raw["ad_creatives"])


def test_the_creative_id_comes_from_the_field_serpapi_actually_sends():
    raw = _load("serpapi_ads_transparency.json")
    out = creatives_from_ads_transparency(raw)
    expected = {str(c["ad_creative_id"]) for c in raw["ad_creatives"]}
    assert {c["creative_id"] for c in out} == expected


def test_creative_ids_are_unique_so_the_diff_can_key_on_them():
    """diff_creatives builds {creative_id: creative}. Collisions would silently
    drop creatives and fabricate launched/dropped events."""
    out = creatives_from_ads_transparency(_load("serpapi_ads_transparency.json"))
    ids = [c["creative_id"] for c in out]
    assert ids, "no creatives — this assertion would otherwise pass vacuously"
    assert len(ids) == len(set(ids))
    assert all(ids), "a falsy creative_id would be dropped by the guard"


def test_advertiser_and_dates_survive_normalization():
    out = creatives_from_ads_transparency(_load("serpapi_ads_transparency.json"))
    assert all(c["advertiser_id"] for c in out)
    assert any(c["first_shown"] for c in out)
    assert any(c["last_shown"] for c in out)


# ---- Google paid block ------------------------------------------------------------------------


def test_serp_ads_are_extracted_from_a_real_paid_block():
    raw = _load("serpapi_google_ads.json")
    assert raw["ads"], "fixture is empty; recapture it"
    out = serp_ads_from_google(raw)
    assert len(out) == len(raw["ads"])


def test_the_bottom_block_is_preserved_rather_than_defaulted_to_top():
    """`block` defaults to "top" when block_position is missing. The engine we now
    use populates it, and a bottom-of-page ad recorded as top-of-page would
    misreport position in the share-of-voice view."""
    out = serp_ads_from_google(_load("serpapi_google_ads.json"))
    assert {a["block"] for a in out} == {"top", "bottom"}


def test_the_advertiser_domain_is_not_the_redirect_host():
    """Every `link` is now a google.com/goto redirect, so resolving the advertiser
    from it yields "google.com" for every ad on the page. displayed_link is the
    only field that names the advertiser."""
    out = serp_ads_from_google(_load("serpapi_google_ads.json"))
    domains = {a["advertiser_domain"] for a in out}
    assert "google.com" not in domains
    assert len(domains) > 1, "all ads resolved to one domain — the redirect leaked through"


def test_a_breadcrumb_displayed_link_still_resolves_to_a_bare_domain():
    """Google renders displayed_link as a breadcrumb: "https://www.foodandwine.com ›
    sep-reviews › espresso-makers". urlparse has no "/" to terminate the netloc, so
    the whole breadcrumb became the domain.

    advertiser_domain is the diff key for SERP ads, so an advertiser whose breadcrumb
    changed between runs read as a different advertiser — one false `new_advertiser`
    and one false `advertiser_disappeared` per run, for the same company."""
    assert domain_of("https://www.foodandwine.com › sep-reviews › espresso-makers") == "foodandwine.com"
    assert domain_of("www.nespresso.com › coffee") == "nespresso.com"


def test_every_ad_in_a_real_block_resolves_to_a_registrable_domain():
    out = serp_ads_from_google(_load("serpapi_google_ads.json"))
    for a in out:
        d = a["advertiser_domain"]
        assert d and " " not in d and "›" not in d, f"not a domain: {d!r}"
        assert "/" not in d


# ---- which engine the client asks for ----------------------------------------------------------


class _Capture(SerpApiClient):
    """Records the params that would go to SerpApi without spending a search."""

    def __init__(self):
        self.params: dict[str, Any] = {}

    def search(self, params, *, fresh: bool = False):  # type: ignore[override]
        self.params = dict(params)
        return None


def test_the_keyword_collector_asks_for_the_engine_that_returns_the_paid_block():
    """`engine=google` omits the paid block on commercial queries. Measured
    2026-09-03 with an identical query, location and minute: `google` returned 0
    ads on all 6 of crm software / car insurance quotes / espresso machine /
    meal kit delivery / running shoes / project management software, while
    `google_ads` returned 2-6 on every one. Both cost one search."""
    c = _Capture()
    c.google_search(q="espresso machine", location="Austin, Texas, United States")
    assert c.params["engine"] == "google_ads"


def test_the_keyword_collector_always_sends_a_location():
    """Without `location` the paid block comes back empty even on the right
    engine — Google will not serve ads to an unlocated request. A keyword
    collected with no location silently yields no competitors."""
    c = _Capture()
    c.google_search(q="espresso machine")
    assert c.params.get("location"), "no location — the paid block will be empty"
