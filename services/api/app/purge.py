"""Deleting a watchlist or a competitor, in foreign-key order.

Most of a watchlist's rows are reached through keywords and runs rather than through
the watchlist itself, and only competitors, keywords and creatives have ORM cascades.
Everything else — serp_ads, product_listings, trend_points, related_queries,
snapshots, changes, insights, alerts, llm_calls, runs — has to be removed explicitly.

The demo reset already spelled this chain out once and had already drifted:
product_listings was added to the schema and not to the chain, and reset returned 500
in production. So the chain lives here, both callers use it, and a test asserts it
covers every table reachable from a watchlist rather than trusting it to stay covered.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models as m

# Children before parents. Changes go before Insights (Change.insight_id references
# them), Alerts before Insights, and everything keyed on a keyword or run goes before
# those. Order is load-bearing.
CHAIN = (
    m.Alert,
    m.Change,
    m.Insight,
    m.RelatedQuery,
    m.TrendPoint,
    m.ProductListing,
    m.SerpAd,
    m.Creative,
    m.Snapshot,
    m.CompanyAsset,
    m.LlmCall,
    m.Run,
    m.Keyword,
    m.Competitor,
)


def delete_competitor(db: Session, competitor: m.Competitor) -> None:
    """Remove a competitor, its creatives, and the brand term that tracks its name.

    keywords.owner_competitor_id references competitors.id, so the brand term has to
    go first — adding that column made this endpoint fail on any competitor that had
    one. The customer's own market keywords are untouched: only the brand term belongs
    to the competitor.
    """
    db.execute(
        delete(m.Keyword).where(m.Keyword.owner_competitor_id == competitor.id),
        execution_options={"synchronize_session": False},
    )
    db.execute(
        delete(m.Creative).where(m.Creative.competitor_id == competitor.id),
        execution_options={"synchronize_session": False},
    )
    db.delete(competitor)


def delete_watchlist_data(db: Session, watchlist_id: int) -> None:
    """Every row belonging to one watchlist, leaving the watchlist row itself."""
    watchlists = select(m.Watchlist.id).where(m.Watchlist.id == watchlist_id)
    competitors = select(m.Competitor.id).where(m.Competitor.watchlist_id.in_(watchlists))
    keywords = select(m.Keyword.id).where(m.Keyword.watchlist_id.in_(watchlists))
    insights = select(m.Insight.id).where(m.Insight.watchlist_id.in_(watchlists))

    where = {
        m.Alert: m.Alert.insight_id.in_(insights),
        m.Change: m.Change.watchlist_id.in_(watchlists),
        m.Insight: m.Insight.watchlist_id.in_(watchlists),
        m.RelatedQuery: m.RelatedQuery.keyword_id.in_(keywords),
        m.TrendPoint: m.TrendPoint.keyword_id.in_(keywords),
        m.ProductListing: m.ProductListing.keyword_id.in_(keywords),
        m.SerpAd: m.SerpAd.keyword_id.in_(keywords),
        m.Creative: m.Creative.competitor_id.in_(competitors),
        m.Snapshot: m.Snapshot.watchlist_id.in_(watchlists),
        m.CompanyAsset: m.CompanyAsset.watchlist_id.in_(watchlists),
        m.LlmCall: m.LlmCall.watchlist_id.in_(watchlists),
        m.Run: m.Run.watchlist_id.in_(watchlists),
        m.Keyword: m.Keyword.watchlist_id.in_(watchlists),
        m.Competitor: m.Competitor.watchlist_id.in_(watchlists),
    }
    for table in CHAIN:
        db.execute(delete(table).where(where[table]), execution_options={"synchronize_session": False})


def delete_watchlist(db: Session, watchlist: m.Watchlist) -> None:
    delete_watchlist_data(db, watchlist.id)
    db.delete(watchlist)
