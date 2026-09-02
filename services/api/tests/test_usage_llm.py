"""GET /usage must expose Claude spend alongside SerpApi spend, or the cost page tells
half the truth. Runs against the real ASGI app with the DB dependency pointed at the
in-memory fixture."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import metering
from app import models as m
from app.db import Base, get_db
from app.main import app


class Usage:
    def __init__(self, i=0, o=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


@pytest.fixture
def client():
    # TestClient serves the app on another thread; SQLite connections are thread-bound
    # and ":memory:" is per-connection. StaticPool shares one connection across both.
    engine = create_engine(
        "sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_local()

    ws = m.Workspace(id=1, name="acme")
    session.add(ws)
    session.flush()
    w = m.Watchlist(id=10, workspace_id=1, name="Coffee", vertical="specialty coffee", geo="US")
    session.add(w)
    session.flush()

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def test_usage_reports_zero_llm_spend_before_any_call(client):
    c, _ = client
    body = c.get("/api/v1/usage").json()
    assert body["llm"]["calls"] == 0
    assert body["llm"]["cost_usd"] == 0.0
    assert body["llm"]["metering_since"] is None


def test_usage_reports_recorded_claude_spend(client):
    c, session = client
    metering.record_call(session, workspace_id=1, model="claude-sonnet-5", feature="analyst", usage=Usage(i=1_000_000), watchlist_id=10)
    metering.record_call(session, workspace_id=1, model="claude-sonnet-5", feature="report", usage=Usage(o=1_000_000), watchlist_id=10)

    body = c.get("/api/v1/usage").json()

    assert body["llm"]["calls"] == 2
    assert body["llm"]["cost_usd"] == pytest.approx(12.00)
    assert {r["feature"] for r in body["llm"]["by_feature"]} == {"analyst", "report"}
    assert body["llm"]["metering_since"] is not None


def test_total_cost_combines_serpapi_and_claude(client):
    c, session = client
    metering.record_call(session, workspace_id=1, model="claude-sonnet-5", feature="analyst", usage=Usage(i=1_000_000))
    body = c.get("/api/v1/usage").json()
    assert body["total_cost_usd"] == pytest.approx(body["cost_to_date_usd"] + body["llm"]["cost_usd"])


def test_llm_cost_is_attributed_per_watchlist(client):
    c, session = client
    metering.record_call(session, workspace_id=1, model="claude-sonnet-5", feature="analyst", usage=Usage(i=1_000_000), watchlist_id=10)
    body = c.get("/api/v1/usage").json()
    row = next(r for r in body["by_watchlist"] if r["watchlist_id"] == 10)
    assert row["llm_cost_usd"] == pytest.approx(2.00)


def test_unpriced_calls_are_surfaced_not_hidden(client):
    """A model with no published rate must be visible on the page, not silently free."""
    c, session = client
    metering.record_call(session, workspace_id=1, model="claude-sonnet-4-5", feature="analyst", usage=Usage(i=1_000_000))
    body = c.get("/api/v1/usage").json()
    assert body["llm"]["unpriced_calls"] == 1
    assert body["llm"]["cost_usd"] == 0.0
