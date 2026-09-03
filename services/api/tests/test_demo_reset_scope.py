"""reset() must not cross workspace boundaries.

Adding auth to the endpoint stopped anonymous destruction, but the delete itself
was still global — any authenticated user of any workspace could wipe every other
workspace's data. These tests pin the blast radius to the caller.
"""

from sqlalchemy import func, select

from app import models as m
from app.seed.demo import reset


def _workspace_with_data(db, ws_id: int, name: str):
    db.add(m.Workspace(id=ws_id, name=name))
    db.flush()
    w = m.Watchlist(workspace_id=ws_id, name=f"{name} watchlist", vertical="coffee", geo="US")
    db.add(w)
    db.flush()
    comp = m.Competitor(watchlist_id=w.id, name="Rival", domain=f"{name}-rival.com")
    kw = m.Keyword(watchlist_id=w.id, term="coffee subscription")
    run = m.Run(watchlist_id=w.id, status="done", searches_used=3)
    db.add_all([comp, kw, run])
    db.flush()
    db.add_all(
        [
            m.Creative(competitor_id=comp.id, creative_id=f"CR-{name}", first_seen_run_id=run.id, last_seen_run_id=run.id),
            m.SerpAd(keyword_id=kw.id, run_id=run.id, position=1, block="top", advertiser_domain="x.com"),
            m.ProductListing(keyword_id=kw.id, run_id=run.id, merchant="AShop", title="Grinder", price=99.0),
            m.TrendPoint(keyword_id=kw.id, run_id=run.id, date=__import__("datetime").date(2026, 9, 1), value=50),
            m.RelatedQuery(keyword_id=kw.id, run_id=run.id, query="q", bucket="rising"),
            m.Snapshot(run_id=run.id, watchlist_id=w.id, kind="search_ads", subject_type="keyword", subject_id=kw.id, raw={}),
            m.Change(watchlist_id=w.id, run_id=run.id, kind="creative_launched", subject_type="competitor", subject_id=comp.id, payload={}),
            m.LlmCall(workspace_id=ws_id, watchlist_id=w.id, feature="analyst", model="claude-sonnet-5"),
        ]
    )
    db.flush()
    ins = m.Insight(watchlist_id=w.id, run_id=run.id, model="claude-sonnet-5", summary="s")
    db.add(ins)
    db.flush()
    db.add(m.Alert(insight_id=ins.id, channel="webhook", target="https://hooks.example/x"))
    db.flush()
    return w


def _counts(db, ws_id: int) -> dict[str, int]:
    wl_ids = db.scalars(select(m.Watchlist.id).where(m.Watchlist.workspace_id == ws_id)).all()
    comp_ids = db.scalars(select(m.Competitor.id).where(m.Competitor.watchlist_id.in_(wl_ids))).all() if wl_ids else []
    kw_ids = db.scalars(select(m.Keyword.id).where(m.Keyword.watchlist_id.in_(wl_ids))).all() if wl_ids else []
    ins_ids = db.scalars(select(m.Insight.id).where(m.Insight.watchlist_id.in_(wl_ids))).all() if wl_ids else []
    n = lambda rows: len(rows)  # noqa: E731
    return {
        "watchlists": n(wl_ids),
        "competitors": n(comp_ids),
        "keywords": n(kw_ids),
        "creatives": n(db.scalars(select(m.Creative.id).where(m.Creative.competitor_id.in_(comp_ids))).all()) if comp_ids else 0,
        "serp_ads": n(db.scalars(select(m.SerpAd.id).where(m.SerpAd.keyword_id.in_(kw_ids))).all()) if kw_ids else 0,
        "product_listings": n(db.scalars(select(m.ProductListing.id).where(m.ProductListing.keyword_id.in_(kw_ids))).all()) if kw_ids else 0,
        "trend_points": n(db.scalars(select(m.TrendPoint.id).where(m.TrendPoint.keyword_id.in_(kw_ids))).all()) if kw_ids else 0,
        "snapshots": n(db.scalars(select(m.Snapshot.id).where(m.Snapshot.watchlist_id.in_(wl_ids))).all()) if wl_ids else 0,
        "changes": n(db.scalars(select(m.Change.id).where(m.Change.watchlist_id.in_(wl_ids))).all()) if wl_ids else 0,
        "insights": n(ins_ids),
        "alerts": n(db.scalars(select(m.Alert.id).where(m.Alert.insight_id.in_(ins_ids))).all()) if ins_ids else 0,
        "llm_calls": n(db.scalars(select(m.LlmCall.id).where(m.LlmCall.workspace_id == ws_id)).all()),
    }


def test_reset_clears_the_calling_workspace(db):
    _workspace_with_data(db, 1, "acme")
    assert _counts(db, 1)["watchlists"] == 1

    reset(db, workspace_id=1)

    after = _counts(db, 1)
    assert after == dict.fromkeys(after, 0), f"caller's own data should be gone, got {after}"


def test_reset_leaves_other_workspaces_untouched(db):
    _workspace_with_data(db, 1, "acme")
    _workspace_with_data(db, 2, "globex")
    before = _counts(db, 2)

    reset(db, workspace_id=1)

    assert _counts(db, 2) == before, "another workspace's data must survive"
    assert before["watchlists"] == 1 and before["alerts"] == 1, "fixture should have created data to protect"


def test_reset_of_an_empty_workspace_is_a_no_op(db):
    _workspace_with_data(db, 2, "globex")
    before = _counts(db, 2)
    reset(db, workspace_id=999)
    assert _counts(db, 2) == before


def test_reset_leaves_no_orphaned_rows_anywhere(db):
    """Count globally, not through the parent.

    `_counts` resolves every child through its watchlist, so once reset deletes the
    watchlist an undeleted child reads as zero and the scope tests pass while rows
    are still in the table. That is how a new table with foreign keys to keywords and
    runs was added without being added to reset(): the suite stayed green and
    production returned 500 on the first reset, because Postgres does enforce the
    constraint even though SQLite here does not.
    """
    _workspace_with_data(db, 1, "acme")
    db.flush()
    reset(db, workspace_id=1)
    db.flush()

    leftovers = {
        table.__name__: db.scalar(select(func.count()).select_from(table))
        for table in (
            m.Creative, m.SerpAd, m.ProductListing, m.TrendPoint, m.RelatedQuery,
            m.Snapshot, m.Change, m.Insight, m.Alert, m.LlmCall, m.Run, m.Keyword,
            m.Competitor, m.Watchlist,
        )
    }
    assert not {k: v for k, v in leftovers.items() if v}, f"rows survived reset: {leftovers}"
