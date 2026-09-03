"""Managing per-workspace API keys over HTTP.

The storage layer already refuses to write plaintext. This adds the rule that made
this whole session start: a key is validated with the provider before it is saved,
so "apiworld2026" is rejected at the point of entry rather than 502-ing every
collect while /health stays green.
"""

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import crypto, providers
from app import models as m
from app.db import Base, get_db
from app.main import app

GOOD_SERPAPI = "a" * 64
ACCOUNT_OK = {"plan_name": "Free Plan", "searches_per_month": 250, "plan_searches_left": 250,
              "extra_credits": 0, "total_searches_left": 250, "this_month_usage": 0}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    providers._cache.clear()

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
        crypto._fernet = None
        providers._cache.clear()


def _accept(monkeypatch, status=200, body=None):
    monkeypatch.setattr(
        providers, "_transport_for_tests",
        httpx.MockTransport(lambda r: httpx.Response(status, json=body if body is not None else ACCOUNT_OK)),
    )


def test_no_keys_initially(client):
    c, _ = client
    assert c.get("/api/v1/workspace/keys").json() == []


def test_saving_a_valid_key_returns_only_its_last_four(client, monkeypatch):
    c, _ = client
    _accept(monkeypatch)
    r = c.put("/api/v1/workspace/keys/serpapi", json={"key": GOOD_SERPAPI})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "serpapi"
    assert body["last4"] == "aaaa"
    assert GOOD_SERPAPI not in r.text, "the key must never be echoed back"


def test_an_invalid_key_is_rejected_and_not_stored(client, monkeypatch):
    """This is the apiworld2026 case. Rejecting on save is the whole point."""
    c, s = client
    _accept(monkeypatch, status=401, body={"error": "Invalid API key."})
    r = c.put("/api/v1/workspace/keys/serpapi", json={"key": "apiworld2026"})
    assert r.status_code == 400
    assert "invalid" in r.text.lower()
    assert s.scalars(select(m.WorkspaceSecret)).all() == []


def test_a_key_that_cannot_be_checked_is_still_accepted(client, monkeypatch):
    """Provider downtime is not proof of a bad key — refusing would make the settings
    page unusable whenever SerpApi has a wobble."""
    c, s = client
    monkeypatch.setattr(
        providers, "_transport_for_tests",
        httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("dns"))),
    )
    r = c.put("/api/v1/workspace/keys/serpapi", json={"key": GOOD_SERPAPI})
    assert r.status_code == 200
    assert r.json()["verified"] is False
    assert len(s.scalars(select(m.WorkspaceSecret)).all()) == 1


def test_listing_shows_kind_and_last4_but_never_ciphertext(client, monkeypatch):
    c, _ = client
    _accept(monkeypatch)
    c.put("/api/v1/workspace/keys/serpapi", json={"key": GOOD_SERPAPI})
    r = c.get("/api/v1/workspace/keys")
    assert r.json()[0]["last4"] == "aaaa"
    assert "ciphertext" not in r.text
    assert GOOD_SERPAPI not in r.text


def test_replacing_a_key_keeps_one_row(client, monkeypatch):
    c, s = client
    _accept(monkeypatch)
    c.put("/api/v1/workspace/keys/serpapi", json={"key": GOOD_SERPAPI})
    c.put("/api/v1/workspace/keys/serpapi", json={"key": "b" * 64})
    rows = s.scalars(select(m.WorkspaceSecret)).all()
    assert len(rows) == 1 and rows[0].last4 == "bbbb"


def test_deleting_falls_back_to_the_platform_key(client, monkeypatch):
    c, s = client
    _accept(monkeypatch)
    c.put("/api/v1/workspace/keys/serpapi", json={"key": GOOD_SERPAPI})
    assert c.delete("/api/v1/workspace/keys/serpapi").status_code == 204
    assert s.scalars(select(m.WorkspaceSecret)).all() == []


def test_an_unknown_kind_is_rejected(client):
    c, _ = client
    assert c.put("/api/v1/workspace/keys/openai", json={"key": "x"}).status_code == 400


def test_an_empty_key_is_rejected(client):
    c, _ = client
    assert c.put("/api/v1/workspace/keys/serpapi", json={"key": "   "}).status_code == 400


def test_without_encryption_configured_the_api_refuses_rather_than_storing_plaintext(client, monkeypatch):
    c, s = client
    _accept(monkeypatch)
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    r = c.put("/api/v1/workspace/keys/serpapi", json={"key": GOOD_SERPAPI})
    assert r.status_code == 503
    assert s.scalars(select(m.WorkspaceSecret)).all() == []
