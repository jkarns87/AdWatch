"""Diff engine — pure functions over plain dicts so they're trivially unit-testable.

Inputs are "previous" and "current" normalized views for one subject. Output is a list of
Change-shaped dicts (kind, severity, subject_type, subject_id, subject_label, payload).
See docs/ARCHITECTURE.md § Change taxonomy for thresholds.

Baseline rule: if `previous` is None (first run for this subject) -> no changes.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

SURGE_MIN_DELTA = 3
SURGE_MIN_PCT = 0.5
POSITION_SHIFT_MIN = 2
SPIKE_RATIO = 1.5
SPIKE_MIN_VALUE = 20
DECLINE_RATIO = 0.6
RISING_MIN_PCT = 300.0
TRAILING_WINDOW = 4
# Repeated identical product queries showed no spurious price movement at all, so the
# floor exists only to ignore rounding and currency jitter, not sampling noise.
PRICE_MIN_PCT = 2.0
PRICE_CUT_HIGH_PCT = 10.0


def _chg(kind: str, severity: str, subject_type: str, subject_id: int, label: str, payload: dict[str, Any]) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "subject_label": label,
        "payload": payload,
    }


# ---- creatives (per competitor) -----------------------------------------------------------------


def diff_creatives(
    previous: list[dict] | None, current: list[dict], *, competitor_id: int, label: str
) -> list[dict]:
    if previous is None:
        return []
    prev = {c["creative_id"]: c for c in previous}
    cur = {c["creative_id"]: c for c in current}
    changes: list[dict] = []

    for cid in cur.keys() - prev.keys():
        c = cur[cid]
        changes.append(
            _chg(
                "creative_launched",
                "medium",
                "competitor",
                competitor_id,
                label,
                {
                    "creative_id": cid,
                    "format": c.get("format"),
                    "details_url": c.get("details_url"),
                    "image_url": c.get("image_url"),
                    "text": c.get("text"),
                    "first_shown": str(c.get("first_shown") or ""),
                },
            )
        )
    for cid in prev.keys() - cur.keys():
        c = prev[cid]
        changes.append(
            _chg(
                "creative_dropped",
                "low",
                "competitor",
                competitor_id,
                label,
                {"creative_id": cid, "format": c.get("format"), "details_url": c.get("details_url"), "text": c.get("text")},
            )
        )

    before, after = len(prev), len(cur)
    if before > 0 and after - before >= SURGE_MIN_DELTA and (after - before) / before >= SURGE_MIN_PCT:
        changes.append(
            _chg(
                "creative_surge",
                "high",
                "competitor",
                competitor_id,
                label,
                {"before": before, "after": after, "delta_pct": round(100 * (after - before) / before)},
            )
        )
    return changes


# ---- SERP ads (per keyword) ---------------------------------------------------------------------


def diff_serp_ads(
    previous: list[dict] | None,
    current: list[dict],
    *,
    keyword_id: int,
    label: str,
    tracked_domains: set[str] | None = None,
) -> list[dict]:
    if previous is None:
        return []
    tracked = {d.lower() for d in (tracked_domains or set())}

    def by_domain(rows: list[dict]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for r in sorted(rows, key=lambda r: (0 if r.get("block") == "top" else 1, r.get("position", 99))):
            d = (r.get("advertiser_domain") or "").lower()
            if d and d not in out:
                out[d] = r
        return out

    prev, cur = by_domain(previous), by_domain(current)
    changes: list[dict] = []

    for d in cur.keys() - prev.keys():
        r = cur[d]
        changes.append(
            _chg(
                "new_serp_advertiser",
                "high",
                "keyword",
                keyword_id,
                label,
                {"advertiser_domain": d, "position": r.get("position"), "block": r.get("block"), "title": r.get("title"),
                 "is_tracked_competitor": d in tracked},
            )
        )
    for d in prev.keys() - cur.keys():
        r = prev[d]
        changes.append(
            _chg(
                "serp_advertiser_left",
                "medium",
                "keyword",
                keyword_id,
                label,
                {"advertiser_domain": d, "position": r.get("position"), "block": r.get("block"),
                 "is_tracked_competitor": d in tracked},
            )
        )
    for d in cur.keys() & prev.keys():
        p, c = prev[d], cur[d]

        # Ad copy was stored on every row from the first run and never compared, so a
        # competitor rewriting their headline produced no event at all — arguably the
        # most direct read on a rival's positioning available on the page.
        # Only for advertisers present in both runs: an arrival already reports itself.
        if (c.get("title") or "") != (p.get("title") or "") or (c.get("description") or "") != (p.get("description") or ""):
            changes.append(
                _chg(
                    "ad_copy_changed",
                    "medium",
                    "keyword",
                    keyword_id,
                    label,
                    {
                        "advertiser_domain": d,
                        "from_title": p.get("title"),
                        "to_title": c.get("title"),
                        "from_description": p.get("description"),
                        "to_description": c.get("description"),
                        "is_tracked_competitor": d in tracked,
                    },
                )
            )

        # Sitelinks compared as a set: order varies between identical calls, membership
        # does not. Observed on 3 of 4 ads and the only place extensions surface.
        before_sl, after_sl = set(p.get("sitelinks") or []), set(c.get("sitelinks") or [])
        if before_sl != after_sl:
            changes.append(
                _chg(
                    "ad_sitelinks_changed",
                    "low",
                    "keyword",
                    keyword_id,
                    label,
                    {
                        "advertiser_domain": d,
                        "added": sorted(after_sl - before_sl),
                        "removed": sorted(before_sl - after_sl),
                        "is_tracked_competitor": d in tracked,
                    },
                )
            )

        moved = abs(int(c.get("position", 0)) - int(p.get("position", 0))) >= POSITION_SHIFT_MIN
        block_changed = c.get("block") != p.get("block")
        if (moved or block_changed) and (d in tracked or not tracked):
            changes.append(
                _chg(
                    "serp_position_shift",
                    "medium",
                    "keyword",
                    keyword_id,
                    label,
                    {
                        "advertiser_domain": d,
                        "from_position": p.get("position"),
                        "to_position": c.get("position"),
                        "from_block": p.get("block"),
                        "to_block": c.get("block"),
                        "is_tracked_competitor": d in tracked,
                    },
                )
            )
    return changes


# ---- products (per keyword) ---------------------------------------------------------------------


def diff_products(previous: list[dict] | None, current: list[dict], *, keyword_id: int, label: str) -> list[dict]:
    """Price and promotion moves among the product listings on a keyword.

    Deliberately price-only. Measured on repeated identical queries: prices held
    steady with zero spurious changes, while the *set* of listings churned heavily
    between draws. So a price move is evidence and a product appearing or vanishing
    is usually sampling — emitting the latter would bury the former.

    Keyed on (merchant, title) because product ids were measured unstable run to run.
    """
    if previous is None:
        return []

    def by_key(rows: list[dict]) -> dict[tuple[str, str], dict]:
        return {(str(r.get("merchant", "")).strip().lower(), str(r.get("title", "")).strip().lower()): r for r in rows}

    prev, cur = by_key(previous), by_key(current)
    changes: list[dict] = []
    for key in cur.keys() & prev.keys():
        p, c = prev[key], cur[key]
        before, after = p.get("price"), c.get("price")
        if before and after and before > 0:
            delta_pct = round(100 * (after - before) / before, 1)
            if abs(delta_pct) >= PRICE_MIN_PCT:
                changes.append(
                    _chg(
                        "product_price_changed",
                        "high" if delta_pct <= -PRICE_CUT_HIGH_PCT else "medium",
                        "keyword",
                        keyword_id,
                        label,
                        {"merchant": c.get("merchant"), "title": c.get("title"), "from_price": before,
                         "to_price": after, "delta_pct": delta_pct},
                    )
                )
        if c.get("promo") and not p.get("promo"):
            changes.append(
                _chg(
                    "product_promo_appeared",
                    "medium",
                    "keyword",
                    keyword_id,
                    label,
                    {"merchant": c.get("merchant"), "title": c.get("title"), "promo": c.get("promo"),
                     "original_price": c.get("original_price"), "price": after},
                )
            )
    return changes


# ---- trends (per keyword) -----------------------------------------------------------------------


def diff_trends(points: list[dict], *, keyword_id: int, label: str, had_previous_run: bool) -> list[dict]:
    """Trends compare the latest point to its own trailing window (the timeseries is self-contained),
    but we still suppress on the very first run so the baseline doesn't scream."""
    if not had_previous_run or len(points) < TRAILING_WINDOW + 1:
        return []
    pts = sorted(points, key=lambda p: p["date"])
    latest = int(pts[-1]["value"])
    trailing = [int(p["value"]) for p in pts[-(TRAILING_WINDOW + 1) : -1]]
    base = mean(trailing) if trailing else 0
    if base <= 0:
        return []
    ratio = latest / base
    payload = {"latest": latest, "trailing_mean": round(base, 1), "ratio": round(ratio, 2)}
    if ratio >= SPIKE_RATIO and latest >= SPIKE_MIN_VALUE:
        return [_chg("trend_spike", "high", "keyword", keyword_id, label, payload)]
    if ratio <= DECLINE_RATIO:
        return [_chg("trend_decline", "low", "keyword", keyword_id, label, payload)]
    return []


def diff_related_queries(
    previous: list[dict] | None, current: list[dict], *, keyword_id: int, label: str
) -> list[dict]:
    if previous is None:
        return []
    prev_rising = {r["query"].lower() for r in previous if r.get("bucket") == "rising"}
    changes: list[dict] = []
    for r in current:
        if r.get("bucket") != "rising":
            continue
        q = r["query"].lower()
        if q in prev_rising:
            continue
        vt = str(r.get("value_text", ""))
        vn = r.get("value_num")
        breakout = "breakout" in vt.lower()
        big = vn is not None and float(vn) >= RISING_MIN_PCT
        if breakout or big:
            changes.append(
                _chg("rising_query", "medium", "keyword", keyword_id, label, {"query": r["query"], "value_text": vt})
            )
    return changes
