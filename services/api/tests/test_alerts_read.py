"""GET /alerts — the notification feed, with delivery status attached.

Replaces the frontend's 1+N (api.watchlists() then api.insights() per watchlist).
The alerts table is a delivery log; the page renders a feed. This returns the feed
and hangs delivery off it, so you can see both what was said and whether it landed.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.db import Base, get_db
from app.main import app

SLACK_TRUNCATED = "https://hooks.slack.invalid/services/T04ABCDEFGH/B07ZYXWVUTS/aBcDeFgHiJ…"


@pytest.fixture
def client():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _insight(session, *, ws_id: int, wl_name: str, summary: str, severities: list[str], minutes_ago: int = 0, delivery: dict | None = None):
    ws = session.get(m.Workspace, ws_id) or m.Workspace(id=ws_id, name=f"ws{ws_id}")
    session.add(ws)
    session.flush()
    w = m.Watchlist(workspace_id=ws_id, name=wl_name, vertical="coffee", geo="US")
    session.add(w)
    session.flush()
    run = m.Run(watchlist_id=w.id, status="done")
    session.add(run)
    session.flush()
    ins = m.Insight(
        watchlist_id=w.id, run_id=run.id, model="claude-sonnet-5", summary=summary,
        why_it_matters="because", created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )
    session.add(ins)
    session.flush()
    for sev in severities:
        session.add(m.Change(
            watchlist_id=w.id, run_id=run.id, kind="creative_launched", severity=sev,
            subject_type="competitor", subject_id=1, subject_label="Rival", payload={}, insight_id=ins.id,
        ))
    if delivery:
        session.add(m.Alert(insight_id=ins.id, **delivery))
    session.flush()
    return w, ins


def test_empty_workspace_returns_no_alerts(client):
    c, _ = client
    r = c.get("/api/v1/alerts")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_returns_insights_across_every_watchlist_newest_first(client):
    c, s = client
    _insight(s, ws_id=1, wl_name="Coffee", summary="older", severities=["low"], minutes_ago=60)
    _insight(s, ws_id=1, wl_name="Mattresses", summary="newer", severities=["low"], minutes_ago=1)

    body = c.get("/api/v1/alerts").json()

    assert [a["summary"] for a in body] == ["newer", "older"]
    assert {a["watchlist_name"] for a in body} == {"Coffee", "Mattresses"}


def test_severity_is_the_worst_of_the_linked_changes(client):
    c, s = client
    _insight(s, ws_id=1, wl_name="Coffee", summary="mixed", severities=["low", "high", "medium"])
    assert c.get("/api/v1/alerts").json()[0]["severity"] == "high"


def test_another_workspace_is_not_visible(client):
    c, s = client
    _insight(s, ws_id=2, wl_name="Someone else", summary="theirs", severities=["high"])
    assert c.get("/api/v1/alerts").json() == []


def test_delivery_status_is_attached_when_an_alert_row_exists(client):
    c, s = client
    _insight(
        s, ws_id=1, wl_name="Coffee", summary="delivered", severities=["high"],
        delivery={"channel": "slack", "target": SLACK_TRUNCATED, "status": "sent"},
    )
    item = c.get("/api/v1/alerts").json()[0]
    assert item["delivery"]["channel"] == "slack"
    assert item["delivery"]["status"] == "sent"


def test_an_undelivered_insight_still_appears(client):
    """Alerts only dispatch above min_severity, so plenty of insights have no Alert
    row. They are still things the user should read."""
    c, s = client
    _insight(s, ws_id=1, wl_name="Coffee", summary="never dispatched", severities=["low"])
    item = c.get("/api/v1/alerts").json()[0]
    assert item["summary"] == "never dispatched"
    assert item["delivery"] is None


def test_the_webhook_target_is_never_returned_in_full(client):
    """Even truncated, target carries the team id, bot id and a token prefix."""
    c, s = client
    _insight(
        s, ws_id=1, wl_name="Coffee", summary="s", severities=["high"],
        delivery={"channel": "slack", "target": SLACK_TRUNCATED, "status": "sent"},
    )
    body = c.get("/api/v1/alerts").text
    assert "aBcDeFgHiJ" not in body, "token material reached the API response"
    assert "hooks.slack.invalid" in body, "host is useful and not secret"


def test_a_delivery_error_is_returned_redacted(client):
    c, s = client
    _insight(
        s, ws_id=1, wl_name="Coffee", summary="s", severities=["high"],
        delivery={"channel": "slack", "target": SLACK_TRUNCATED, "status": "failed",
                  "error": f"Client error '404' for url '{SLACK_TRUNCATED}'"},
    )
    body = c.get("/api/v1/alerts").text
    assert "aBcDeFgHiJ" not in body


def test_limit_caps_the_feed(client):
    c, s = client
    for i in range(5):
        _insight(s, ws_id=1, wl_name=f"W{i}", summary=f"s{i}", severities=["low"], minutes_ago=i)
    assert len(c.get("/api/v1/alerts", params={"limit": 2}).json()) == 2
