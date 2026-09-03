"""Reading across runs, not just the latest one.

Every existing read pins to _latest_run_id, so serp_ads, trend_points and the creative
flight columns — all of which are already stored per run and cost real quota to collect
— could not be queried at all. The run_id foreign keys existed only so the diff engine
could compare run N to N-1.

No new data. These endpoints read what is already there.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    s.add(m.Workspace(id=1, name="acme"))
    s.flush()
    w = m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="coffee", geo="US")
    s.add(w)
    s.flush()

    me = m.Competitor(id=10, watchlist_id=1, name="Verve", domain="vervecoffee.com", is_self=True)
    rival = m.Competitor(id=11, watchlist_id=1, name="Blue Bottle", domain="bluebottlecoffee.com")
    kw = m.Keyword(id=21, watchlist_id=1, term="coffee subscription")
    s.add_all([me, rival, kw])
    s.flush()

    base = datetime(2026, 9, 1, tzinfo=UTC)
    runs = []
    for i in range(3):
        r = m.Run(watchlist_id=1, status="done", started_at=base + timedelta(days=i),
                  finished_at=base + timedelta(days=i, minutes=4), searches_used=19)
        s.add(r)
        s.flush()
        runs.append(r)

    # A creative that ran for the first two runs then stopped, and one still live.
    s.add_all([
        m.Creative(competitor_id=11, creative_id="CR-OLD", format="image",
                   first_shown=date(2026, 8, 20), last_shown=date(2026, 9, 2),
                   first_seen_run_id=runs[0].id, last_seen_run_id=runs[1].id, active=False),
        m.Creative(competitor_id=11, creative_id="CR-LIVE", format="video",
                   first_shown=date(2026, 9, 1), last_shown=date(2026, 9, 3),
                   first_seen_run_id=runs[0].id, last_seen_run_id=runs[2].id, active=True),
        m.Creative(competitor_id=10, creative_id="CR-MINE", format="text",
                   first_shown=date(2026, 9, 1), last_shown=date(2026, 9, 3),
                   first_seen_run_id=runs[0].id, last_seen_run_id=runs[2].id, active=True),
    ])

    # A rival climbing from 4th to 1st while we slip from 1st to 3rd.
    for i, r in enumerate(runs):
        s.add(m.SerpAd(keyword_id=21, run_id=r.id, position=1 + i, block="top",
                       advertiser_domain="vervecoffee.com", title="us"))
        s.add(m.SerpAd(keyword_id=21, run_id=r.id, position=4 - i, block="top",
                       advertiser_domain="bluebottlecoffee.com", title="them"))
    s.flush()

    app.dependency_overrides[get_db] = lambda: s
    try:
        yield TestClient(app), s, runs
    finally:
        app.dependency_overrides.pop(get_db, None)
        s.close()
        engine.dispose()


# ---- creative flight history ------------------------------------------------------


def test_flights_include_creatives_that_have_stopped(client):
    """The whole point. The latest-run view shows only what is live now, so a creative
    that ran for a fortnight and stopped is invisible — exactly the thing worth seeing."""
    c, _, _ = client
    body = c.get("/api/v1/watchlists/1/history/creatives").json()
    ids = {f["creative_id"] for f in body}
    assert "CR-OLD" in ids and "CR-LIVE" in ids


def test_a_flight_reports_how_long_it_ran(client):
    c, _, _ = client
    old = next(f for f in c.get("/api/v1/watchlists/1/history/creatives").json() if f["creative_id"] == "CR-OLD")
    assert old["first_shown"] == "2026-08-20"
    assert old["last_shown"] == "2026-09-02"
    # Inclusive of both ends: Aug 20 through Sep 2 is 14 distinct days live, and a
    # creative first and last seen on the same day ran for one day, not zero.
    assert old["days_live"] == 14
    assert old["active"] is False


def test_a_creative_seen_on_a_single_day_counts_as_one_day(client):
    c, s, runs = client
    s.add(m.Creative(competitor_id=11, creative_id="CR-ONEDAY", format="text",
                     first_shown=date(2026, 9, 3), last_shown=date(2026, 9, 3),
                     first_seen_run_id=runs[2].id, last_seen_run_id=runs[2].id, active=True))
    s.flush()
    one = next(f for f in c.get("/api/v1/watchlists/1/history/creatives").json()
               if f["creative_id"] == "CR-ONEDAY")
    assert one["days_live"] == 1


def test_your_own_creatives_are_included_and_labelled(client):
    """Tracking yourself is the point of is_self; a flight chart without your own ads
    tells you what everyone else did and not how you compare."""
    c, _, _ = client
    mine = [f for f in c.get("/api/v1/watchlists/1/history/creatives").json() if f["is_self"]]
    assert [f["creative_id"] for f in mine] == ["CR-MINE"]


def test_flights_can_be_filtered_to_one_competitor(client):
    c, _, _ = client
    body = c.get("/api/v1/watchlists/1/history/creatives", params={"competitor_id": 11}).json()
    assert {f["competitor_id"] for f in body} == {11}


def test_flights_are_newest_first(client):
    c, _, _ = client
    shown = [f["last_shown"] for f in c.get("/api/v1/watchlists/1/history/creatives").json()]
    assert shown == sorted(shown, reverse=True)


# ---- SERP position history --------------------------------------------------------


def test_serp_history_returns_a_point_per_run(client):
    c, _, runs = client
    body = c.get("/api/v1/watchlists/1/history/serp", params={"keyword_id": 21}).json()
    assert [r["run_id"] for r in body["runs"]] == [r.id for r in runs]
    us = next(s for s in body["series"] if s["advertiser_domain"] == "vervecoffee.com")
    assert [p["position"] for p in us["points"]] == [1, 2, 3]


def test_serp_history_marks_who_is_tracked_and_who_is_you(client):
    """Otherwise a position chart is a list of strangers."""
    c, _, _ = client
    body = c.get("/api/v1/watchlists/1/history/serp", params={"keyword_id": 21}).json()
    by = {s["advertiser_domain"]: s for s in body["series"]}
    assert by["vervecoffee.com"]["is_self"] is True
    assert by["bluebottlecoffee.com"]["tracked"] is True
    assert by["bluebottlecoffee.com"]["is_self"] is False


def test_serp_history_rejects_a_keyword_from_another_watchlist(client):
    c, _, _ = client
    assert c.get("/api/v1/watchlists/1/history/serp", params={"keyword_id": 999}).status_code == 404


def test_serp_history_is_bounded_to_recent_runs(client):
    c, _, _ = client
    body = c.get("/api/v1/watchlists/1/history/serp", params={"keyword_id": 21, "runs": 2}).json()
    assert len(body["runs"]) == 2
    for s in body["series"]:
        assert len(s["points"]) <= 2


def test_an_advertiser_absent_from_a_run_has_no_point_for_it(client):
    """Leaving the run out entirely, rather than reporting position 0, is what lets a
    chart show a gap instead of a drop to the top of the page."""
    c, s, runs = client
    s.add(m.SerpAd(keyword_id=21, run_id=runs[2].id, position=6, block="bottom",
                   advertiser_domain="latecomer.com", title="new"))
    s.flush()
    body = c.get("/api/v1/watchlists/1/history/serp", params={"keyword_id": 21}).json()
    late = next(x for x in body["series"] if x["advertiser_domain"] == "latecomer.com")
    assert [p["run_id"] for p in late["points"]] == [runs[2].id]
