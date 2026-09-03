"""Plan catalog + SerpApi cost model. Single source of truth for the Usage page and docs/COST_MODEL.md.

Every SerpApi call is one "search". A watchlist with C competitors and K keywords costs, per full run:
    C   (Ads Transparency Center, one per competitor)
  + K   (Google Search paid block, one per keyword)
  + K   (Google Trends TIMESERIES, one per keyword)          -> ceil(K/5) when batched, Trends allows 5 q per call
  + K   (Google Trends RELATED_QUERIES, one per keyword)
The cadence per source is what a plan really sells: creatives change daily, SERP ads change by hour,
demand moves daily, related queries move weekly.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

# blended $/search at the SerpApi tier we'd buy at that scale (Production 15k = $0.010, Big Data 30k = $0.0092)
RATE_PER_SEARCH_USD = 0.01
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Cadence:
    creatives_per_day: float  # Ads Transparency Center pulls per competitor per day
    serp_per_day: float  # Google Search paid-block samples per keyword per day
    trends_per_day: float  # Trends TIMESERIES pulls (batched 5 keywords/call) per day
    related_per_week: float  # Trends RELATED_QUERIES pulls per keyword per week


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_usd: int
    watchlists: int
    competitors_per_watchlist: int
    keywords_per_watchlist: int
    searches_per_month: int  # hard budget for the workspace; collection pauses when exhausted
    cadence: Cadence
    blurb: str


PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free",
        name="Free",
        price_usd=0,
        watchlists=1,
        competitors_per_watchlist=2,
        keywords_per_watchlist=3,
        searches_per_month=250,
        cadence=Cadence(creatives_per_day=1, serp_per_day=1, trends_per_day=1, related_per_week=1),
        blurb="One watchlist, daily refresh. Enough to see the product work.",
    ),
    "team": Plan(
        key="team",
        name="Team",
        price_usd=79,
        watchlists=3,
        competitors_per_watchlist=5,
        keywords_per_watchlist=10,
        searches_per_month=3000,
        cadence=Cadence(creatives_per_day=1, serp_per_day=2, trends_per_day=1, related_per_week=1),
        blurb="Three watchlists, SERP sampled twice a day, in-app + Slack/Teams/Discord/email alerts.",
    ),
    "agency": Plan(
        key="agency",
        name="Agency",
        price_usd=299,
        watchlists=10,
        competitors_per_watchlist=10,
        keywords_per_watchlist=15,
        searches_per_month=15000,
        cadence=Cadence(creatives_per_day=1, serp_per_day=2, trends_per_day=1, related_per_week=1),
        blurb="Ten client watchlists, per-client destinations, priority collection.",
    ),
}

# what the scheduler does today: everything, every 6 hours, no Trends batching
CURRENT_CADENCE = Cadence(creatives_per_day=4, serp_per_day=4, trends_per_day=4, related_per_week=28)


def searches_per_run(competitors: int, keywords: int, *, batch_trends: bool = False) -> int:
    trends = math.ceil(keywords / 5) if batch_trends else keywords
    return competitors + keywords + trends + keywords


def searches_per_month(competitors: int, keywords: int, cadence: Cadence, *, batch_trends: bool = True) -> int:
    trends_calls = math.ceil(keywords / 5) if batch_trends else keywords
    creatives = competitors * cadence.creatives_per_day * DAYS_PER_MONTH
    serp = keywords * cadence.serp_per_day * DAYS_PER_MONTH
    trends = trends_calls * cadence.trends_per_day * DAYS_PER_MONTH
    related = keywords * cadence.related_per_week * (DAYS_PER_MONTH / 7)
    return int(round(creatives + serp + trends + related))


def cost_usd(searches: int, rate: float = RATE_PER_SEARCH_USD) -> float:
    return round(searches * rate, 2)


def plan_dict(p: Plan) -> dict:
    d = asdict(p)
    d["cadence"] = asdict(p.cadence)
    return d


def plan_for(key: str | None) -> Plan:
    """Resolve a plan key to its limits.

    An unrecognised key falls back to the most restrictive plan rather than the most
    permissive. The key comes from the control plane, so an unknown value means the
    two sides disagree about what plans exist — and guessing generously there would
    hand out limits nobody is paying for.
    """
    return PLANS.get((key or "").strip().lower(), PLANS["free"])
