"""Markdown, HTML and CSV renderings of one coffee keyword report."""

from __future__ import annotations

import csv
import html
import io
from typing import Any

EVIDENCE_LABELS = {
    "targeting_keyword": "named in the ad URL",
    "sponsored_query": "ads served on it",
    "ad_copy": "advertiser copy",
    "autocomplete": "autocomplete only",
}
BAND_COLORS = {"high": "#b42318", "medium": "#b54708", "low": "#175cd3", "none": "#667085"}

CSV_COLUMNS = [
    "rank", "keyword", "score", "evidence", "recovered_from_ad", "advertiser_count",
    "advertisers", "match_types", "competition", "ads", "seen_on_queries",
]


def _label(kw: dict[str, Any]) -> str:
    return EVIDENCE_LABELS.get(kw["evidence"], kw["evidence"])


def to_csv(r: dict[str, Any]) -> str:
    """One row per keyword, for a spreadsheet.

    List cells are joined with ";" rather than "," so the file survives being
    opened in Excel or Sheets without quoting surprises.
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for i, kw in enumerate(r["keywords"], 1):
        w.writerow([
            i,
            kw["keyword"],
            kw["score"],
            kw["evidence"],
            "yes" if kw["recovered_from_ad"] else "no",
            kw["advertiser_count"],
            ";".join(kw["advertisers"]),
            ";".join(kw["match_types"]),
            kw["competition"],
            kw["ads"],
            ";".join(kw["seen_on_queries"]),
        ])
    return buf.getvalue()


def to_markdown(r: dict[str, Any]) -> str:
    s = r["summary"]
    out = [
        f"# Coffee keywords — “{r['query']}”",
        "",
        f"*{r.get('location') or 'default market'} · {s['ads_seen']} ads from {s['advertisers']} advertisers across "
        f"{s['queries_scanned']} queries · advertisers on the seed: **{s['competition']}** · confidence: **{s['confidence']}** · "
        f"{r['searches_used']} SerpApi searches*",
        "",
        "| # | keyword | score | advertisers | band | evidence |",
        "| --: | --- | --: | --: | --- | --- |",
    ]
    for i, kw in enumerate(r["keywords"], 1):
        out.append(f"| {i} | {kw['keyword']} | {kw['score']} | {kw['advertiser_count']} | {kw['competition']} | {_label(kw)} |")
    if not r["keywords"]:
        out.append("| | *no sponsored results found* | | | | |")

    recovered = [k for k in r["keywords"] if k["recovered_from_ad"]]
    if recovered:
        out += [
            "",
            "## Recovered from advertisers' own ad URLs",
            "",
            "Read out of the click-tracking URL, where Google expanded the `{keyword}` macro into the advertiser's targeting keyword.",
            "",
        ]
        for kw in recovered:
            mt = f" ({', '.join(kw['match_types'])})" if kw["match_types"] else ""
            out.append(f"- **{kw['keyword']}**{mt} — {', '.join(kw['advertisers'][:6])}")

    if r["advertisers"]:
        out += ["", "## Advertisers", "", "| advertiser | ads | keywords named in their ad URLs |", "| --- | --: | --- |"]
        for a in r["advertisers"][:20]:
            out.append(f"| {a['advertiser_domain']} | {a['ads']} | {', '.join(a['recovered_keywords']) or '—'} |")

    if s["escalated_to"]:
        out += [
            "",
            f"*No advertisers on “{r['query']}” itself, so the scan escalated to the commercial terms behind it: "
            + ", ".join(f"`{q}`" for q in s["escalated_to"]) + ".*",
        ]

    out += ["", "## Queries scanned", ""]
    for q in r["queries"]:
        out.append(f"- `{q['query']}` — {q['ads']} ads, {q['advertisers']} advertisers")
    for w in r.get("warnings") or []:
        out.append(f"- `{w['query']}` — skipped: {w['error']}")
    out += ["", f"*{s['ads_exposing_a_keyword']} of {s['ads_seen']} ads exposed a targeting keyword. "
                f"Score formula: `{r['scoring']['formula']}`*"]
    return "\n".join(out) + "\n"


def to_html(r: dict[str, Any]) -> str:
    e = html.escape
    s = r["summary"]
    rows = []
    for i, kw in enumerate(r["keywords"], 1):
        sig = kw["signals"]
        why = []
        if sig["targeting_keyword_advertisers"]:
            why.append(f"{sig['targeting_keyword_advertisers']} advertiser(s) name it in their ad URL")
        if sig["sponsored_query_advertisers"]:
            why.append(f"{sig['sponsored_query_advertisers']} advertiser(s) shown on it")
        if sig["ad_copy_advertisers"]:
            why.append(f"in {sig['ad_copy_advertisers']} advertiser(s)' copy")
        if sig["autocomplete_rank"]:
            why.append(f"autocomplete suggestion #{sig['autocomplete_rank']}")
        if sig["related_search"]:
            why.append("related search")
        tag = "recovered" if kw["recovered_from_ad"] else "inferred"
        rows.append(
            f'    <tr><td class="num">{i}</td>'
            f'<td><span class="kw">{e(kw["keyword"])}</span> <span class="tag {tag}">{e(_label(kw))}</span></td>'
            f'<td class="num"><div class="bar" style="--w:{kw["score"]}%"></div>{kw["score"]}</td>'
            f'<td class="num">{kw["advertiser_count"]}</td>'
            f'<td style="color:{BAND_COLORS[kw["competition"]]}">{kw["competition"]}</td>'
            f'<td class="why">{e(", ".join(why))}</td></tr>'
        )

    advertisers = "\n".join(
        f'    <tr><td>{e(a["advertiser_domain"])}</td><td class="num">{a["ads"]}</td>'
        f'<td class="why">{e(", ".join(a["recovered_keywords"]) or "—")}</td></tr>'
        for a in r["advertisers"][:20]
    )
    queries = " · ".join(f"<code>{e(q['query'])}</code> ({q['ads']} ads)" for q in r["queries"])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coffee keywords — {e(r['query'])}</title>
<style>
  :root {{ color-scheme: light dark; --fg:#101828; --mut:#667085; --line:#e4e7ec; --bg:#fff; --accent:#175cd3; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --fg:#e6e8ec; --mut:#98a2b3; --line:#2a2f3a; --bg:#14161a; }} }}
  body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; }}
  main {{ max-width:960px; margin:0 auto; padding:32px 20px 64px; }}
  h1 {{ font-size:24px; margin:0 0 4px; }}
  h2 {{ font-size:16px; margin:36px 0 10px; text-transform:uppercase; letter-spacing:.06em; color:var(--mut); }}
  .sub {{ color:var(--mut); margin:0 0 8px; }}
  .wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th,td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--mut); font-weight:600; }}
  tr:last-child td {{ border-bottom:none; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .kw {{ font-weight:600; }}
  .why {{ color:var(--mut); font-size:13px; }}
  .bar {{ display:inline-block; height:6px; width:var(--w); max-width:90px; min-width:2px; background:var(--accent);
          border-radius:3px; margin-right:8px; vertical-align:middle; opacity:.75; }}
  .tag {{ font-size:10px; text-transform:uppercase; letter-spacing:.05em; padding:2px 6px; border-radius:999px;
          margin-left:6px; border:1px solid var(--line); color:var(--mut); }}
  .tag.recovered {{ color:#067647; border-color:#067647; }}
  code {{ font-size:12.5px; color:var(--mut); }}
  footer {{ margin-top:32px; color:var(--mut); font-size:12.5px; }}
</style></head><body><main>
  <h1>Coffee keywords — “{e(r['query'])}”</h1>
  <p class="sub">{e(r.get('location') or 'default market')} · {s['ads_seen']} ads · {s['advertisers']} advertisers ·
     {s['queries_scanned']} queries · competition <strong>{s['competition']}</strong> ·
     confidence <strong>{s['confidence']}</strong> ·
     {s['keywords_recovered_from_ads']} keywords named in an ad URL
     ({s['ads_exposing_a_keyword']}/{s['ads_seen']} ads exposed one)</p>
  <div class="wrap"><table>
    <thead><tr><th></th><th>Keyword</th><th>Score</th><th>Advertisers</th><th>Band</th><th>Why</th></tr></thead>
    <tbody>
{chr(10).join(rows) or '    <tr><td colspan="6">No sponsored results.</td></tr>'}
    </tbody>
  </table></div>
  <h2>Advertisers</h2>
  <div class="wrap"><table>
    <thead><tr><th>Advertiser</th><th>Ads</th><th>Keywords named in their ad URLs</th></tr></thead>
    <tbody>
{advertisers or '    <tr><td colspan="3">None.</td></tr>'}
    </tbody>
  </table></div>
  <h2>Queries scanned</h2>
  <p class="sub">{queries}</p>
  <footer>{r['searches_used']} SerpApi searches · score = <code>{e(r['scoring']['formula'])}</code></footer>
</main></body></html>
"""
