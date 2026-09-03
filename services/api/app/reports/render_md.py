"""Markdown renderer — paste into Slack/Notion/email."""

from __future__ import annotations

from typing import Any


def render_md(data: dict[str, Any]) -> str:
    k = data["kpis"]
    ex = data["executive_summary"]
    out = [
        f"# AdWatch — {data['title']}",
        f"*{data['watchlist']['name']} · {data['watchlist']['vertical']} · {data['watchlist']['geo']} · {data['period']['from']} → {data['period']['to']} · prepared for {'the CFO' if data['audience'] == 'cfo' else 'Marketing'}*",
        "",
        f"**{k['changes']} changes** ({k['high']} high · {k['medium']} medium · {k['low']} low) · {k['insights']} AI insights · {k['actions']} actions · {k['competitors']} competitors · {k['keywords']} keywords · {k['runs_in_period']} runs",
        "",
        "## Executive summary",
        f"**{ex.get('headline', '')}**",
        "",
        *ex.get("paragraphs", []),
    ]
    if ex.get("decisions"):
        out += ["", "**Decisions for this reader**"] + [f"- {d}" for d in ex["decisions"]]
    if ex.get("watch_next"):
        out += ["", f"**Watch next:** {ex['watch_next']}"]
    if data["actions"]:
        out += ["", "## Recommended actions", "", "| Urgency | Effort | Action | Rationale |", "|---|---|---|---|"]
        out += [f"| {a.get('urgency', '').replace('_', ' ')} | {a.get('effort', '')} | {a.get('action', '')} | {a.get('rationale', '')} |" for a in data["actions"]]
    out += ["", f"## What changed ({k['changes']} events)", ""]
    if data["changes_by_kind"]:
        out += [" · ".join(f"{c['count']} {c['label'].lower()}" for c in data["changes_by_kind"]), ""]
    out += ["| Sev | Type | Subject | Detail |", "|---|---|---|---|"]
    out += [f"| {c['severity']} | {c['label']} | {c['subject']} | {c['description']} |" for c in data["changes"]] or ["| — | No changes detected | | |"]
    out += ["", "## Competitor activity", "", "| Competitor | Domain | Active | Launched | Dropped | Formats |", "|---|---|---|---|---|---|"]
    out += [f"| {c['name']} | {c['domain']} | {c['active_creatives']} | {c['launched']} | {c['dropped']} | {', '.join(f'{a} {b}' for a, b in sorted(c['formats'].items()))} |" for c in data["competitors"]]
    if data.get("brand_defence"):
        # First, because a rival on your own name is the most actionable thing on the
        # page: they are paying to intercept people who already asked for you.
        out += ["", "## Brand defence", "", "| Brand | Owner bidding | Who else is bidding |", "|---|---|---|"]
        for b in data["brand_defence"]:
            owner = f"yes (#{b['owner_position']})" if b["owner_present"] else ("**no**" if b["undefended"] else "no")
            others = ", ".join(b["conquerors"]) or "nobody"
            out += [f"| {b['brand']}{' (you)' if b['is_self'] else ''} | {owner} | {others} |"]

    if data.get("proven_creatives"):
        # Ranked by days actually served, not by recency. An advertiser does not keep
        # paying to run a creative that is not working, which makes longevity the
        # closest thing to a performance signal that public ad-library data offers.
        out += ["", "## Proven creatives", "",
                "*Longest-running ads still live. Days served is the strongest performance proxy public data offers.*",
                "", "| Days live | Competitor | Format | First shown |", "|---|---|---|---|"]
        for c in data["proven_creatives"]:
            out += [f"| {c['days'] if c['days'] is not None else '—'} | {c['competitor']} | {c['format']} | {c['first_shown'] or '—'} |"]

    out += ["", "## Keywords", ""]
    for kw in data["keywords"]:
        block = ", ".join(f"{'↓' if a['block'] == 'bottom' else ''}#{a['position']} {a['domain']}{' *' if a['tracked'] else ''}" for a in kw["paid_block"]) or "no paid results captured"
        sov = ", ".join(f"{s['domain']} ×{s['appearances']} (avg #{s['avg_position']})" for s in kw["share_of_voice"][:4]) or "—"
        demand = (f"{kw['demand_latest']}" + (f" vs 4-wk avg {kw['demand_trailing']}" if kw["demand_trailing"] is not None else "")) if kw["demand_latest"] is not None else "—"
        out += [f"### {kw['term']}", f"- **Paid block now:** {block}", f"- **Share of voice:** {sov}", f"- **Demand:** {demand}", f"- **Rising:** {', '.join(kw['rising_queries']) or '—'}", ""]
    out += ["", "_* tracked competitor. Source: SerpApi (Google Ads Transparency Center, Google Search, Google Trends). Analysis: AdWatch diff engine + AI analyst._"]
    return "\n".join(out)
