"""The redactor has to be reached from the paths that actually handle credentials."""

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app import models as m
from app.alerts import webhook as wh
from app.engine import collect as collect_mod

SLACK = "https://hooks.slack.invalid/services/T04ABCDEFGH/B07ZYXWVUTS/aBcDeFgHiJkLmNoPqRsTuVwX"
TOKEN = "aBcDeFgHiJkLmNoPqRsTuVwX"


@pytest.fixture
def watchlist_with_insight(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(workspace_id=1, name="Coffee", vertical="coffee", geo="US")
    db.add(w)
    db.flush()
    run = m.Run(watchlist_id=w.id, status="done")
    db.add(run)
    db.flush()
    ins = m.Insight(watchlist_id=w.id, run_id=run.id, model="claude-sonnet-5", summary="s")
    db.add(ins)
    db.flush()
    change = m.Change(
        watchlist_id=w.id, run_id=run.id, kind="creative_launched", severity="high",
        subject_type="competitor", subject_id=1, subject_label="Rival", payload={},
    )
    db.add(change)
    db.flush()
    return w, ins, [change]


def test_failed_webhook_does_not_store_the_token(db, watchlist_with_insight, monkeypatch, caplog):
    """httpx puts the full URL in its exception message. That string was written
    verbatim into alerts.error and printed to stdout."""
    w, ins, changes = watchlist_with_insight
    monkeypatch.setattr(wh, "get_settings", lambda: SimpleNamespace(webhook_url=SLACK, dashboard_url="https://adwatch.dev"))

    def boom(*a, **k):
        raise httpx.HTTPStatusError(
            f"Client error '404 Not Found' for url '{SLACK}'",
            request=httpx.Request("POST", SLACK),
            response=httpx.Response(404, request=httpx.Request("POST", SLACK)),
        )

    monkeypatch.setattr(wh.httpx, "post", boom)

    wh.dispatch_insight(db, w, ins, changes)

    db.flush()  # the fixture session is autoflush=False
    alert = db.scalars(select(m.Alert)).one()
    assert alert.status == "failed"
    assert TOKEN not in (alert.error or ""), "the webhook token reached the database"
    assert TOKEN not in caplog.text, "the webhook token reached the logs"


def test_a_failed_collect_does_not_store_credentials(db, monkeypatch):
    """run.error is surfaced straight back to the client as a 502 body."""
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(workspace_id=1, name="Coffee", vertical="coffee", geo="US")
    db.add(w)
    db.flush()
    db.add(m.Keyword(watchlist_id=w.id, term="coffee"))
    db.flush()

    from app.collectors.serpapi_client import SerpApiError

    class ExplodingClient:
        """Every collector call fails with a message carrying the API key."""

        searches_used = 0

        def __getattr__(self, _name):
            def boom(*a, **k):
                raise SerpApiError(
                    "SerpApi 401 for https://serpapi.com/search.json?engine=google&api_key=" + "d" * 64
                )

            return boom

    monkeypatch.setattr(collect_mod, "SerpApiClient", lambda *a, **k: ExplodingClient())

    run, _, _ = collect_mod.run_collect(db, w)

    assert run.status == "failed"
    assert "d" * 64 not in (run.error or ""), "the SerpApi key reached run.error"
