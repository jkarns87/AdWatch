"""Actually execute run_collect end to end against a fake SerpApi client.

Every other test of the collect path stops at client construction, so no test had
ever run the body. That let a plain signature mismatch reach production: a helper
was called without a keyword-only argument it still required, and the endpoint
returned 500 on the first request. The unit test for the helper passed, because it
called the helper directly with the old signature.

Nothing here asserts about SerpApi. The point is that the collect body executes —
every call site reachable, every normalizer wired to a model whose columns exist,
and a run that reaches "done".
"""

import pytest

from app import models as m
from app.engine import collect as collect_mod

ATC = {"ad_creatives": [
    {"ad_creative_id": "CR1", "format": "text", "advertiser": "A Co", "advertiser_id": "AR1",
     "first_shown": 1700000000, "last_shown": 1788000000, "total_days_shown": 120,
     "details_link": "https://adstransparency.example/CR1", "target_domain": "rival.com"},
]}
SERP = {
    "ads": [
        {"position": 1, "block_position": "top", "title": "Buy Coffee", "description": "Fresh roast",
         "displayed_link": "https://www.rival.com › shop", "link": "https://www.google.com/goto?url=X",
         "source": "Rival®", "sitelinks": [{"title": "Pricing", "link": "https://www.google.com/goto?url=Y"}]},
    ],
    "immersive_products": [
        {"source": "AShop", "title": "Grinder", "price": "$99.00", "extracted_price": 99.0,
         "rating": 4.5, "reviews": 100, "extensions": ["10% OFF"], "extracted_original_price": 110.0},
    ],
}
TIMESERIES = {"interest_over_time": {"timeline_data": [
    {"date": "Sep 1, 2026", "timestamp": "1788307200", "values": [{"extracted_value": 50}]},
]}}
RELATED = {"related_queries": {"rising": [{"query": "cold brew", "value": "+400%", "extracted_value": 400}]}}


class _Res:
    from_cache = False

    def __init__(self, data):
        self.data = data
        self.search_id = "sid"


class _FakeClient:
    """Answers every engine the collector calls, with plausibly-shaped payloads."""

    searches_used = 0

    def __init__(self, *a, **k):
        self.calls: list[str] = []

    def ads_transparency(self, **k):
        self.calls.append("atc")
        return _Res(ATC)

    def google_search(self, **k):
        self.calls.append("serp")
        return _Res(SERP)

    def trends_timeseries(self, **k):
        self.calls.append("trends")
        return _Res(TIMESERIES)

    def trends_related_queries(self, **k):
        self.calls.append("related")
        return _Res(RELATED)


@pytest.fixture
def watchlist(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(workspace_id=1, name="Coffee", vertical="coffee", geo="US", location="Austin, Texas, United States")
    db.add(w)
    db.flush()
    db.add(m.Competitor(watchlist_id=w.id, name="Rival", domain="rival.com"))
    db.add(m.Keyword(watchlist_id=w.id, term="coffee"))
    db.flush()
    return w


@pytest.fixture
def faked(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: client)
    return client


def test_a_run_completes(db, watchlist, faked):
    """The regression test. A TypeError anywhere in the body fails here."""
    run, n_snapshots, changes = collect_mod.run_collect(db, watchlist, fresh=False)
    assert run.status == "done", f"run failed: {run.error}"
    assert n_snapshots > 0


def test_every_collector_is_reached(db, watchlist, faked):
    collect_mod.run_collect(db, watchlist, fresh=False)
    assert set(faked.calls) == {"atc", "serp", "trends", "related"}


def test_the_consensus_takes_more_than_one_related_draw(db, watchlist, faked):
    collect_mod.run_collect(db, watchlist, fresh=False)
    assert faked.calls.count("related") == collect_mod.RELATED_QUERY_DRAWS


def test_rows_land_in_every_table_the_collector_writes(db, watchlist, faked):
    """Each normalizer is wired to a model whose columns actually exist — a renamed
    or missing column raises here rather than at the first production request."""
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    assert db.query(m.Creative).count() == 1
    assert db.query(m.SerpAd).count() == 1
    assert db.query(m.ProductListing).count() == 1
    assert db.query(m.TrendPoint).count() >= 1


def test_the_new_fields_are_persisted_not_just_parsed(db, watchlist, faked):
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    ad = db.query(m.SerpAd).one()
    assert ad.sitelinks == ["Pricing"]
    assert ad.source == "Rival®"
    assert ad.advertiser_domain == "rival.com", "breadcrumb leaked into the diff key"
    assert db.query(m.Creative).one().total_days_shown == 120
    p = db.query(m.ProductListing).one()
    assert (p.merchant, p.price, p.promo) == ("AShop", 99.0, "10% OFF")


def test_the_first_run_emits_no_changes(db, watchlist, faked):
    """Baseline rule: there is nothing to diff against."""
    _, _, changes = collect_mod.run_collect(db, watchlist, fresh=False)
    assert changes == []


def test_a_second_run_diffs_against_the_first(db, watchlist, faked):
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    _, _, changes = collect_mod.run_collect(db, watchlist, fresh=False)
    # Identical payloads, so the only honest answer is no change.
    assert [c.kind for c in changes] == []


# ---- absence of evidence ----------------------------------------------------------------------


class _EmptyATC(_FakeClient):
    """The Ads Transparency call returns nothing for this competitor."""

    def ads_transparency(self, **k):
        self.calls.append("atc")
        return _Res({"ad_creatives": []})


def test_an_empty_transparency_response_does_not_retire_known_creatives(db, watchlist, monkeypatch):
    """Zero creatives back is not the same as zero creatives running.

    upsert_creatives deactivates everything it did not see this run, so a single
    empty response — a domain absent from the Ads Transparency Center, an API
    hiccup, an exhausted quota — silently retired a competitor's entire history.
    Observed in production: a live run against a watchlist of synthetic `.example`
    domains took every seeded creative to active=False in one pass.

    The rest of the engine already draws this distinction: serp_view separates "no
    ads on that run" from "never collected", and the diff suppresses its baseline
    rather than reporting everything as new.
    """
    client = _FakeClient()
    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: client)
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    assert db.query(m.Creative).filter_by(active=True).count() == 1

    empty = _EmptyATC()
    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: empty)
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    assert db.query(m.Creative).filter_by(active=True).count() == 1, "an empty response retired the creative"


