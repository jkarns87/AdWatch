"""The user's own domain is tracked as a competitor row with is_self=True.

That flag has reach: eleven places touch w.competitors. Getting it wrong makes the
user appear as their own competitor, which reads as a data bug rather than a code
bug and is miserable to trace. The rule:

  EXCLUDE self — user-facing competitor counts and plan limits
  INCLUDE self — collection and share of voice, which are the whole point of
                 tracking yourself in the first place
"""

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
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    session.add(m.Workspace(id=1, name="acme"))
    session.flush()
    w = m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="specialty coffee", geo="US")
    session.add(w)
    session.flush()
    session.add_all([
        m.Competitor(watchlist_id=w.id, name="Verve", domain="vervecoffee.com", is_self=True),
        m.Competitor(watchlist_id=w.id, name="Blue Bottle", domain="bluebottlecoffee.com"),
        m.Competitor(watchlist_id=w.id, name="Sightglass", domain="sightglasscoffee.com"),
    ])
    session.add(m.Keyword(watchlist_id=w.id, term="coffee subscription"))
    session.flush()
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session, w
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def test_the_summary_count_excludes_you(client):
    """Three rows, two competitors. You are not your own competitor."""
    c, _, _ = client
    row = next(r for r in c.get("/api/v1/watchlists").json() if r["id"] == 1)
    assert row["competitor_count"] == 2


def test_the_detail_view_marks_which_row_is_you(client):
    c, _, _ = client
    body = c.get("/api/v1/watchlists/1").json()
    mine = [x for x in body["competitors"] if x["is_self"]]
    assert [x["domain"] for x in mine] == ["vervecoffee.com"]
    assert len(body["competitors"]) == 3, "you are still listed, just labelled"


def test_plan_limits_do_not_count_you(client):
    """Charging someone a competitor slot for their own domain would be absurd."""
    c, _, _ = client
    row = next(r for r in c.get("/api/v1/usage").json()["by_watchlist"] if r["watchlist_id"] == 1)
    assert row["competitors"] == 2


def test_collection_still_fetches_your_own_creatives(client):
    """The point of tracking yourself: creative_launched should fire on your ads too."""
    from app.engine import collect as collect_mod

    _, session, w = client
    session.refresh(w)
    targets = collect_mod.competitors_to_collect(w)
    assert "vervecoffee.com" in {c.domain for c in targets}
    assert len(targets) == 3


def test_share_of_voice_treats_you_as_tracked(client):
    """Otherwise the SERP table shows every rival as tracked and you as a stranger."""
    from app.routers import reads

    _, session, w = client
    session.refresh(w)
    assert "vervecoffee.com" in reads.tracked_domains(w)
    assert len(reads.tracked_domains(w)) == 3
