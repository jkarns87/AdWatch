"""Synthetic SerpApi client. Produces canned responses in the real SerpApi shapes so the
*entire* pipeline (normalize -> upsert -> diff -> analyze) runs exactly as in production,
with zero quota and zero real brands. Responses vary by run index so run 2 diffs against run 1.

Fictitious advertisers only. Domains use .example (RFC 2606) so nothing resolves."""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any

from ..collectors.serpapi_client import SerpResult

FICTIONAL_COMPETITORS = [
    {"name": "BeanLoop", "domain": "beanloop.example"},
    {"name": "RoastNest", "domain": "roastnest.example"},
    {"name": "DripCrate", "domain": "dripcrate.example"},
]
FICTIONAL_KEYWORDS = ["coffee subscription", "specialty coffee beans", "cold brew delivery", "best coffee beans online", "coffee gift box"]
OUTSIDERS = ["brewdrop.example", "mugbox.example", "grindhaus.example", "pourfolk.example"]

HEADLINES = [
    "Roasted to Order, Delivered Weekly",
    "First Bag Free",
    "Single-Origin, Small-Batch",
    "Fresh Beans From $14.99/Bag",
    "Skip Any Week, Cancel Anytime",
    "New: Cold Brew Concentrate",
    "Bay Area Roasted, Shipped Nationwide",
    "Decaf That Actually Tastes Good",
]


def _rng(*parts: Any) -> random.Random:
    seed = int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)
    return random.Random(seed)


