"""Provider key health — is the key valid, and how much quota is left?

`/health` reported `serpapi_key: true` for the literal string "apiworld2026", because
it only asked `bool(...)`. Every collect returned 502 while the health check stayed
green. Presence is not validity; this asks SerpApi.

`account.json` costs no search quota, but it *is* a network call, so results are cached
per key. The container healthcheck polls every 15 seconds — nothing here should turn a
status poll into thousands of outbound requests a day, or couple container liveness to
SerpApi's uptime.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from .workspace_secrets import resolve_key

log = logging.getLogger(__name__)

ACCOUNT_URL = "https://serpapi.com/account.json"
TTL_SECONDS = 60.0
TIMEOUT_SECONDS = 8.0

# Swapped for an httpx.MockTransport in tests; None means "real network".
_transport_for_tests: httpx.BaseTransport | None = None

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_key(api_key: str) -> str:
    """Hash rather than store the key — this dict is process memory that ends up in
    tracebacks and heap dumps."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def serpapi_status(db: Session, *, workspace_id: int, platform_key: str) -> dict[str, Any]:
    """Validity and remaining quota for whichever key this workspace would actually use."""
    workspace_key = resolve_key(db, workspace_id=workspace_id, kind="serpapi", fallback="")
    api_key = workspace_key or platform_key
    source = "workspace" if workspace_key else ("platform" if platform_key else "none")

    if not api_key:
        return {**_blank("unset"), "key_source": "none", "cached": False}

    ck = _cache_key(api_key)
    hit = _cache.get(ck)
    if hit and (time.monotonic() - hit[0]) < TTL_SECONDS:
        return {**hit[1], "key_source": source, "cached": True}

    result = _probe(api_key)
    _cache[ck] = (time.monotonic(), result)
    return {**result, "key_source": source, "cached": False}


ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"


def validate_key(kind: str, api_key: str) -> str:
    """Ask the provider whether this key works. Returns ok | invalid | unreachable.

    `unreachable` is deliberately distinct from `invalid`: provider downtime is not
    proof of a bad key, and refusing to save during a wobble would make the settings
    page unusable.
    """
    try:
        if kind == "serpapi":
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=_transport_for_tests) as c:
                r = c.get(ACCOUNT_URL, params={"api_key": api_key})
        elif kind == "anthropic":
            # /v1/models authenticates without spending tokens.
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=_transport_for_tests) as c:
                r = c.get(
                    ANTHROPIC_MODELS_URL,
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
        else:
            raise ValueError(f"unknown provider {kind!r}")
    except httpx.HTTPError as e:
        log.warning("%s key validation unreachable: %s", kind, e.__class__.__name__)
        return "unreachable"

    if r.status_code in (401, 403):
        return "invalid"
    if r.status_code == 200:
        return "ok"
    log.warning("%s key validation returned %s", kind, r.status_code)
    return "unreachable"


def _blank(status: str) -> dict[str, Any]:
    """Every branch returns the same keys, so callers never need to guess which
    fields exist for which status."""
    return {
        "status": status,
        "plan": None,
        "searches_left": None,
        "plan_searches_left": None,
        "extra_credits": None,
        "searches_per_month": None,
        "used_this_month": None,
    }


def _probe(api_key: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, transport=_transport_for_tests) as client:
            r = client.get(ACCOUNT_URL, params={"api_key": api_key})
    except httpx.HTTPError as e:
        # SerpApi being down must not read as a bad key — the operator response differs.
        log.warning("serpapi account check unreachable: %s", e.__class__.__name__)
        return _blank("unreachable")

    if r.status_code == 401:
        return _blank("invalid")
    if r.status_code != 200:
        log.warning("serpapi account check returned %s", r.status_code)
        return _blank("unreachable")

    data = r.json()
    # total_searches_left = plan_searches_left + extra_credits. Reporting only the
    # total against searches_per_month produces nonsense like "14370 / 250" — this
    # account has 14,120 granted credits on top of a 250/month Free Plan. Callers
    # need both numbers to render anything truthful.
    left = data.get("total_searches_left")
    # account.json echoes api_key and account_email back. Pick fields explicitly;
    # never spread the response into an API payload.
    return {
        "status": "exhausted" if left == 0 else "ok",
        "plan": data.get("plan_name"),
        "searches_left": left,  # what you can actually spend
        "plan_searches_left": data.get("plan_searches_left"),
        "extra_credits": data.get("extra_credits"),
        "searches_per_month": data.get("searches_per_month"),
        "used_this_month": data.get("this_month_usage"),
    }
