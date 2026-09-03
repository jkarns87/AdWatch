"""Deleting a competitor or a whole watchlist, without leaving orphans behind.

Two things make this more than a one-liner.

Brand terms carry a foreign key to the competitor whose name they track, so deleting
a competitor with the ORM alone violates it — the feature that added the column made
an existing endpoint fail.

And a watchlist owns rows in eleven tables, most of them reached through keywords and
runs rather than through the watchlist itself. Only competitors, keywords and
creatives have ORM cascades; serp_ads, product_listings, trend_points, related_queries,
snapshots, changes, insights, alerts and runs do not. The demo reset already had to
spell that chain out and had already drifted once — product_listings was added to the
schema and not to the chain, and reset returned 500 in production until it was found.
So there is one chain, in one place, used by both.
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from app import models as m
from app import purge
from app.engine import brand


@pytest.fixture
def watchlist(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="coffee", geo="US")
    db.add(w)
    db.flush()
    comp = m.Competitor(id=10, watchlist_id=1, name="Rival", domain="rival.com")
    kw = m.Keyword(id=20, watchlist_id=1, term="coffee subscription")
    db.add_all([comp, kw])
    db.flush()
    db.add(m.Keyword(id=21, watchlist_id=1, term="Rival", kind="brand", owner_competitor_id=10))
    run = m.Run(id=30, watchlist_id=1, status="done", searches_used=5)
    db.add(run)
    db.flush()
    db.add_all([
        m.Creative(competitor_id=10, creative_id="CR1", first_seen_run_id=30, last_seen_run_id=30),
        m.SerpAd(keyword_id=20, run_id=30, position=1, block="top", advertiser_domain="rival.com"),
        m.ProductListing(keyword_id=20, run_id=30, merchant="M", title="T", price=9.99),
        m.TrendPoint(keyword_id=20, run_id=30, date=date(2026, 9, 1), value=50),
        m.RelatedQuery(keyword_id=20, run_id=30, query="q", bucket="rising"),
        m.Snapshot(run_id=30, watchlist_id=1, kind="search_ads", subject_type="keyword", subject_id=20, raw={}),
        m.Change(watchlist_id=1, run_id=30, kind="creative_launched", subject_type="competitor", subject_id=10, payload={}),
        m.LlmCall(workspace_id=1, watchlist_id=1, feature="analyst", model="claude-sonnet-5"),
    ])
    db.flush()
    ins = m.Insight(watchlist_id=1, run_id=30, model="claude-sonnet-5", summary="s")
    db.add(ins)
    db.flush()
    db.add(m.Alert(insight_id=ins.id, channel="webhook", target="https://hooks.example/x"))
    db.flush()
    return w


def _count(db, table) -> int:
    return db.scalar(select(func.count()).select_from(table))


# ---- competitors ---------------------------------------------------------------------------------


def test_deleting_a_competitor_takes_its_brand_term_with_it(db, watchlist):
    """keywords.owner_competitor_id references competitors.id, so the brand term has
    to go first or the delete violates the constraint."""
    purge.delete_competitor(db, db.get(m.Competitor, 10))
    db.flush()
    assert _count(db, m.Competitor) == 0
    assert db.scalars(select(m.Keyword).where(m.Keyword.kind == "brand")).all() == []


def test_deleting_a_competitor_keeps_the_market_keywords(db, watchlist):
    """Only the brand term belongs to the competitor. The keywords the customer
    chose are theirs and survive."""
    purge.delete_competitor(db, db.get(m.Competitor, 10))
    db.flush()
    assert [k.term for k in db.scalars(select(m.Keyword)).all()] == ["coffee subscription"]


def test_deleting_a_competitor_removes_its_creatives(db, watchlist):
    purge.delete_competitor(db, db.get(m.Competitor, 10))
    db.flush()
    assert _count(db, m.Creative) == 0


def test_the_brand_term_is_recreated_on_the_next_run_only_if_the_competitor_returns(db, watchlist):
    """Provisioning is driven by the competitor list, so a deleted competitor stays
    gone rather than resurrecting itself on the next collect."""
    purge.delete_competitor(db, db.get(m.Competitor, 10))
    db.flush()
    db.refresh(watchlist)
    brand.ensure_brand_terms(db, watchlist)
    db.flush()
    assert db.scalars(select(m.Keyword).where(m.Keyword.kind == "brand")).all() == []


# ---- watchlists ----------------------------------------------------------------------------------


def test_deleting_a_watchlist_leaves_no_orphans_anywhere(db, watchlist):
    """Counted globally. Scoping the check through the watchlist would report zero
    for every orphan, because the parent is gone — the exact blind spot that let
    product_listings drift out of the demo reset chain."""
    purge.delete_watchlist(db, watchlist)
    db.flush()
    leftovers = {
        t.__name__: _count(db, t)
        for t in (m.Creative, m.SerpAd, m.ProductListing, m.TrendPoint, m.RelatedQuery,
                  m.Snapshot, m.Change, m.Insight, m.Alert, m.LlmCall, m.Run, m.Keyword,
                  m.Competitor, m.Watchlist)
    }
    assert not {k: v for k, v in leftovers.items() if v}, f"rows survived: {leftovers}"


def test_deleting_a_watchlist_leaves_other_watchlists_alone(db, watchlist):
    other = m.Watchlist(id=2, workspace_id=1, name="Tea", vertical="tea", geo="US")
    db.add(other)
    db.flush()
    db.add(m.Keyword(watchlist_id=2, term="loose leaf tea"))
    db.flush()

    purge.delete_watchlist(db, watchlist)
    db.flush()
    assert [w.name for w in db.scalars(select(m.Watchlist)).all()] == ["Tea"]
    assert [k.term for k in db.scalars(select(m.Keyword)).all()] == ["loose leaf tea"]


def test_deleting_an_empty_watchlist_is_not_an_error(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(id=5, workspace_id=1, name="Empty", vertical="x", geo="US")
    db.add(w)
    db.flush()
    purge.delete_watchlist(db, w)
    db.flush()
    assert _count(db, m.Watchlist) == 0


def test_the_delete_chain_covers_every_table_that_points_at_a_watchlist(db):
    """A new table with a foreign key into this graph must be added to the chain.
    This asserts the chain is complete rather than trusting it to stay complete —
    it already drifted once."""
    covered = {t.__tablename__ for t in purge.CHAIN}
    reachable = set()
    for table in m.Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name in {"watchlists", "keywords", "competitors", "runs", "insights"}:
                reachable.add(table.name)
    missing = reachable - covered - {"watchlists"}
    assert not missing, f"tables reachable from a watchlist but absent from the delete chain: {missing}"
