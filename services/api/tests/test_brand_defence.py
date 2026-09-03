"""Brand conquesting — who is bidding on a brand's own name.

Measured against the live API on 2026-09-03: 7 of 8 brand SERPs carried ads, 7 of 7
of those had a competitor bidding on the brand, and in 4 of 7 the brand owner was
absent from its own name. Engine choice decides whether you can see it at all —
`engine=google` reported zero conquerors on a brand term where two advertisers were
actively bidding.

It is the highest-value alert in paid search that public data can support: a rival
paying for your name is spending money to take customers who already asked for you,
and being absent from your own brand term means paying nothing to defend it.

Cost is one search per brand term per run, and brand terms deliberately skip the
trends and related-query calls that ordinary keywords make — demand for a brand name
is not the signal here, so charging three extra searches for it would be waste.
"""

import pytest

from app import models as m
from app.engine import brand
from app.engine import collect as collect_mod


def _ad(domain: str, *, position: int = 1, title: str = "T") -> dict:
    return {"advertiser_domain": domain, "position": position, "block": "top", "title": title}


# ---- who counts as a conqueror ------------------------------------------------------------------


def test_a_rival_bidding_on_the_brand_is_a_conqueror():
    out = brand.assess(
        [_ad("rival.com"), _ad("owner.com", position=2)], owner_domain="owner.com"
    )
    assert [c["advertiser_domain"] for c in out["conquerors"]] == ["rival.com"]


def test_the_owner_is_never_its_own_conqueror():
    out = brand.assess([_ad("owner.com")], owner_domain="owner.com")
    assert out["conquerors"] == []
    assert out["owner_present"] is True


def test_a_subdomain_of_the_owner_is_still_the_owner():
    """shop.owner.com is the brand defending itself, not an attack on it."""
    out = brand.assess([_ad("shop.owner.com")], owner_domain="owner.com")
    assert out["conquerors"] == []
    assert out["owner_present"] is True


def test_an_unrelated_domain_that_merely_ends_in_the_owner_is_not_the_owner():
    """notowner.com endswith owner.com as a string. Suffix matching has to respect
    the label boundary or a lookalike domain reads as the brand defending itself —
    which is exactly the kind of advertiser worth alerting on."""
    out = brand.assess([_ad("notowner.com")], owner_domain="owner.com")
    assert [c["advertiser_domain"] for c in out["conquerors"]] == ["notowner.com"]


def test_the_owner_absent_from_its_own_brand_is_reported():
    """Measured at 4 of 7 live brand SERPs. Paying nothing to defend your own name
    while a rival pays to take it is the worst position on the page."""
    out = brand.assess([_ad("rival.com")], owner_domain="owner.com")
    assert out["owner_present"] is False
    assert out["undefended"] is True


def test_undefended_requires_someone_to_actually_be_attacking():
    """No ads at all on a brand term is not an emergency — nobody is paying for it,
    including the owner, and that is the normal, healthy state."""
    out = brand.assess([], owner_domain="owner.com")
    assert out["owner_present"] is False
    assert out["undefended"] is False


def test_the_owners_position_is_reported_when_present():
    out = brand.assess([_ad("rival.com"), _ad("owner.com", position=2)], owner_domain="owner.com")
    assert out["owner_position"] == 2


# ---- events ------------------------------------------------------------------------------------


def test_the_first_run_reports_nothing():
    """Baseline rule, as everywhere else in the diff engine: with nothing to compare
    against, every advertiser would look new."""
    assert brand.diff_brand(None, [_ad("rival.com")], owner_domain="o.com", competitor_id=1, label="Owner") == []


def test_a_newly_arrived_conqueror_is_reported():
    out = brand.diff_brand(
        [_ad("owner.com")], [_ad("rival.com"), _ad("owner.com", position=2)],
        owner_domain="owner.com", competitor_id=1, label="Owner",
    )
    c = next(c for c in out if c["kind"] == "brand_conquest")
    assert c["severity"] == "high"
    assert c["payload"]["advertiser_domain"] == "rival.com"
    assert c["payload"]["brand"] == "Owner"


def test_a_conqueror_that_was_already_there_is_not_re_reported():
    """Ads flicker between identical calls, so re-announcing a standing conqueror
    every run would bury the run where one actually arrives."""
    prev = [_ad("rival.com"), _ad("owner.com", position=2)]
    assert brand.diff_brand(prev, prev, owner_domain="owner.com", competitor_id=1, label="Owner") == []


def test_a_conqueror_giving_up_is_reported():
    out = brand.diff_brand(
        [_ad("rival.com")], [_ad("owner.com")],
        owner_domain="owner.com", competitor_id=1, label="Owner",
    )
    assert "brand_conquest_ended" in {c["kind"] for c in out}


def test_losing_your_own_brand_term_is_reported():
    out = brand.diff_brand(
        [_ad("owner.com"), _ad("rival.com", position=2)], [_ad("rival.com")],
        owner_domain="owner.com", competitor_id=1, label="Owner",
    )
    c = next(c for c in out if c["kind"] == "brand_undefended")
    assert c["severity"] == "high"


def test_regaining_your_own_brand_term_is_reported():
    out = brand.diff_brand(
        [_ad("rival.com")], [_ad("owner.com"), _ad("rival.com", position=2)],
        owner_domain="owner.com", competitor_id=1, label="Owner",
    )
    assert "brand_defended" in {c["kind"] for c in out}


def test_an_empty_current_block_does_not_report_the_owner_as_losing_ground():
    """A brand SERP with no ads at all means nobody is bidding, owner included.
    Reporting that as "undefended" would fire on the quietest possible state, and
    the paid block is measurably flaky — one call sees zero ads 44% of the time."""
    out = brand.diff_brand(
        [_ad("owner.com")], [], owner_domain="owner.com", competitor_id=1, label="Owner"
    )
    assert "brand_undefended" not in {c["kind"] for c in out}


