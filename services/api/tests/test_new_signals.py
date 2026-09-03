"""Signals that were already in responses we pay for, and were being discarded.

Live probing on 2026-09-03 found three of these riding free on the `google_ads` call
the keyword collector already makes:

  * `ads[].sitelinks`   - present on 3 of 4 ads; the richest creative signal available,
                          and the only place ad extensions surface.
  * `ads[].source`      - the advertiser's display name ("Nespresso(R)", "MerakiTech"),
                          distinct from the domain and useful for attribution.
  * `immersive_products` - 24-49 product listings per commercial query, 100% coverage
                          on merchant / title / price / rating / reviews.

and one on the Ads Transparency call:

  * `ad_creatives[].total_days_shown` - present on 100% of creatives, never read.

The diff also never compared ad copy, even though title and description were already
stored on every row, so a competitor rewriting their headline produced no event at all.

Product events are deliberately price-only. Measured: prices are stable enough that
repeated identical queries showed zero spurious changes, but the *set* of products
churns between draws, so presence and absence would fire constantly. Emitting only
what was measured to be stable is the difference between a signal and a rumour.
"""

from app.collectors.normalize import creatives_from_ads_transparency, products_from_google, serp_ads_from_google
from app.engine import diff

# ---- capturing the fields ---------------------------------------------------------------------


def test_sitelink_titles_are_captured():
    raw = {"ads": [{"position": 1, "block_position": "top", "title": "t", "displayed_link": "https://www.a.com",
                    "sitelinks": [{"title": "Find Your Machine", "link": "https://www.google.com/goto?url=AAA"},
                                  {"title": "Shop Deals", "link": "https://www.google.com/goto?url=BBB"}]}]}
    out = serp_ads_from_google(raw)
    assert out[0]["sitelinks"] == ["Find Your Machine", "Shop Deals"]


def test_sitelink_redirect_urls_are_not_stored():
    """The links are google.com/goto redirects that change between identical calls.
    Storing them would churn the diff without adding information."""
    raw = {"ads": [{"position": 1, "displayed_link": "https://www.a.com",
                    "sitelinks": [{"title": "Shop", "link": "https://www.google.com/goto?url=ZZZ"}]}]}
    assert "goto" not in repr(serp_ads_from_google(raw)[0]["sitelinks"])


def test_an_ad_without_sitelinks_gets_an_empty_list_not_none():
    """1 of 4 observed ads had `sitelinks: null`. An empty list keeps the diff's set
    comparison total instead of special-casing None."""
    raw = {"ads": [{"position": 1, "displayed_link": "https://www.a.com", "sitelinks": None}]}
    assert serp_ads_from_google(raw)[0]["sitelinks"] == []


def test_the_advertiser_display_name_is_captured():
    raw = {"ads": [{"position": 1, "displayed_link": "https://www.a.com", "source": "Nespresso®"}]}
    assert serp_ads_from_google(raw)[0]["source"] == "Nespresso®"


def test_total_days_shown_is_captured():
    raw = {"ad_creatives": [{"ad_creative_id": "CR1", "format": "text", "total_days_shown": 490}]}
    assert creatives_from_ads_transparency(raw)[0]["total_days_shown"] == 490


# ---- products ---------------------------------------------------------------------------------


def test_products_are_extracted_with_merchant_and_price():
    raw = {"immersive_products": [
        {"source": "Target", "title": "Barista Express", "price": "$699.99", "extracted_price": 699.99,
         "rating": 4.6, "reviews": 12000},
    ]}
    p = products_from_google(raw)[0]
    assert p["merchant"] == "Target"
    assert p["title"] == "Barista Express"
    assert p["price"] == 699.99


def test_a_product_on_sale_records_its_original_price():
    raw = {"immersive_products": [
        {"source": "M", "title": "T", "extracted_price": 80.0, "extracted_original_price": 100.0,
         "extensions": ["20% OFF"]},
    ]}
    p = products_from_google(raw)[0]
    assert p["original_price"] == 100.0
    assert p["promo"] == "20% OFF"


def test_a_product_without_a_price_is_skipped():
    """Price is the entire point of the row; a listing without one cannot be diffed."""
    raw = {"immersive_products": [{"source": "M", "title": "T"}]}
    assert products_from_google(raw) == []


# ---- ad copy diff -----------------------------------------------------------------------------


def _ad(domain: str, *, title: str = "T", desc: str = "D", sitelinks=None, position: int = 1):
    return {"advertiser_domain": domain, "title": title, "description": desc,
            "sitelinks": sitelinks if sitelinks is not None else [], "position": position, "block": "top"}


def test_a_rewritten_headline_is_reported():
    out = diff.diff_serp_ads([_ad("a.com", title="Old")], [_ad("a.com", title="New")], keyword_id=1, label="k")
    kinds = {c["kind"] for c in out}
    assert "ad_copy_changed" in kinds
    c = next(c for c in out if c["kind"] == "ad_copy_changed")
    assert c["payload"]["from_title"] == "Old"
    assert c["payload"]["to_title"] == "New"


def test_a_rewritten_description_is_reported():
    out = diff.diff_serp_ads([_ad("a.com", desc="Old")], [_ad("a.com", desc="New")], keyword_id=1, label="k")
    assert "ad_copy_changed" in {c["kind"] for c in out}


def test_unchanged_copy_reports_nothing():
    assert diff.diff_serp_ads([_ad("a.com")], [_ad("a.com")], keyword_id=1, label="k") == []


