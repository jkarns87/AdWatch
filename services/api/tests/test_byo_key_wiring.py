"""A stored workspace key must actually be the one used to call the provider.

Storing keys nobody reads is theatre — these assert the resolver is reached from
the collect and analyze paths, and that the platform key is used when a
workspace has not supplied one.
"""

from contextlib import suppress
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from app import crypto
from app import models as m
from app import workspace_secrets as sec
from app.engine import analyze as analyze_mod
from app.engine import collect as collect_mod

WORKSPACE_SERPAPI = "1" * 64
PLATFORM_SERPAPI = "9" * 64


@pytest.fixture(autouse=True)
def keyed(monkeypatch):
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    yield
    crypto._fernet = None


@pytest.fixture
def watchlist(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(workspace_id=1, name="Coffee", vertical="coffee", geo="US")
    db.add(w)
    db.flush()
    db.add(m.Keyword(watchlist_id=w.id, term="coffee"))
    db.flush()
    return w


def _capture_client(seen: list[str]):
    class Client:
        searches_used = 0

        def __init__(self, *a, api_key: str = "", **k):
            seen.append(api_key)

        def __getattr__(self, _n):
            def noop(*a, **k):
                raise RuntimeError("stop after construction")

            return noop

    return Client


def test_collect_uses_the_workspace_key_when_present(db, watchlist, monkeypatch):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=WORKSPACE_SERPAPI)
    seen: list[str] = []
    monkeypatch.setattr(collect_mod, "SerpApiClient", _capture_client(seen))
    monkeypatch.setattr(
        collect_mod, "get_settings", lambda: SimpleNamespace(serpapi_api_key=PLATFORM_SERPAPI)
    )

    # The stub aborts once constructed; construction is the behaviour under test.
    with suppress(RuntimeError):
        collect_mod.run_collect(db, watchlist)

    assert seen and seen[0] == WORKSPACE_SERPAPI, "the workspace's own key should have been used"


def test_collect_falls_back_to_the_platform_key(db, watchlist, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(collect_mod, "SerpApiClient", _capture_client(seen))
    monkeypatch.setattr(
        collect_mod, "get_settings", lambda: SimpleNamespace(serpapi_api_key=PLATFORM_SERPAPI)
    )

    with suppress(RuntimeError):
        collect_mod.run_collect(db, watchlist)

    assert seen and seen[0] == PLATFORM_SERPAPI


def test_analyze_uses_the_workspace_anthropic_key(db, watchlist, monkeypatch):
    sec.set_secret(db, workspace_id=1, kind="anthropic", plaintext="sk-ant-workspace-key")
    seen: list[str] = []

    class Analyst:
        def __init__(self, api_key: str = "", model: str | None = None):
            seen.append(api_key)

        def analyze(self, context, changes):
            return []

    monkeypatch.setattr(analyze_mod, "Analyst", Analyst)
    monkeypatch.setattr(
        analyze_mod,
        "get_settings",
        lambda: SimpleNamespace(alert_dispatcher="none", anthropic_api_key="sk-ant-platform-key"),
    )
    db.add(
        m.Change(
            watchlist_id=watchlist.id,
            run_id=db.scalar(__import__("sqlalchemy").select(m.Run.id)) or _mkrun(db, watchlist),
            kind="creative_launched",
            severity="high",
            subject_type="competitor",
            subject_id=1,
            subject_label="Rival",
            payload={},
        )
    )
    db.flush()

    analyze_mod.run_analyze(db, watchlist)

    assert seen and seen[0] == "sk-ant-workspace-key"


def _mkrun(db, watchlist):
    run = m.Run(watchlist_id=watchlist.id, status="done")
    db.add(run)
    db.flush()
    return run.id
