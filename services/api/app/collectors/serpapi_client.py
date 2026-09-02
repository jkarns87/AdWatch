"""Thin SerpApi client with a disk cache.

Every call = 1 search against the monthly quota (free tier: 250). The cache is keyed by the
exact parameter set so re-running a collect during development costs nothing. Delete the
cache dir (or pass fresh=True) to force a live pull.

Engines used:
  google_ads_transparency_center  -> every creative an advertiser is running
  google                          -> live paid block (`ads`) for a keyword
  google_trends                   -> TIMESERIES / RELATED_QUERIES for a keyword
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"


class SerpApiError(RuntimeError):
    pass


@dataclass
class SerpResult:
    data: dict[str, Any]
    from_cache: bool

    @property
    def search_id(self) -> str | None:
        return (self.data.get("search_metadata") or {}).get("id")


class SerpApiClient:
    def __init__(self, api_key: str | None = None, cache_dir: str | None = None, timeout_s: float | None = None):
        s = get_settings()
        self.api_key = api_key or s.serpapi_api_key
        self.cache_dir = Path(cache_dir or s.serpapi_cache_dir)
        self.timeout_s = timeout_s or s.serpapi_timeout_s
        self.searches_used = 0

    # ---- low level -------------------------------------------------------------------------

    def _cache_path(self, params: dict[str, Any]) -> Path:
        key = json.dumps(params, sort_keys=True)
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        return self.cache_dir / f"{params.get('engine', 'x')}-{digest}.json"

    def search(self, params: dict[str, Any], *, fresh: bool = False) -> SerpResult:
        if not self.api_key:
            raise SerpApiError("SERPAPI_API_KEY is not set")
        path = self._cache_path(params)
        if not fresh and path.exists():
            log.info("serpapi cache hit %s", path.name)
            return SerpResult(json.loads(path.read_text()), from_cache=True)

        q = {**params, "api_key": self.api_key}
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(SERPAPI_URL, params=q)
        if r.status_code != 200:
            raise SerpApiError(f"SerpApi {r.status_code}: {r.text[:300]}")
        data = r.json()
        if data.get("error"):
            # SerpApi returns 200 with {"error": "..."} for empty results in some engines — keep it, it's still a search.
            log.warning("serpapi soft error for %s: %s", params.get("engine"), data["error"])
        self.searches_used += 1
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return SerpResult(data, from_cache=False)

    # ---- engines ---------------------------------------------------------------------------

    def ads_transparency(
        self,
        *,
        domain: str | None = None,
        advertiser_id: str | None = None,
        region: str | None = None,
        creative_format: str | None = None,
        platform: str | None = None,
        num: int = 100,
        fresh: bool = False,
    ) -> SerpResult:
        if not (domain or advertiser_id):
            raise ValueError("domain or advertiser_id required")
        params: dict[str, Any] = {"engine": "google_ads_transparency_center", "num": num}
        if advertiser_id:
            params["advertiser_id"] = advertiser_id
        else:
            params["text"] = domain
        if region:
            params["region"] = region
        if creative_format:
            params["creative_format"] = creative_format
        if platform:
            params["platform"] = platform
        return self.search(params, fresh=fresh)

    def google_search(
        self, *, q: str, gl: str = "us", hl: str = "en", device: str = "desktop", location: str | None = None, fresh: bool = False
    ) -> SerpResult:
        params: dict[str, Any] = {"engine": "google", "q": q, "gl": gl, "hl": hl, "device": device, "google_domain": "google.com", "num": 10}
        if location:
            params["location"] = location  # e.g. "San Francisco, California, United States" — geo-targets the paid block
        return self.search(params, fresh=fresh)

    def trends_timeseries(self, *, q: str, geo: str = "US", date: str = "today 3-m", fresh: bool = False) -> SerpResult:
        params = {"engine": "google_trends", "q": q, "geo": geo, "date": date, "data_type": "TIMESERIES"}
        return self.search(params, fresh=fresh)

    def trends_related_queries(self, *, q: str, geo: str = "US", date: str = "today 3-m", fresh: bool = False) -> SerpResult:
        params = {"engine": "google_trends", "q": q, "geo": geo, "date": date, "data_type": "RELATED_QUERIES"}
        return self.search(params, fresh=fresh)
