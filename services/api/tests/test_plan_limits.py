"""Plans gate what you can create, not just what the usage page reports.

plans.py defined watchlists, competitors_per_watchlist and keywords_per_watchlist from
the start, and was imported by exactly one module: routers/usage.py. Every limit was
displayed and none was checked, so a free workspace capped at 2 competitors and 3
keywords could add fifty of each.

Two things must not count against a limit:

  * the self competitor, which the model already excludes from user-facing counts and
    plan limits — it is the customer's own domain, tracked so SERP reads can answer
    "where am I versus them";
  * brand terms, which the collector provisions from the competitor list rather than
    the customer choosing them. Charging a keyword slot for a row the system created
    would make adding a competitor silently consume a keyword.

Enforcement is on creation only. A workspace that is already over a limit — because it
was created before this existed, or was downgraded — keeps everything it has and is
simply unable to add more. Deleting data to punish a downgrade is not our call.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.db import Base, get_db
from app.main import app
from app.plans import PLANS


@pytest.fixture
def client():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    s.add(m.Workspace(id=1, name="acme"))
    s.flush()
    s.add(m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="coffee", geo="US"))
    s.commit()
    app.dependency_overrides[get_db] = lambda: s
    try:
        yield TestClient(app), s
    finally:
        app.dependency_overrides.pop(get_db, None)
        s.close()
        engine.dispose()


def _hdr(plan: str) -> dict:
    """AUTH_PROVIDER=none in tests, so X-Plan selects the plan under test."""
    return {"X-Plan": plan, "X-Workspace-Id": "1"}


FREE = PLANS["free"]


# ---- competitors ---------------------------------------------------------------------------------


def test_competitors_are_capped_by_the_plan(client):
    c, s = client
    for i in range(FREE.competitors_per_watchlist):
        r = c.post("/api/v1/watchlists/1/competitors", json={"name": f"R{i}", "domain": f"r{i}.com"}, headers=_hdr("free"))
        assert r.status_code == 201, r.text
    r = c.post("/api/v1/watchlists/1/competitors", json={"name": "one too many", "domain": "x.com"}, headers=_hdr("free"))
    assert r.status_code == 402
    assert "free" in r.json()["detail"].lower()
    assert str(FREE.competitors_per_watchlist) in r.json()["detail"]


def test_a_bigger_plan_allows_more(client):
    c, s = client
    for i in range(FREE.competitors_per_watchlist + 1):
        r = c.post("/api/v1/watchlists/1/competitors", json={"name": f"R{i}", "domain": f"r{i}.com"}, headers=_hdr("team"))
        assert r.status_code == 201, r.text


def test_the_self_competitor_does_not_consume_a_slot(client):
    """It is the customer's own domain, already excluded from user-facing counts."""
    c, s = client
    s.add(m.Competitor(watchlist_id=1, name="Us", domain="us.com", is_self=True))
    s.commit()
    for i in range(FREE.competitors_per_watchlist):
        r = c.post("/api/v1/watchlists/1/competitors", json={"name": f"R{i}", "domain": f"r{i}.com"}, headers=_hdr("free"))
        assert r.status_code == 201, r.text


# ---- keywords ------------------------------------------------------------------------------------


def test_keywords_are_capped_by_the_plan(client):
    c, s = client
    for i in range(FREE.keywords_per_watchlist):
        assert c.post("/api/v1/watchlists/1/keywords", json={"term": f"kw {i}"}, headers=_hdr("free")).status_code == 201
    r = c.post("/api/v1/watchlists/1/keywords", json={"term": "one too many"}, headers=_hdr("free"))
    assert r.status_code == 402
    assert str(FREE.keywords_per_watchlist) in r.json()["detail"]


def test_brand_terms_do_not_consume_keyword_slots(client):
    """The collector creates one per competitor. Charging a slot for a row the system
    created would make adding a competitor silently cost a keyword."""
    c, s = client
    comp = m.Competitor(watchlist_id=1, name="Rival", domain="rival.com")
    s.add(comp)
    s.flush()
    s.add(m.Keyword(watchlist_id=1, term="Rival", kind="brand", owner_competitor_id=comp.id))
    s.commit()
    for i in range(FREE.keywords_per_watchlist):
        r = c.post("/api/v1/watchlists/1/keywords", json={"term": f"kw {i}"}, headers=_hdr("free"))
        assert r.status_code == 201, r.text


# ---- watchlists ----------------------------------------------------------------------------------


def test_watchlists_are_capped_by_the_plan(client):
    c, s = client
    # The fixture already holds one, which is the free allowance.
    r = c.post("/api/v1/watchlists", json={"name": "Second", "vertical": "tea", "geo": "US"}, headers=_hdr("free"))
    assert r.status_code == 402
    assert "watchlist" in r.json()["detail"].lower()


def test_a_bigger_plan_allows_a_second_watchlist(client):
    c, s = client
    assert c.post("/api/v1/watchlists", json={"name": "Second", "vertical": "tea", "geo": "US"}, headers=_hdr("team")).status_code == 201


# ---- being over a limit already --------------------------------------------------------------------


def test_an_over_limit_workspace_keeps_what_it_has(client):
    """A downgrade must not delete anything. It stops you adding more, and that is all."""
    c, s = client
    for i in range(5):
        s.add(m.Competitor(watchlist_id=1, name=f"R{i}", domain=f"r{i}.com"))
    s.commit()

    assert c.post("/api/v1/watchlists/1/competitors", json={"name": "x", "domain": "x.com"}, headers=_hdr("free")).status_code == 402
    assert len(c.get("/api/v1/watchlists/1", headers=_hdr("free")).json()["competitors"]) == 5


def test_the_message_says_what_to_do_about_it(client):
    """A limit the user cannot act on is just a wall. Name the plan, the limit, and
    the fact that a bigger plan exists."""
    c, s = client
    for i in range(FREE.competitors_per_watchlist):
        c.post("/api/v1/watchlists/1/competitors", json={"name": f"R{i}", "domain": f"r{i}.com"}, headers=_hdr("free"))
    detail = c.post("/api/v1/watchlists/1/competitors", json={"name": "x", "domain": "x.com"}, headers=_hdr("free")).json()["detail"]
    assert "upgrade" in detail.lower()
