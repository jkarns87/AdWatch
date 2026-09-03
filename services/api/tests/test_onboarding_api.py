"""POST /onboarding/analyze and /onboarding/create.

Split on purpose: analyze spends Anthropic tokens and no SerpApi quota, create spends
one Ads Transparency search per kept competitor. The user sees the proposal before any
quota goes.
"""

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.db import Base, get_db
from app.main import app
from app.onboarding import analyze as ana

PROPOSAL = {
    "vertical": {"id": 71, "name": "Food & Drink"},
    "keywords": ["coffee subscription"],
    "competitors": [{"domain": "bluebottlecoffee.com", "name": "Blue Bottle", "reason": "DTC roaster"}],
    "assets": [{"kind": "brand", "key": "primary_color", "value": "#B5121B"}],
    "site_read": True,
    "_usage": SimpleNamespace(input_tokens=1000, output_tokens=200,
                              cache_read_input_tokens=0, cache_creation_input_tokens=0),
}


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    session.add(m.Workspace(id=1, name="acme"))
    session.flush()
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _stub_analysis(monkeypatch, proposal=None):
    monkeypatch.setattr(ana, "analyze_company", lambda **kw: dict(proposal or PROPOSAL))


def _stub_verification(monkeypatch, advertising: set[str]):
    """A domain is verified by whether Ads Transparency knows it as an advertiser."""
    from app.onboarding import verify as ver

    monkeypatch.setattr(ver, "domain_advertises", lambda client, domain: domain in advertising)


def test_analyze_returns_a_proposal_without_persisting(client, monkeypatch):
    c, s = client
    _stub_analysis(monkeypatch)
    body = c.post("/api/v1/onboarding/analyze",
                  json={"name": "Verve", "domain": "vervecoffee.com", "description": "roaster"}).json()
    assert body["vertical"]["name"] == "Food & Drink"
    assert body["competitors"][0]["domain"] == "bluebottlecoffee.com"
    assert s.scalars(select(m.Watchlist)).all() == [], "analyze must not create anything"


def test_analyze_never_leaks_the_usage_marker(client, monkeypatch):
    c, _ = client
    _stub_analysis(monkeypatch)
    r = c.post("/api/v1/onboarding/analyze", json={"name": "V", "domain": "v.com", "description": "d"})
    assert "_usage" not in r.text


def test_analyze_is_metered(client, monkeypatch):
    """Onboarding will be the highest-volume Claude path; it has to show up in cost."""
    c, s = client
    _stub_analysis(monkeypatch)
    c.post("/api/v1/onboarding/analyze", json={"name": "V", "domain": "v.com", "description": "d"})
    row = s.scalars(select(m.LlmCall)).one()
    assert row.feature == "onboarding"
    assert row.input_tokens == 1000


def test_create_tracks_the_company_itself(client, monkeypatch):
    c, s = client
    _stub_verification(monkeypatch, {"bluebottlecoffee.com"})
    body = c.post("/api/v1/onboarding/create", json={
        "name": "Verve", "domain": "vervecoffee.com", "description": "roaster",
        "vertical_id": 71, "keywords": ["coffee subscription"],
        "competitors": ["bluebottlecoffee.com"], "assets": [],
    }).json()
    w = s.get(m.Watchlist, body["watchlist_id"])
    mine = [x for x in w.competitors if x.is_self]
    assert [x.domain for x in mine] == ["vervecoffee.com"]
    assert w.trends_category_id == 71


def test_create_skips_a_domain_that_does_not_advertise(client, monkeypatch):
    """A hallucinated competitor would burn a search every run forever. Skipping it
    silently would be worse than saying so."""
    c, s = client
    _stub_verification(monkeypatch, {"bluebottlecoffee.com"})
    body = c.post("/api/v1/onboarding/create", json={
        "name": "Verve", "domain": "vervecoffee.com", "description": "roaster",
        "vertical_id": 71, "keywords": ["k"],
        "competitors": ["bluebottlecoffee.com", "madeupcoffee.invalid"], "assets": [],
    }).json()
    assert [x["domain"] for x in body["competitors"]] == ["bluebottlecoffee.com"]
    assert body["skipped"] == [{"domain": "madeupcoffee.invalid", "reason": "no advertiser found"}]
    w = s.get(m.Watchlist, body["watchlist_id"])
    assert "madeupcoffee.invalid" not in {x.domain for x in w.competitors}


def test_create_rejects_an_invalid_vertical(client, monkeypatch):
    c, _ = client
    _stub_verification(monkeypatch, set())
    r = c.post("/api/v1/onboarding/create", json={
        "name": "V", "domain": "v.com", "description": "d",
        "vertical_id": 999999, "keywords": [], "competitors": [], "assets": [],
    })
    assert r.status_code == 400


def test_create_persists_assets(client, monkeypatch):
    c, s = client
    _stub_verification(monkeypatch, set())
    c.post("/api/v1/onboarding/create", json={
        "name": "V", "domain": "v.com", "description": "d", "vertical_id": 71,
        "keywords": [], "competitors": [],
        "assets": [{"kind": "brand", "key": "primary_color", "value": "#B5121B"}],
    })
    asset = s.scalars(select(m.CompanyAsset)).one()
    assert asset.kind == "brand" and asset.value == "#B5121B"


def test_create_keeps_what_claude_was_told_so_a_rerun_is_reproducible(client, monkeypatch):
    c, s = client
    _stub_verification(monkeypatch, set())
    body = c.post("/api/v1/onboarding/create", json={
        "name": "Verve", "domain": "vervecoffee.com", "description": "DTC roaster",
        "vertical_id": 71, "keywords": [], "competitors": [], "assets": [],
    }).json()
    w = s.get(m.Watchlist, body["watchlist_id"])
    assert w.company_domain == "vervecoffee.com"
    assert w.company_description == "DTC roaster"


def test_verification_failure_does_not_lose_the_watchlist(client, monkeypatch):
    """SerpApi being down must not throw away everything the user just confirmed."""
    from app.onboarding import verify as ver

    def boom(client, domain):
        raise httpx.ConnectError("dns")

    monkeypatch.setattr(ver, "domain_advertises", boom)
    c, s = client
    body = c.post("/api/v1/onboarding/create", json={
        "name": "V", "domain": "v.com", "description": "d", "vertical_id": 71,
        "keywords": ["k"], "competitors": ["rival.com"], "assets": [],
    }).json()
    assert s.get(m.Watchlist, body["watchlist_id"]) is not None
    assert body["skipped"][0]["reason"] == "could not be checked"