def test_copy_is_not_reported_for_an_advertiser_that_just_arrived():
    """A new advertiser already gets new_serp_advertiser. Reporting its copy as
    "changed" as well would double-count one event."""
    out = diff.diff_serp_ads([_ad("a.com")], [_ad("a.com"), _ad("b.com", title="X")], keyword_id=1, label="k")
    assert [c["kind"] for c in out] == ["new_serp_advertiser"]


# ---- sitelink diff ----------------------------------------------------------------------------


def test_a_changed_sitelink_set_is_reported():
    out = diff.diff_serp_ads(
        [_ad("a.com", sitelinks=["Pricing", "Demo"])],
        [_ad("a.com", sitelinks=["Pricing", "Free Trial"])],
        keyword_id=1, label="k",
    )
    c = next(c for c in out if c["kind"] == "ad_sitelinks_changed")
    assert c["payload"]["added"] == ["Free Trial"]
    assert c["payload"]["removed"] == ["Demo"]


def test_reordered_sitelinks_are_not_a_change():
    """Order varies between identical calls; only membership is meaningful."""
    out = diff.diff_serp_ads(
        [_ad("a.com", sitelinks=["A", "B"])], [_ad("a.com", sitelinks=["B", "A"])], keyword_id=1, label="k"
    )
    assert out == []


# ---- product diff -----------------------------------------------------------------------------


def _p(merchant: str, title: str, price: float, *, original=None, promo=None):
    return {"merchant": merchant, "title": title, "price": price, "original_price": original, "promo": promo}


def test_a_price_cut_is_reported():
    out = diff.diff_products([_p("M", "T", 100.0)], [_p("M", "T", 80.0)], keyword_id=1, label="k")
    c = next(c for c in out if c["kind"] == "product_price_changed")
    assert c["payload"]["from_price"] == 100.0
    assert c["payload"]["to_price"] == 80.0
    assert c["payload"]["delta_pct"] == -20.0


def test_a_price_rise_is_reported_too():
    out = diff.diff_products([_p("M", "T", 80.0)], [_p("M", "T", 100.0)], keyword_id=1, label="k")
    assert next(c for c in out if c["kind"] == "product_price_changed")["payload"]["delta_pct"] == 25.0


def test_a_rounding_sized_move_is_ignored():
    """Measured noise floor on repeated identical queries was zero changes, but a
    sub-percent move is not worth an alert."""
    assert diff.diff_products([_p("M", "T", 100.0)], [_p("M", "T", 100.4)], keyword_id=1, label="k") == []


def test_a_product_appearing_is_not_an_event():
    """The product SET churns hard between identical draws, so presence and absence
    would fire on sampling rather than on merchandising."""
    assert diff.diff_products([_p("M", "T", 10.0)], [_p("M", "T", 10.0), _p("M2", "T2", 20.0)],
                              keyword_id=1, label="k") == []


def test_a_product_disappearing_is_not_an_event():
    assert diff.diff_products([_p("M", "T", 10.0), _p("M2", "T2", 20.0)], [_p("M", "T", 10.0)],
                              keyword_id=1, label="k") == []


def test_the_same_title_at_two_merchants_is_two_products():
    """Diff key is (merchant, title): product ids were measured unstable across runs."""
    out = diff.diff_products(
        [_p("A", "T", 100.0), _p("B", "T", 100.0)],
        [_p("A", "T", 100.0), _p("B", "T", 50.0)],
        keyword_id=1, label="k",
    )
    assert len(out) == 1
    assert out[0]["payload"]["merchant"] == "B"


def test_a_new_promotion_is_reported():
    out = diff.diff_products([_p("M", "T", 100.0)], [_p("M", "T", 100.0, original=120.0, promo="20% OFF")],
                             keyword_id=1, label="k")
    assert "product_promo_appeared" in {c["kind"] for c in out}


def test_the_first_run_reports_nothing():
    assert diff.diff_products(None, [_p("M", "T", 10.0)], keyword_id=1, label="k") == []


# ---- video exclusion --------------------------------------------------------------------------


def test_video_creatives_are_excluded():
    """Video ads are dropped at normalization, not at the API.

    `creative_format` filters server-side but accepts exactly one value, so keeping
    text and image would cost two searches per competitor per run instead of one.
    Dropping the rows here costs nothing and leaves `snapshots.raw` complete, so
    video can be re-derived later without spending quota.
    """
    raw = {"ad_creatives": [
        {"ad_creative_id": "T", "format": "text"},
        {"ad_creative_id": "V", "format": "video"},
        {"ad_creative_id": "I", "format": "image"},
    ]}
    out = creatives_from_ads_transparency(raw)
    assert [c["creative_id"] for c in out] == ["T", "I"]


def test_the_format_filter_is_case_insensitive():
    """Observed values are lowercase, but the API rejects `TEXT` as a request param,
    so it clearly normalises case somewhere and the response may too."""
    raw = {"ad_creatives": [{"ad_creative_id": "V", "format": "VIDEO"}]}
    assert creatives_from_ads_transparency(raw) == []


def test_an_unknown_format_is_kept_rather_than_silently_dropped():
    """Unknown formats already collapse to "text". A new format Google introduces
    should show up as a creative, not vanish."""
    raw = {"ad_creatives": [{"ad_creative_id": "X", "format": "carousel"}]}
    assert len(creatives_from_ads_transparency(raw)) == 1
