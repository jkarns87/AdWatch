"""SerpApi key health — validity and remaining quota, not mere presence.

/health reported `serpapi_key: true` for the string "apiworld2026" because it only
asked `bool(...)`. Collection 401'd on every run while the health check stayed green.
This asks SerpApi.
"""


import httpx
import pytest
from cryptography.fernet import Fernet

from app import crypto, providers
from app import workspace_secrets as sec

PLATFORM_KEY = "9" * 64
WORKSPACE_KEY = "1" * 64

ACCOUNT_OK = {
    "account_id": "acc_123",
    "api_key": WORKSPACE_KEY,  # SerpApi echoes the key back — it must not be passed through
    "account_email": "someone@example.com",
    "plan_name": "Free Plan",
    "searches_per_month": 250,
    "plan_searches_left": 184,
    "extra_credits": 14120,
    "total_searches_left": 14304,
    "this_month_usage": 66,
}


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    providers._cache.clear()
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    yield
    providers._cache.clear()
    crypto._fernet = None


def _transport(status: int, body: dict | None = None, boom: Exception | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if boom:
            raise boom
        return httpx.Response(status, json=body or {})

    return httpx.MockTransport(handler)


def test_no_key_anywhere_reports_unset_without_calling_out(db, monkeypatch):
    calls: list[str] = []

    def should_not_run(*a, **k):
        calls.append("called")
        raise AssertionError("no network call should be made without a key")

    monkeypatch.setattr(providers.httpx, "Client", should_not_run)
    out = providers.serpapi_status(db, workspace_id=1, platform_key="")
    assert out["status"] == "unset"
    assert out["key_source"] == "none"
    assert calls == []


def test_invalid_key_is_reported_as_invalid(db, monkeypatch):
    monkeypatch.setattr(providers, "_transport_for_tests", _transport(401, {"error": "Invalid API key."}))
    out = providers.serpapi_status(db, workspace_id=1, platform_key="apiworld2026")
    assert out["status"] == "invalid"


def test_valid_key_reports_remaining_quota(db, monkeypatch):
    monkeypatch.setattr(providers, "_transport_for_tests", _transport(200, ACCOUNT_OK))
    out = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert out["status"] == "ok"
    assert out["searches_left"] == 14304, "the total is what you can actually spend"
    assert out["plan_searches_left"] == 184
    assert out["extra_credits"] == 14120
    assert out["searches_per_month"] == 250
    assert out["used_this_month"] == 66
    assert out["plan"] == "Free Plan"


def test_the_account_response_echoes_the_key_and_it_must_not_be_returned(db, monkeypatch):
    monkeypatch.setattr(providers, "_transport_for_tests", _transport(200, ACCOUNT_OK))
    out = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert WORKSPACE_KEY not in str(out)
    assert "api_key" not in out
    assert "account_email" not in out, "no need to surface the account holder's email"


def test_exhausted_quota_is_distinct_from_invalid(db, monkeypatch):
    """Exhausted means the *total* is gone. A used-up plan allowance with extra
    credits remaining is still usable — reporting that as exhausted would pause
    collection while 14,000 searches sat unspent."""
    monkeypatch.setattr(
        providers, "_transport_for_tests",
        _transport(200, {**ACCOUNT_OK, "total_searches_left": 0, "plan_searches_left": 0, "extra_credits": 0}),
    )
    out = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert out["status"] == "exhausted"
    assert out["searches_left"] == 0


def test_plan_allowance_spent_but_credits_left_is_still_ok(db, monkeypatch):
    monkeypatch.setattr(
        providers, "_transport_for_tests",
        _transport(200, {**ACCOUNT_OK, "plan_searches_left": 0, "extra_credits": 14120, "total_searches_left": 14120}),
    )
    out = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert out["status"] == "ok"
    assert out["plan_searches_left"] == 0 and out["extra_credits"] == 14120


def test_a_network_failure_is_unreachable_not_a_crash(db, monkeypatch):
    monkeypatch.setattr(providers, "_transport_for_tests", _transport(0, boom=httpx.ConnectError("dns")))
    out = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert out["status"] == "unreachable"


def test_the_workspace_key_is_preferred_and_reported_as_such(db, monkeypatch):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=WORKSPACE_KEY)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params.get("api_key", ""))
        return httpx.Response(200, json=ACCOUNT_OK)

    monkeypatch.setattr(providers, "_transport_for_tests", httpx.MockTransport(handler))
    out = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert seen == [WORKSPACE_KEY]
    assert out["key_source"] == "workspace"


def test_the_result_is_cached_so_polling_does_not_hammer_serpapi(db, monkeypatch):
    """The container healthcheck hits /health every 15s. Nothing in this codebase
    should turn a status poll into 5,760 outbound calls a day."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=ACCOUNT_OK)

    monkeypatch.setattr(providers, "_transport_for_tests", httpx.MockTransport(handler))
    providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    second = providers.serpapi_status(db, workspace_id=1, platform_key=PLATFORM_KEY)
    assert len(calls) == 1, "second call within the TTL should be served from cache"
    assert second["cached"] is True
