"""The weekly report as a forwardable artifact.

Two additions and one regression fix.

`total_days_shown` is on every creative the Ads Transparency Center returns and was
being stored and never surfaced. Days actually served is the strongest performance
proxy public ad-library data offers — an advertiser does not keep paying to run a
creative that is not working — and the report had no notion of it, so a reader saw
what changed this week and nothing about what is proven.

Brand defence is the other thing a weekly brief should lead with and could not, since
conquesting fires as an event only when it starts or stops.

The regression: brand terms live in the keywords table, so every consumer that
iterated `watchlist.keywords` started treating them as market keywords the moment
brand tracking shipped. They appeared in the keyword list in the UI and in the
report's share-of-voice section, where a brand term's paid block is a different
question entirely.
"""

from datetime import date

import pytest

from app import models as m
from app.reports.data import PROVEN_PER_COMPETITOR, build_report_data


@pytest.fixture
def watchlist(db):
    db.add(m.Workspace(id=1, name="acme"))
    db.flush()
    w = m.Watchlist(id=1, workspace_id=1, name="Coffee", vertical="coffee", geo="US")
    db.add(w)
    db.flush()
    a = m.Competitor(id=10, watchlist_id=1, name="Alpha", domain="alpha.com")
    b = m.Competitor(id=11, watchlist_id=1, name="Beta", domain="beta.com")
    db.add_all([a, b])
    db.flush()
    db.add_all([
        m.Keyword(id=20, watchlist_id=1, term="coffee subscription"),
        m.Keyword(id=21, watchlist_id=1, term="Alpha", kind="brand", owner_competitor_id=10),
    ])
    # finished_at is deliberately unset: SQLite drops tzinfo, so a value written here
    # comes back naive and the period filter compares it against an aware datetime.
    # Postgres with DateTime(timezone=True) returns aware values, so this is an
    # artifact of the test database rather than something the report has to handle.
    run = m.Run(id=30, watchlist_id=1, status="done", searches_used=5)
    db.add(run)
    db.flush()
    db.add_all([
        # A long-running workhorse, a middling one, and a brand-new test.
        m.Creative(competitor_id=10, creative_id="CR-EVERGREEN", format="text", total_days_shown=947,
                   first_shown=date(2024, 1, 1), last_shown=date(2026, 9, 1),
                   first_seen_run_id=30, last_seen_run_id=30, active=True),
        m.Creative(competitor_id=11, creative_id="CR-MID", format="image", total_days_shown=120,
                   first_shown=date(2026, 5, 1), last_shown=date(2026, 9, 1),
                   first_seen_run_id=30, last_seen_run_id=30, active=True),
        m.Creative(competitor_id=10, creative_id="CR-TEST", format="text", total_days_shown=3,
                   first_shown=date(2026, 8, 30), last_shown=date(2026, 9, 1),
                   first_seen_run_id=30, last_seen_run_id=30, active=True),
        # Retired: should not be presented as proven.
        m.Creative(competitor_id=10, creative_id="CR-DEAD", format="text", total_days_shown=800,
                   first_shown=date(2023, 1, 1), last_shown=date(2024, 1, 1),
                   first_seen_run_id=30, last_seen_run_id=30, active=False),
        # Someone bidding on Alpha's own name, and Alpha absent.
        m.SerpAd(keyword_id=21, run_id=30, position=1, block="top", advertiser_domain="beta.com", title="Switch to Beta"),
        m.SerpAd(keyword_id=20, run_id=30, position=1, block="top", advertiser_domain="alpha.com", title="Alpha coffee"),
        m.Snapshot(run_id=30, watchlist_id=1, kind="search_ads", subject_type="keyword", subject_id=21, raw={}),
    ])
    db.commit()
    return w


# ---- proven creatives ----------------------------------------------------------------------------


def test_the_report_ranks_creatives_by_days_actually_served(watchlist, db):
    d = build_report_data(db, watchlist, days=7)
    assert [c["creative_id"] for c in d["proven_creatives"]] == ["CR-EVERGREEN", "CR-MID", "CR-TEST"]


def test_a_retired_creative_is_not_presented_as_proven(watchlist, db):
    """It ran 800 days and stopped. That is history, not what the competitor is
    betting on now, and a weekly brief that led with it would mislead."""
    d = build_report_data(db, watchlist, days=7)
    assert "CR-DEAD" not in {c["creative_id"] for c in d["proven_creatives"]}


def test_each_proven_creative_names_its_advertiser(watchlist, db):
    d = build_report_data(db, watchlist, days=7)
    top = d["proven_creatives"][0]
    assert top["competitor"] == "Alpha"
    assert top["days"] == 947
    assert top["format"] == "text"


def test_creatives_without_a_day_count_do_not_lead_the_ranking(watchlist, db):
    """Unknown is not "longest running". A null sorting to the top would put the
    least evidenced creative first."""
    db.add(m.Creative(competitor_id=11, creative_id="CR-NULL", format="text", total_days_shown=None,
                      first_seen_run_id=30, last_seen_run_id=30, active=True))
    db.commit()
    d = build_report_data(db, watchlist, days=7)
    assert d["proven_creatives"][0]["creative_id"] == "CR-EVERGREEN"


# ---- brand defence -------------------------------------------------------------------------------


def test_the_report_names_who_is_bidding_on_a_tracked_brand(watchlist, db):
    d = build_report_data(db, watchlist, days=7)
    alpha = next(b for b in d["brand_defence"] if b["brand"] == "Alpha")
    assert alpha["conquerors"] == ["beta.com"]
    assert alpha["owner_present"] is False


def test_a_watchlist_with_no_brand_terms_reports_an_empty_list(db):
    db.add(m.Workspace(id=2, name="other"))
    db.flush()
    w = m.Watchlist(id=2, workspace_id=2, name="Tea", vertical="tea", geo="US")
    db.add(w)
    db.commit()
    assert build_report_data(db, w, days=7)["brand_defence"] == []


# ---- the regression ------------------------------------------------------------------------------


def test_brand_terms_are_not_reported_as_market_keywords(watchlist, db):
    """A brand term's paid block answers "who is bidding on this company's name",
    not "who competes on this market term". Mixing them put a competitor's brand in
    the share-of-voice table as though the customer had chosen to target it."""
    d = build_report_data(db, watchlist, days=7)
    assert [k["term"] for k in d["keywords"]] == ["coffee subscription"]


def test_one_prolific_competitor_cannot_monopolise_the_ranking(watchlist, db):
    """Observed on live data: Starbucks has 92 creatives, its oldest run 1,700+ days,
    and a global top-10 by days returned ten Starbucks rows. Dunkin' and Peet's were
    invisible. A competitive brief that shows one competitor is not a competitive
    brief, so each gets a capped share of the table.
    """
    for i in range(20):
        db.add(m.Creative(competitor_id=10, creative_id=f"CR-BULK-{i}", format="text",
                          total_days_shown=900 + i, first_shown=date(2022, 1, 1), last_shown=date(2026, 9, 1),
                          first_seen_run_id=30, last_seen_run_id=30, active=True))
    db.commit()
    d = build_report_data(db, watchlist, days=7)
    names = [c["competitor"] for c in d["proven_creatives"]]
    assert "Beta" in names, "the prolific competitor crowded everyone else out"
    assert names.count("Alpha") <= PROVEN_PER_COMPETITOR


def test_the_ranking_is_still_ordered_by_days(watchlist, db):
    d = build_report_data(db, watchlist, days=7)
    days = [c["days"] for c in d["proven_creatives"]]
    assert days == sorted(days, reverse=True)
