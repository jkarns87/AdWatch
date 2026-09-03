"""The maintenance endpoint.

Retention is deliberately cross-workspace: it is one nightly sweep, not a per-tenant
action. That makes authentication the whole design question — a normal user token must
not be able to reach it, because a tenant pruning every other tenant's payloads is a
tenant deleting other people's data.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.config import get_settings
from app.db import Base, get_db
from app.main import app

SECRET = "test-dataplane-secret"


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    s.add(m.Workspace(id=1, name="acme"))
    s.flush()
    s.add(m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="coffee", geo="US"))
    s.flush()

    base = datetime(2026, 9, 1, tzinfo=UTC)
    for i in range(6):
        r = m.Run(watchlist_id=1, status="done", started_at=base + timedelta(days=i))
        s.add(r)
        s.flush()
        s.add(m.Snapshot(run_id=r.id, watchlist_id=1, kind="search_ads", subject_type="keyword",
                         subject_id=1, serpapi_search_id=f"s{i}", raw={"payload": "x" * 200}))
    s.flush()

    settings = get_settings()
    monkeypatch.setattr(settings, "dataplane_shared_secret", SECRET, raising=False)
    app.dependency_overrides[get_db] = lambda: s
    try:
        yield TestClient(app), s
    finally:
        app.dependency_overrides.pop(get_db, None)
        s.close()
        engine.dispose()


def test_a_user_token_cannot_prune_every_workspace(client):
    """The endpoint sweeps all workspaces. A tenant reaching it would be deleting other
    tenants' payloads."""
    c, _ = client
    r = c.post("/api/v1/maintenance/prune-snapshots", headers={"X-Workspace-Id": "1"})
    assert r.status_code == 401


def test_the_shared_secret_gets_in(client):
    c, _ = client
    r = c.post("/api/v1/maintenance/prune-snapshots",
               headers={"X-Dataplane-Secret": SECRET}, params={"keep_runs": 2})
    assert r.status_code == 200
    assert r.json()["snapshots_pruned"] == 4


def test_a_wrong_secret_does_not(client):
    c, _ = client
    r = c.post("/api/v1/maintenance/prune-snapshots", headers={"X-Dataplane-Secret": "nope"})
    assert r.status_code == 401


def test_keep_runs_below_the_floor_is_a_client_error_not_a_500(client):
    c, _ = client
    r = c.post("/api/v1/maintenance/prune-snapshots",
               headers={"X-Dataplane-Secret": SECRET}, params={"keep_runs": 1})
    assert r.status_code == 422


def test_the_footprint_is_readable_before_deciding_to_prune(client):
    """Nobody should have to guess whether this job is worth running."""
    c, _ = client
    body = c.get("/api/v1/maintenance/snapshots", headers={"X-Dataplane-Secret": SECRET}).json()
    assert body["snapshots"] == 6
    assert body["with_payload"] == 6
    assert {k["kind"] for k in body["by_kind"]} == {"search_ads"}
