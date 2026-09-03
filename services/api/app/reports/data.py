"""Assemble everything a report needs from the database, then ask the analyst for an
audience-tailored executive summary. Pure data in, dict out — the PDF / DOCX / Markdown
renderers only format."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import get_settings
from ..engine import brand as brand_engine
from ..engine.analyst import _extract_json
from ..metering import record_call

log = logging.getLogger(__name__)

PROVEN_LIMIT = 10
# Cap per competitor so one prolific advertiser cannot own the table. Observed on live
# data: a competitor with 92 creatives, the oldest running 1,700+ days, took all ten
# slots and the other two competitors were invisible. A competitive brief showing one
# competitor is not a competitive brief.
PROVEN_PER_COMPETITOR = 3

AUDIENCES = {
    "cfo": {
        "title": "Competitive Spend & Risk Brief",
        "reader": "the CFO and finance leadership",
        "lens": (
            "Frame everything in terms of where competitors are shifting investment, which of our keywords "
            "are getting more expensive or contested, demand signals that justify or defer budget, and the "
            "two or three decisions finance should weigh in on. Avoid creative jargon. No invented dollar "
            "figures — describe direction and magnitude in relative terms only."
        ),
    },
    "marketing": {
        "title": "Competitive Intelligence Brief",
        "reader": "marketing managers and the paid-search team",
        "lens": (
            "Frame everything as concrete campaign, creative, keyword and landing-page actions with owners "
            "and timing. Call out which competitor moves matter this week and which are noise."
        ),
    },
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

KIND_LABEL = {
    "creative_launched": "Creative launched",
    "creative_dropped": "Creative dropped",
    "creative_surge": "Creative surge",
    "new_serp_advertiser": "New advertiser on keyword",
    "serp_advertiser_left": "Advertiser left keyword",
    "serp_position_shift": "Position shift",
    "trend_spike": "Demand spike",
    "trend_decline": "Demand decline",
    "rising_query": "Rising query",
    "ad_copy_changed": "Ad copy rewritten",
    "ad_sitelinks_changed": "Sitelinks changed",
    "product_price_changed": "Price changed",
    "product_promo_appeared": "Promotion started",
    "brand_conquest": "Bidding on brand",
    "brand_conquest_ended": "Stopped bidding on brand",
    "brand_undefended": "Brand undefended",
    "brand_defended": "Brand defended",
}


def describe_change(c: m.Change) -> str:
    p = c.payload or {}
    k = c.kind
    if k == "creative_launched":
        h = (p.get("text") or {}).get("headline")
        return f"{c.subject_label} launched a {p.get('format', '')} creative" + (f': "{h}"' if h else "")
    if k == "creative_dropped":
        return f"{c.subject_label} dropped a {p.get('format', '')} creative"
    if k == "creative_surge":
        return f"{c.subject_label} went from {p.get('before')} to {p.get('after')} active creatives (+{p.get('delta_pct')}%)"
    if k == "new_serp_advertiser":
        return f"{p.get('advertiser_domain')} appeared on \"{c.subject_label}\" ({p.get('block')} #{p.get('position')})"
    if k == "serp_advertiser_left":
        return f"{p.get('advertiser_domain')} left the paid block on \"{c.subject_label}\""
    if k == "serp_position_shift":
        return (
            f"{p.get('advertiser_domain')} moved {p.get('from_block')} #{p.get('from_position')} → "
            f"{p.get('to_block')} #{p.get('to_position')} on \"{c.subject_label}\""
        )
    if k == "trend_spike":
        return f"Interest in \"{c.subject_label}\" is {p.get('ratio')}× its 4-week average ({p.get('latest')} vs {p.get('trailing_mean')})"
    if k == "trend_decline":
        return f"Interest in \"{c.subject_label}\" fell to {p.get('ratio')}× its 4-week average"
    if k == "rising_query":
        return f"\"{p.get('query')}\" is {p.get('value_text')} for \"{c.subject_label}\""
    if k == "ad_copy_changed":
        return f"{p.get('advertiser_domain')} rewrote its ad on \"{c.subject_label}\": \"{p.get('from_title')}\" → \"{p.get('to_title')}\""
    if k == "ad_sitelinks_changed":
        added, removed = p.get("added") or [], p.get("removed") or []
        parts = [f"added {', '.join(added)}" if added else "", f"removed {', '.join(removed)}" if removed else ""]
        return f"{p.get('advertiser_domain')} changed sitelinks on \"{c.subject_label}\" — " + "; ".join(x for x in parts if x)
    if k == "product_price_changed":
        return f"{p.get('merchant')} moved \"{p.get('title')}\" from {p.get('from_price')} to {p.get('to_price')} ({p.get('delta_pct')}%)"
    if k == "product_promo_appeared":
        return f"{p.get('merchant')} started a promotion on \"{p.get('title')}\": {p.get('promo')}"
    if k == "brand_conquest":
        return f"{p.get('advertiser_domain')} is bidding on the {p.get('brand')} brand term (#{p.get('position')})"
    if k == "brand_conquest_ended":
        return f"{p.get('advertiser_domain')} stopped bidding on the {p.get('brand')} brand term"
    if k == "brand_undefended":
        return f"{p.get('brand')} is absent from its own brand term while {', '.join(p.get('conquerors') or [])} bid on it"
    if k == "brand_defended":
        return f"{p.get('brand')} is defending its own brand term again (#{p.get('position')})"
    return k


def build_report_data(db: Session, w: m.Watchlist, *, audience: str = "marketing", days: int = 7) -> dict[str, Any]:
    audience = audience if audience in AUDIENCES else "marketing"
    since = datetime.now(UTC) - timedelta(days=days)
    runs = db.scalars(select(m.Run).where(m.Run.watchlist_id == w.id, m.Run.status == "done").order_by(m.Run.id)).all()
    runs_in_period = [r for r in runs if r.finished_at and r.finished_at >= since]
    last_run = runs[-1] if runs else None

    changes = db.scalars(
        select(m.Change).where(m.Change.watchlist_id == w.id, m.Change.detected_at >= since).order_by(m.Change.id.desc())
    ).all()
    changes_sorted = sorted(changes, key=lambda c: (SEVERITY_ORDER.get(c.severity, 9), -c.id))
    by_kind = Counter(c.kind for c in changes)
    by_sev = Counter(c.severity for c in changes)

    insights = db.scalars(
        select(m.Insight).where(m.Insight.watchlist_id == w.id, m.Insight.created_at >= since).order_by(m.Insight.id.desc())
    ).all()
    actions: list[dict[str, Any]] = []
    for i in insights:
        for a in i.recommended_actions or []:
            actions.append({**a, "insight_id": i.id, "confidence": i.confidence})
    urg_rank = {"now": 0, "this_week": 1, "monitor": 2}
    actions.sort(key=lambda a: (urg_rank.get(a.get("urgency", ""), 3), -float(a.get("confidence") or 0)))
    seen: set[str] = set()
    actions = [a for a in actions if not ((a.get("action") or "").strip().lower() in seen or seen.add((a.get("action") or "").strip().lower()))]

    # competitors: active creatives + launched in period
    launched_by_comp = Counter(c.subject_id for c in changes if c.kind == "creative_launched")
    dropped_by_comp = Counter(c.subject_id for c in changes if c.kind == "creative_dropped")
    competitors = []
    for comp in w.competitors:
        active = db.scalar(select(m.Creative).where(m.Creative.competitor_id == comp.id, m.Creative.active.is_(True)).limit(1))
        active_n = len(db.scalars(select(m.Creative.id).where(m.Creative.competitor_id == comp.id, m.Creative.active.is_(True))).all()) if active else 0
        fmt = Counter(
            r.format for r in db.scalars(select(m.Creative).where(m.Creative.competitor_id == comp.id, m.Creative.active.is_(True))).all()
        )
        competitors.append(
            {
                "name": comp.name,
                "domain": comp.domain,
                "active_creatives": active_n,
                "launched": launched_by_comp.get(comp.id, 0),
                "dropped": dropped_by_comp.get(comp.id, 0),
                "formats": dict(fmt),
            }
        )

    # keywords: share of voice (latest run) + demand
    tracked = {c.domain.lower() for c in w.competitors}
    keywords = []
    # Brand terms live in the keywords table. Their paid block answers "who is bidding
    # on this company's name", not "who competes on this market term", so listing them
    # here would put a competitor's brand in share of voice as though the customer had
    # chosen to target it.
    market_keywords = [k for k in w.keywords if getattr(k, "kind", "keyword") == "keyword"]
    brand_keywords = [k for k in w.keywords if getattr(k, "kind", "keyword") == "brand"]
    for kw in market_keywords:
        ads = db.scalars(select(m.SerpAd).where(m.SerpAd.keyword_id == kw.id, m.SerpAd.run_id == (last_run.id if last_run else -1))).all()
        sov_all: dict[str, list[int]] = defaultdict(list)
        for r in db.scalars(select(m.SerpAd).where(m.SerpAd.keyword_id == kw.id)).all():
            sov_all[r.advertiser_domain].append(r.position)
        sov = sorted(
            ({"domain": d, "appearances": len(p), "avg_position": round(mean(p), 1), "tracked": d.lower() in tracked} for d, p in sov_all.items()),
            key=lambda x: (-x["appearances"], x["avg_position"]),
        )[:6]
        run_id = db.scalar(select(m.TrendPoint.run_id).where(m.TrendPoint.keyword_id == kw.id).order_by(m.TrendPoint.run_id.desc()).limit(1))
        pts = (
            db.scalars(select(m.TrendPoint).where(m.TrendPoint.keyword_id == kw.id, m.TrendPoint.run_id == run_id).order_by(m.TrendPoint.date)).all()
            if run_id
            else []
        )
        vals = [p.value for p in pts]
        latest = vals[-1] if vals else None
        trailing = round(mean(vals[-5:-1]), 1) if len(vals) >= 5 else None
        rising = [
            r.query
            for r in db.scalars(
                select(m.RelatedQuery).where(m.RelatedQuery.keyword_id == kw.id, m.RelatedQuery.run_id == run_id, m.RelatedQuery.bucket == "rising")
            ).all()
        ][:4] if run_id else []
        keywords.append(
            {
                "term": kw.term,
                "paid_block": [{"position": a.position, "block": a.block, "domain": a.advertiser_domain, "tracked": a.advertiser_domain.lower() in tracked} for a in sorted(ads, key=lambda a: (a.block != "top", a.position))],
                "share_of_voice": sov,
                "demand_latest": latest,
                "demand_trailing": trailing,
                "demand_series": [{"date": p.date.isoformat(), "value": p.value} for p in pts],
                "rising_queries": rising,
            }
        )

    # Days actually served is the strongest performance proxy an ad library offers: an
    # advertiser does not keep paying to run a creative that is not working. The field
    # is on every creative the transparency engine returns and was stored and never
    # surfaced, so the report showed what changed this week and nothing about what is
    # proven. Active only — a retired creative's run is history, not a current bet.
    by_comp = {c.id: c for c in w.competitors}
    proven_rows = db.scalars(
        select(m.Creative).where(
            m.Creative.competitor_id.in_(list(by_comp) or [-1]),
            m.Creative.active.is_(True),
        )
    ).all()
    # A null day count is unknown, not "longest running", so it sorts last rather than
    # leading the ranking with the least evidenced creative.
    ranked = sorted(proven_rows, key=lambda r: (r.total_days_shown is None, -(r.total_days_shown or 0)))
    per_comp: Counter[int] = Counter()
    proven_creatives = []
    for r in ranked:
        if per_comp[r.competitor_id] >= PROVEN_PER_COMPETITOR:
            continue
        per_comp[r.competitor_id] += 1
        proven_creatives.append({
            "creative_id": r.creative_id,
            "competitor": by_comp[r.competitor_id].name if r.competitor_id in by_comp else "",
            "format": r.format,
            "days": r.total_days_shown,
            "first_shown": r.first_shown.isoformat() if r.first_shown else None,
            "last_shown": r.last_shown.isoformat() if r.last_shown else None,
        })
        if len(proven_creatives) >= PROVEN_LIMIT:
            break

    # Conquesting fires as an event only when it starts or stops, so a weekly brief
    # would otherwise never mention a rival that has been camped on the brand all week.
    brand_defence = []
    for kw in brand_keywords:
        owner = by_comp.get(kw.owner_competitor_id)
        if owner is None:
            continue
        brand_ads = [
            {"advertiser_domain": r.advertiser_domain, "position": r.position, "block": r.block, "title": r.title}
            for r in db.scalars(
                select(m.SerpAd).where(m.SerpAd.keyword_id == kw.id, m.SerpAd.run_id == (last_run.id if last_run else -1))
            ).all()
        ]
        state = brand_engine.assess(brand_ads, owner_domain=owner.domain)
        brand_defence.append({
            "brand": kw.term,
            "owner_domain": owner.domain,
            "is_self": owner.is_self,
            "owner_present": state["owner_present"],
            "owner_position": state["owner_position"],
            "undefended": state["undefended"],
            "conquerors": [a["advertiser_domain"] for a in state["conquerors"]],
        })

    data: dict[str, Any] = {
        "audience": audience,
        "title": AUDIENCES[audience]["title"],
        "watchlist": {"name": w.name, "vertical": w.vertical, "geo": w.geo},
        "period": {"days": days, "from": since.date().isoformat(), "to": datetime.now(UTC).date().isoformat()},
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
        "kpis": {
            "competitors": len(w.competitors),
            "keywords": len(market_keywords),
            "runs_in_period": len(runs_in_period),
            "searches_used": sum(r.searches_used for r in runs_in_period),
            "changes": len(changes),
            "high": by_sev.get("high", 0),
            "medium": by_sev.get("medium", 0),
            "low": by_sev.get("low", 0),
            "insights": len(insights),
            "actions": len(actions),
        },
        "changes_by_kind": [{"kind": k, "label": KIND_LABEL.get(k, k), "count": n} for k, n in by_kind.most_common()],
        "changes": [
            {"severity": c.severity, "kind": c.kind, "label": KIND_LABEL.get(c.kind, c.kind), "subject": c.subject_label, "description": describe_change(c), "detected_at": c.detected_at.isoformat(timespec="minutes")}
            for c in changes_sorted[:40]
        ],
        "insights": [
            {"id": i.id, "summary": i.summary, "why_it_matters": i.why_it_matters, "confidence": i.confidence, "actions": i.recommended_actions or []}
            for i in insights[:8]
        ],
        "actions": actions[:10],
        "competitors": competitors,
        "keywords": keywords,
        "proven_creatives": proven_creatives,
        "brand_defence": brand_defence,
    }
    summary = executive_summary(data)
    # This call site produces no Insight and no Run — the reason spend is tracked in a
    # ledger table rather than columns on Insight.
    summary_model = summary.get("model", "")
    record_call(
        db,
        workspace_id=w.workspace_id,
        model=summary_model,
        feature="report",
        usage=summary.pop("_usage", None),
        watchlist_id=w.id,
        status="fallback" if summary_model == "fallback" else "ok",
    )
    data["executive_summary"] = summary
    return data


# ---- audience-tailored executive summary -------------------------------------------------------

SUMMARY_SYSTEM = """You are AdWatch's analyst writing the opening page of a competitive-intelligence brief.
Reason ONLY from the JSON provided. Never invent numbers, spend, CTR or costs that are not in the data.
Do not name any third-party company other than the advertiser domains present in the data.
Respond with a single JSON object and nothing else:
{
  "headline": "<one sentence, the single most important thing this week>",
  "paragraphs": ["<2-4 short paragraphs of plain English for the stated reader>"],
  "decisions": ["<2-3 crisp decisions or asks for this reader, one sentence each>"],
  "watch_next": "<one sentence on what to watch before the next report>"
}"""


def executive_summary(data: dict[str, Any]) -> dict[str, Any]:
    aud = AUDIENCES[data["audience"]]
    s = get_settings()
    slim = {
        "reader": aud["reader"],
        "lens": aud["lens"],
        "watchlist": data["watchlist"],
        "period": data["period"],
        "kpis": data["kpis"],
        "changes_by_kind": data["changes_by_kind"],
        "top_changes": data["changes"][:15],
        "insights": [{"summary": i["summary"], "why_it_matters": i["why_it_matters"]} for i in data["insights"][:5]],
        "top_actions": data["actions"][:6],
        "competitors": data["competitors"],
        "keywords": [
            {"term": k["term"], "demand_latest": k["demand_latest"], "demand_trailing": k["demand_trailing"], "share_of_voice": k["share_of_voice"][:4], "rising_queries": k["rising_queries"]}
            for k in data["keywords"]
        ],
    }
    if not s.anthropic_api_key:
        return _fallback_summary(data, reason="ANTHROPIC_API_KEY not set")
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        msg = client.messages.create(
            model=s.anthropic_model,
            max_tokens=1200,
            temperature=0.2,
            system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": "REPORT DATA\n" + json.dumps(slim, default=str) + "\n\nWrite the opening page as JSON."}],
        )
        text = "".join(getattr(b, "text", "") for b in msg.content)
        parsed = _extract_json(text)
        if not parsed:
            return _fallback_summary(data, reason="unparseable model output")
        parsed.setdefault("paragraphs", [])
        parsed.setdefault("decisions", [])
        parsed["model"] = s.anthropic_model
        # Transport to the llm_calls ledger; build_report_data pops it before the
        # payload reaches a renderer. Never persisted.
        parsed["_usage"] = getattr(msg, "usage", None)
        return parsed
    except Exception as e:  # noqa: BLE001
        log.exception("executive summary failed")
        return _fallback_summary(data, reason=f"model error: {e.__class__.__name__}")


def _fallback_summary(data: dict[str, Any], *, reason: str) -> dict[str, Any]:
    k = data["kpis"]
    kinds = ", ".join(f"{c['count']} {c['label'].lower()}" for c in data["changes_by_kind"][:4]) or "no changes"
    top = data["changes"][0]["description"] if data["changes"] else "No changes were detected in the period."
    return {
        "headline": top,
        "paragraphs": [
            f"Over the last {data['period']['days']} days AdWatch ran {k['runs_in_period']} collection cycles across {k['competitors']} competitors and {k['keywords']} keywords, detecting {k['changes']} changes ({k['high']} high, {k['medium']} medium, {k['low']} low): {kinds}.",
            "This summary was generated without the AI analyst (" + reason + "); the tables below are complete and accurate.",
        ],
        "decisions": list(dict.fromkeys(a.get("action", "") for a in data["actions"][:3])),
        "watch_next": "Re-run collection before the next report to refresh the diff.",
        "model": "fallback",
    }
