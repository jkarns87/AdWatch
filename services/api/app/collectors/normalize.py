"""Turn raw SerpApi payloads into flat, typed dicts. Pure functions — easy to re-run from
`snapshots.raw` if we discover a field we missed (zero quota cost)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse


def _to_date(v: Any) -> date | None:
    """SerpApi returns first_shown/last_shown as unix ts (int) or ISO-ish strings depending on engine version."""
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            return datetime.fromtimestamp(int(v), tz=UTC).date()
        return datetime.fromisoformat(str(v)[:19]).date()
    except Exception:
        return None


def domain_of(url_or_display: str | None) -> str:
    if not url_or_display:
        return ""
    s = url_or_display.strip()
    # Google renders displayed_link as a breadcrumb — "https://www.foodandwine.com ›
    # sep-reviews › espresso-makers". There is no "/" to terminate the netloc, so
    # urlparse hands back the entire breadcrumb as the host. This is the diff key for
    # SERP ads, so a changed breadcrumb read as a different advertiser and produced a
    # matched pair of false new/disappeared events for one unchanged company.
    s = re.split(r"[\s›]", s, maxsplit=1)[0]
    if not s.startswith("http"):
        s = "https://" + s
    host = urlparse(s).netloc.lower()
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def creatives_from_ads_transparency(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ad in raw.get("ad_creatives") or []:
        # `ad_creative_id` is what the engine actually sends. Looking only for `id`/
        # `creative_id` meant every creative failed the guard below and a 40-creative
        # response normalized to []. Silent: no error, just an empty diff forever.
        cid = ad.get("ad_creative_id") or ad.get("id") or ad.get("creative_id")
        if not cid:
            continue
        fmt = (ad.get("format") or "text").lower()
        out.append(
            {
                "creative_id": str(cid),
                "format": fmt if fmt in ("text", "image", "video") else "text",
                "platform": ad.get("platform"),
                "target_domain": ad.get("target_domain"),
                "image_url": ad.get("image"),
                "details_url": ad.get("details_link") or ad.get("link"),
                "first_shown": _to_date(ad.get("first_shown")),
                "last_shown": _to_date(ad.get("last_shown")),
                "advertiser_name": ad.get("advertiser"),
                "advertiser_id": ad.get("advertiser_id"),
                "text": {k: ad[k] for k in ("headline", "description", "title") if ad.get(k)} or None,
            }
        )
    return out


def serp_ads_from_google(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ad in raw.get("ads") or []:
        pos = int(ad.get("position") or len(out) + 1)
        block = (ad.get("block_position") or "top").lower()
        block = "bottom" if "bottom" in block else "top"
        out.append(
            {
                "position": pos,
                "block": block,
                "advertiser_domain": domain_of(ad.get("displayed_link") or ad.get("link")),
                "title": ad.get("title") or "",
                "description": ad.get("description"),
                "displayed_link": ad.get("displayed_link"),
                "link": ad.get("link"),
            }
        )
    return out


def trend_points_from_timeseries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pt in (raw.get("interest_over_time") or {}).get("timeline_data") or []:
        vals = pt.get("values") or []
        if not vals:
            continue
        v = vals[0]
        num = v.get("extracted_value")
        if num is None:
            try:
                num = int(re.sub(r"[^0-9]", "", str(v.get("value", "0"))) or 0)
            except ValueError:
                num = 0
        d = None
        ts = pt.get("timestamp")
        if ts:
            d = datetime.fromtimestamp(int(ts), tz=UTC).date()
        else:
            # "Jun 7 – 13, 2026" style; take the first date token
            m = re.match(r"([A-Z][a-z]{2}) (\d{1,2})(?:.*?, (\d{4}))?", pt.get("date", ""))
            if m:
                try:
                    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3) or date.today().year}", "%b %d %Y").date()
                except ValueError:
                    d = None
        if d:
            out.append({"date": d, "value": int(num)})
    return out


def related_queries_from_trends(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rq = raw.get("related_queries") or {}
    for bucket in ("rising", "top"):
        for item in rq.get(bucket) or []:
            q = item.get("query")
            if not q:
                continue
            value_text = str(item.get("value", ""))
            value_num = item.get("extracted_value")
            if value_num is None and value_text.replace("+", "").replace("%", "").replace(",", "").isdigit():
                value_num = float(value_text.replace("+", "").replace("%", "").replace(",", ""))
            out.append({"query": q, "bucket": bucket, "value_text": value_text, "value_num": value_num})
    return out


def consensus_rising(draws: list[list[dict[str, Any]]], *, min_draws: int = 2) -> list[dict[str, Any]]:
    """Collapse repeated RELATED_QUERIES draws into the entries they agree on.

    Google samples the rising bucket, so a single draw is not evidence. Measured
    2026-09-03 across four genuinely uncached calls for one term: pairwise Jaccard
    0.10-0.25, and of 23 unique queries 13 appeared in exactly one draw while only
    one appeared in all four. Diffing one draw against one draw therefore reported
    sampling noise as demand.

    An entry is kept when its (bucket, query) appears in at least `min_draws` draws.
    The breakout flag has to clear the same bar on its own — it was the least stable
    field observed (0 of 2 survived all four draws, and one draw reported none at
    all) and it short-circuits the percentage threshold downstream.
    """
    if not draws:
        return []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    hits: dict[tuple[str, str], int] = {}
    breakouts: dict[tuple[str, str], int] = {}
    for draw in draws:
        for key in {(r.get("bucket") or "", (r.get("query") or "").lower()) for r in draw}:
            hits[key] = hits.get(key, 0) + 1
        for r in draw:
            key = (r.get("bucket") or "", (r.get("query") or "").lower())
            seen.setdefault(key, r)
            if "breakout" in str(r.get("value_text", "")).lower():
                breakouts[key] = breakouts.get(key, 0) + 1

    out: list[dict[str, Any]] = []
    for key, n in hits.items():
        if n < min_draws:
            continue
        row = dict(seen[key])
        if "breakout" in str(row.get("value_text", "")).lower() and breakouts.get(key, 0) < min_draws:
            # Seen as a breakout in a minority of draws: keep the query, drop the claim.
            numeric = [
                r["value_num"]
                for d in draws
                for r in d
                if (r.get("bucket") or "", (r.get("query") or "").lower()) == key and r.get("value_num") is not None
            ]
            row["value_num"] = max(numeric) if numeric else None
            row["value_text"] = f"+{int(row['value_num'])}%" if numeric else "rising"
        out.append(row)
    return out
