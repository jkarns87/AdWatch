from datetime import date

from app.engine.diff import diff_creatives, diff_related_queries, diff_serp_ads, diff_trends


def cr(cid, fmt="image"):
    return {"creative_id": cid, "format": fmt, "details_url": f"https://x/{cid}"}


def ad(domain, pos, block="top"):
    return {"advertiser_domain": domain, "position": pos, "block": block, "title": domain}


def test_first_run_is_baseline():
    assert diff_creatives(None, [cr("a")], competitor_id=1, label="A") == []
    assert diff_serp_ads(None, [ad("a.com", 1)], keyword_id=1, label="k") == []
    assert diff_related_queries(None, [{"query": "x", "bucket": "rising", "value_text": "Breakout"}], keyword_id=1, label="k") == []


def test_creative_launched_and_dropped():
    out = diff_creatives([cr("a"), cr("b")], [cr("b"), cr("c")], competitor_id=7, label="A")
    kinds = sorted(c["kind"] for c in out)
    assert kinds == ["creative_dropped", "creative_launched"]
    launched = next(c for c in out if c["kind"] == "creative_launched")
    assert launched["payload"]["creative_id"] == "c" and launched["subject_id"] == 7


def test_creative_surge():
    prev = [cr(str(i)) for i in range(4)]
    cur = prev + [cr(f"n{i}") for i in range(4)]  # 4 -> 8 = +100%, +4
    out = diff_creatives(prev, cur, competitor_id=1, label="A")
    surge = [c for c in out if c["kind"] == "creative_surge"]
    assert len(surge) == 1 and surge[0]["payload"]["delta_pct"] == 100 and surge[0]["severity"] == "high"


def test_serp_new_left_and_shift():
    prev = [ad("a.com", 1), ad("b.com", 2), ad("c.com", 3)]
    cur = [ad("z.com", 1), ad("a.com", 3), ad("b.com", 1, "bottom")]
    out = diff_serp_ads(prev, cur, keyword_id=3, label="kw", tracked_domains={"a.com", "b.com"})
    kinds = sorted(c["kind"] for c in out)
    assert kinds == ["new_serp_advertiser", "serp_advertiser_left", "serp_position_shift", "serp_position_shift"]
    new = next(c for c in out if c["kind"] == "new_serp_advertiser")
    assert new["payload"]["advertiser_domain"] == "z.com" and new["severity"] == "high"


def test_trend_spike_and_decline():
    base = [{"date": date(2026, 8, d), "value": 40} for d in range(1, 5)]
    spike = base + [{"date": date(2026, 8, 5), "value": 80}]
    out = diff_trends(spike, keyword_id=1, label="kw", had_previous_run=True)
    assert out and out[0]["kind"] == "trend_spike" and out[0]["payload"]["ratio"] == 2.0
    decline = base + [{"date": date(2026, 8, 5), "value": 10}]
    out = diff_trends(decline, keyword_id=1, label="kw", had_previous_run=True)
    assert out and out[0]["kind"] == "trend_decline"
    assert diff_trends(spike, keyword_id=1, label="kw", had_previous_run=False) == []


def test_rising_query_breakout_and_threshold():
    prev = [{"query": "old", "bucket": "rising", "value_text": "Breakout"}]
    cur = [
        {"query": "old", "bucket": "rising", "value_text": "Breakout"},
        {"query": "meal kit for two", "bucket": "rising", "value_text": "Breakout", "value_num": None},
        {"query": "cheap kits", "bucket": "rising", "value_text": "+450%", "value_num": 450},
        {"query": "meh", "bucket": "rising", "value_text": "+120%", "value_num": 120},
        {"query": "top one", "bucket": "top", "value_text": "100", "value_num": 100},
    ]
    out = diff_related_queries(prev, cur, keyword_id=2, label="kw")
    assert sorted(c["payload"]["query"] for c in out) == ["cheap kits", "meal kit for two"]