# ---- brand terms ---------------------------------------------------------------------------------


def test_a_brand_term_is_the_competitor_name():
    assert brand.brand_term(type("C", (), {"name": "Peet's Coffee", "domain": "peets.com"})()) == "Peet's Coffee"


def test_a_competitor_with_no_name_falls_back_to_its_domain_label():
    c = type("C", (), {"name": "", "domain": "dunkindonuts.com"})()
    assert brand.brand_term(c) == "dunkindonuts"


# ---- provisioning and collection -----------------------------------------------------------------


@pytest.fixture
def watchlist(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(workspace_id=1, name="Coffee", vertical="coffee", geo="US",
                    location="Seattle, Washington, United States")
    db.add(w)
    db.flush()
    db.add_all([
        m.Competitor(watchlist_id=w.id, name="Rival", domain="rival.com"),
        m.Competitor(watchlist_id=w.id, name="Us", domain="us.com", is_self=True),
    ])
    db.add(m.Keyword(watchlist_id=w.id, term="coffee subscription"))
    db.flush()
    return w


def test_every_competitor_gets_a_brand_term(db, watchlist):
    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    terms = {k.term: k for k in db.query(m.Keyword).filter_by(kind="brand").all()}
    assert set(terms) == {"Rival", "Us"}


def test_our_own_brand_gets_a_term_too(db, watchlist):
    """Defending your own name is the point. The self competitor is excluded from
    user-facing counts, not from brand monitoring."""
    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    ours = db.query(m.Keyword).filter_by(kind="brand", term="Us").one()
    assert ours.owner_competitor_id == db.query(m.Competitor).filter_by(is_self=True).one().id


def test_provisioning_is_idempotent(db, watchlist):
    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    assert db.query(m.Keyword).filter_by(kind="brand").count() == 2


def test_a_brand_term_does_not_collide_with_an_identical_market_keyword(db, watchlist):
    """A customer may already track their own brand as an ordinary keyword. The two
    are different rows with different collection costs and must not merge."""
    db.add(m.Keyword(watchlist_id=watchlist.id, term="Rival"))
    db.flush()
    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    assert db.query(m.Keyword).filter_by(term="Rival").count() == 2


def test_brand_terms_skip_the_trends_and_related_calls(db, watchlist, monkeypatch):
    """One search per brand term, not four. Demand for a brand name is not the
    signal, so paying for trends and three related-query draws would be waste."""
    from tests.test_collect_smoke import _FakeClient

    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    client = _FakeClient()
    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: client)
    collect_mod.run_collect(db, watchlist, fresh=False)

    # 1 market keyword -> serp + trends + N related draws. 2 brand terms -> serp only.
    assert client.calls.count("serp") == 3
    assert client.calls.count("trends") == 1
    assert client.calls.count("related") == collect_mod.RELATED_QUERY_DRAWS


# ---- the endpoint --------------------------------------------------------------------------------


@pytest.fixture
def api():
    """The brands endpoint over the real ASGI app."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base, get_db
    from app.main import app

    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    s.add(m.Workspace(id=1, name="acme"))
    s.flush()
    s.add(m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="coffee", geo="US"))
    s.flush()
    s.add_all([
        m.Competitor(id=10, watchlist_id=1, name="Us", domain="us.com", is_self=True),
        m.Competitor(id=11, watchlist_id=1, name="Rival", domain="rival.com"),
    ])
    s.flush()
    s.add_all([
        m.Keyword(id=20, watchlist_id=1, term="Us", kind="brand", owner_competitor_id=10),
        m.Keyword(id=21, watchlist_id=1, term="Rival", kind="brand", owner_competitor_id=11),
        m.Keyword(id=22, watchlist_id=1, term="coffee subscription"),
    ])
    run = m.Run(id=30, watchlist_id=1, status="done", searches_used=3)
    s.add(run)
    s.flush()
    s.add_all([
        m.Snapshot(run_id=30, watchlist_id=1, kind="search_ads", subject_type="keyword", subject_id=20, raw={}),
        m.Snapshot(run_id=30, watchlist_id=1, kind="search_ads", subject_type="keyword", subject_id=21, raw={}),
        # Someone is bidding on our name and we are not there. Rival defends its own.
        m.SerpAd(keyword_id=20, run_id=30, position=1, block="top", advertiser_domain="rival.com", title="Switch"),
        m.SerpAd(keyword_id=21, run_id=30, position=1, block="top", advertiser_domain="rival.com", title="Rival"),
    ])
    s.flush()

    app.dependency_overrides[get_db] = lambda: s
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        s.close()
        engine.dispose()


def test_the_endpoint_reports_who_is_bidding_on_our_name(api):
    body = api.get("/api/v1/watchlists/1/brands").json()
    ours = body["brands"][0]
    assert ours["brand"] == "Us"
    assert ours["is_self"] is True
    assert ours["undefended"] is True
    assert [c["advertiser_domain"] for c in ours["conquerors"]] == ["rival.com"]


def test_our_own_brand_is_listed_first(api):
    """It is the one the customer can act on today."""
    assert [b["brand"] for b in api.get("/api/v1/watchlists/1/brands").json()["brands"]] == ["Us", "Rival"]


def test_a_brand_defending_itself_shows_no_conquerors(api):
    rival = api.get("/api/v1/watchlists/1/brands").json()["brands"][1]
    assert rival["owner_present"] is True
    assert rival["conquerors"] == []
    assert rival["undefended"] is False


def test_market_keywords_are_not_listed_as_brands(api):
    assert "coffee subscription" not in {b["brand"] for b in api.get("/api/v1/watchlists/1/brands").json()["brands"]}