def test_a_creative_missing_from_a_populated_response_is_still_retired(db, watchlist, monkeypatch):
    """The guard must not disable genuine retirement — a creative absent from a
    response that returned other creatives really has stopped."""
    client = _FakeClient()
    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: client)
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()

    class _Different(_FakeClient):
        def ads_transparency(self, **k):
            self.calls.append("atc")
            return _Res({"ad_creatives": [{"ad_creative_id": "CR2", "format": "text"}]})

    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: _Different())
    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    assert db.query(m.Creative).filter_by(creative_id="CR1").one().active is False
    assert db.query(m.Creative).filter_by(creative_id="CR2").one().active is True


# ---- long model calls must not hold a transaction ---------------------------------------------


def test_analyze_releases_its_transaction_before_calling_the_model(db, watchlist, faked, monkeypatch):
    """The model calls are the longest wait in the request, and they all happen
    before the result loop starts.

    Holding the read transaction open across them left the connection idle in
    transaction long enough for Postgres to close it, so the first write afterwards
    raised "server closed the connection unexpectedly" — a 500 on an endpoint whose
    collect had already succeeded and committed.
    """
    from app.engine import analyze as analyze_mod

    collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    run = db.query(m.Run).first()
    db.add(m.Change(watchlist_id=watchlist.id, run_id=run.id, kind="creative_launched",
                    subject_type="competitor", subject_id=1, subject_label="Rival",
                    severity="medium", payload={}))
    db.commit()

    in_transaction: list[bool] = []

    class _Analyst:
        def __init__(self, *a, **k):
            pass

        def analyze(self, context, changes):
            in_transaction.append(db.in_transaction())
            return []

    monkeypatch.setattr(analyze_mod, "Analyst", _Analyst)
    analyze_mod.run_analyze(db, watchlist)

    assert in_transaction, "the analyst was never reached"
    assert in_transaction[0] is False, "a transaction was open across the model calls"


def test_a_creative_repeated_in_one_response_is_inserted_once(db, watchlist, monkeypatch):
    """The Ads Transparency response can list the same creative twice.

    upsert_creatives loaded existing rows once, then created a Creative per response
    row without tracking what it had already created in this batch, so a duplicate
    produced two INSERTs of the same (competitor_id, creative_id) in one flush.
    Production: 'Key (competitor_id, creative_id)=(21, CR097050...) already exists',
    which failed the whole run.
    """
    class _Dupes(_FakeClient):
        def ads_transparency(self, **k):
            self.calls.append("atc")
            return _Res({"ad_creatives": [
                {"ad_creative_id": "CR1", "format": "text", "total_days_shown": 10},
                {"ad_creative_id": "CR1", "format": "text", "total_days_shown": 10},
                {"ad_creative_id": "CR2", "format": "text"},
            ]})

    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: _Dupes())
    run, _, _ = collect_mod.run_collect(db, watchlist, fresh=False)
    db.flush()
    assert run.status == "done", f"run failed: {run.error}"
    assert db.query(m.Creative).count() == 2