class SyntheticSerpApiClient:
    """Drop-in for SerpApiClient. `run_index` is 0 for baseline, 1 for the 'overnight' run."""

    def __init__(self, run_index: int = 0):
        self.run_index = run_index
        self.searches_used = 0

    def _res(self, data: dict[str, Any]) -> SerpResult:
        self.searches_used += 1
        data.setdefault("search_metadata", {"id": f"synthetic-{self.run_index}-{self.searches_used}", "status": "Success"})
        return SerpResult(data, from_cache=False)

    # ---- ads transparency ---------------------------------------------------------------------

    def ads_transparency(self, *, domain=None, advertiser_id=None, fresh=False, **_) -> SerpResult:
        r = _rng("ads", domain)
        base_n = r.randint(6, 12)
        today = date.today()
        creatives = []
        for i in range(base_n):
            fmt = r.choice(["text", "text", "image", "video"])
            first = today - timedelta(days=r.randint(20, 120))
            creatives.append(self._creative(domain, f"CR{abs(hash((domain, i))) % 10**12:012d}", fmt, first, today))
        if self.run_index >= 1:
            r2 = _rng("ads-run2", domain)
            # competitor-specific stories: one launches a video burst, one drops a few, one is quiet
            idx = [c["domain"] for c in FICTIONAL_COMPETITORS].index(domain) if domain in [c["domain"] for c in FICTIONAL_COMPETITORS] else 0
            if idx == 1:  # PlateNest: surge of 4 video creatives
                for j in range(4):
                    creatives.append(self._creative(domain, f"CRV{abs(hash((domain, 'v', j))) % 10**11:011d}", "video", today - timedelta(days=1), today))
            elif idx == 0:  # FreshCrate: drops 2 old, launches 1 new discount ad
                creatives = creatives[2:]
                creatives.append(self._creative(domain, f"CRN{abs(hash((domain, 'n'))) % 10**11:011d}", "text", today - timedelta(days=1), today, headline="First Bag Free"))
            else:  # KitchenLoop: launches one image ad
                if r2.random() > 0.2:
                    creatives.append(self._creative(domain, f"CRI{abs(hash((domain, 'i'))) % 10**11:011d}", "image", today, today))
        return self._res({"ad_creatives": creatives})

    @staticmethod
    def _creative(domain: str, cid: str, fmt: str, first: date, last: date, headline: str | None = None) -> dict[str, Any]:
        r = _rng("cr", cid)
        c: dict[str, Any] = {
            "id": cid,
            "advertiser": domain.split(".")[0].title(),
            "advertiser_id": "AR" + hashlib.md5(domain.encode()).hexdigest()[:18].upper(),
            "format": fmt,
            "platform": r.choice(["SEARCH", "SEARCH", "YOUTUBE", "SHOPPING"]) if fmt != "text" else "SEARCH",
            "target_domain": domain,
            "first_shown": first.isoformat(),
            "last_shown": last.isoformat(),
            "details_link": f"https://adstransparency.google.com/advertiser/x/creative/{cid}",
        }
        if fmt == "text":
            c["headline"] = headline or r.choice(HEADLINES)
            c["description"] = "Fresh, pre-portioned ingredients and easy recipes delivered weekly."
        else:
            c["image"] = f"https://placehold.co/300x250/1f2937/ffffff?text={fmt.upper()}+{cid[-4:]}"
        return c

    # ---- google search (paid block) -----------------------------------------------------------

    def google_search(self, *, q: str, gl="us", hl="en", device="desktop", location=None, fresh=False) -> SerpResult:
        r = _rng("serp", q)
        comps = [c["domain"] for c in FICTIONAL_COMPETITORS]
        pool = comps + r.sample(OUTSIDERS, 2)
        r.shuffle(pool)
        lineup = pool[:4]
        if self.run_index >= 1:
            r2 = _rng("serp-run2", q)
            if q == "cold brew delivery":
                newcomer = next(o for o in OUTSIDERS if o not in lineup)  # guaranteed new advertiser takes #1
                lineup = [newcomer] + lineup[:3]
            elif q == "coffee subscription":
                lineup = lineup[1:] + lineup[:1]  # rotate -> position shifts
            elif r2.random() > 0.5 and len(lineup) > 3:
                lineup = lineup[:3]  # someone left
        ads = []
        for i, d in enumerate(lineup):
            block = "top" if i < 3 else "bottom"
            ads.append(
                {
                    "position": i + 1 if block == "top" else 1,
                    "block_position": block,
                    "title": f"{d.split('.')[0].title()} — {r.choice(HEADLINES)}",
                    "link": f"https://{d}/?utm_source=google",
                    "displayed_link": f"https://www.{d}",
                    "description": "Specialty coffee subscription. Roasted this week, shipped free.",
                }
            )
        return self._res({"ads": ads, "organic_results": []})

    # ---- trends -------------------------------------------------------------------------------

    def trends_timeseries(self, *, q: str, geo="US", date="today 3-m", fresh=False) -> SerpResult:  # noqa: A002
        r = _rng("trend", q)
        today = date_today()
        pts = []
        base = r.randint(30, 60)
        for i in range(12, -1, -1):
            d = today - timedelta(weeks=i)
            v = max(5, min(100, base + r.randint(-8, 8)))
            pts.append({"date": d.strftime("%b %-d, %Y"), "timestamp": str(int(__import__("time").mktime(d.timetuple()))), "values": [{"query": q, "value": str(v), "extracted_value": v}]})
        if self.run_index >= 1 and q == "cold brew delivery":
            last = pts[-1]["values"][0]
            last["extracted_value"] = min(100, int(last["extracted_value"] * 2.1))
            last["value"] = str(last["extracted_value"])
        return self._res({"interest_over_time": {"timeline_data": pts}})

    def trends_related_queries(self, *, q: str, geo="US", date="today 3-m", fresh=False) -> SerpResult:  # noqa: A002
        r = _rng("rel", q)
        rising = []
        for suffix in ("reviews", "coupon", "near me"):
            v = r.randint(40, 250)
            rising.append({"query": f"{q} {suffix}", "value": f"+{v}%", "extracted_value": v})
        cost = r.randint(30, 80)
        top = [{"query": f"best {q}", "value": "100", "extracted_value": 100}, {"query": f"{q} cost", "value": str(cost), "extracted_value": cost}]
        if self.run_index >= 1 and q in ("cold brew delivery", "coffee gift box"):
            rising.insert(0, {"query": "coffee gift box for dad" if q == "coffee gift box" else "cold brew delivery san francisco", "value": "Breakout", "extracted_value": None})
        return self._res({"related_queries": {"rising": rising, "top": top}})


def date_today() -> date:
    return date.today()
