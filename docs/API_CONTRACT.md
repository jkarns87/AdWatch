# AdWatch — API contract (web ↔ api)

Base: `http://localhost:8000/api/v1` (env `NEXT_PUBLIC_API_BASE_URL`).
All responses JSON. Errors: `{ "detail": "message" }` with 4xx/5xx.
Auth (once Xano is in): `Authorization: Bearer <xano_jwt>`; the API reads `workspace_id` from it. Until then, `X-Workspace-Id: 1` header (defaults to 1 if absent).

Frontend builds against this document. Backend implements it. **Changes to this file require a PR comment tagging both lanes.**

---

## Health

`GET /health` → `{ "status": "ok", "db": "ok", "serpapi_key_present": true, "anthropic_key_present": true }`

The `_present` fields are exactly that — presence, not validity. `bool("apiworld2026")`
is `true`. For whether the key actually works, and how much quota is left:

`GET /providers/serpapi` → `{ "key_source": "workspace|platform|none",
  "status": "ok|invalid|exhausted|unset|unreachable", "plan": "Free Plan",
  "searches_left": 184, "searches_per_month": 250, "cached": true }`

Cached for 60s per key. `invalid` and `unreachable` are distinct: a bad key versus
SerpApi being down.

---

## Watchlists

`GET /watchlists`
```json
[{ "id": 1, "name": "Meal Kit Delivery", "vertical": "meal kits", "geo": "US",
   "competitor_count": 3, "keyword_count": 5, "last_run_at": "2026-09-02T18:04:11Z",
   "open_changes": 7 }]
```

`POST /watchlists` body `{ "name", "vertical", "geo"?: "US" }` → watchlist (201)

`GET /watchlists/{id}`
```json
{ "id": 1, "name": "…", "vertical": "…", "geo": "US", "created_at": "…",
  "competitors": [{ "id": 11, "name": "…", "domain": "…", "advertiser_id": null, "active_creatives": 14 }],
  "keywords":    [{ "id": 21, "term": "meal kit delivery" }],
  "last_run": { "id": 3, "started_at": "…", "finished_at": "…", "status": "done", "searches_used": 18 } }
```

`POST /watchlists/{id}/competitors` body `{ "name", "domain", "advertiser_id"? }` → competitor (201)
`DELETE /watchlists/{id}/competitors/{competitor_id}` → 204
`POST /watchlists/{id}/keywords` body `{ "term" }` → keyword (201)
`DELETE /watchlists/{id}/keywords/{keyword_id}` → 204

---

## Collection & analysis

`POST /watchlists/{id}/collect`  (synchronous; typical 10–30s; uses SerpApi quota)
```json
{ "run": { "id": 4, "status": "done", "searches_used": 18, "started_at": "…", "finished_at": "…" },
  "snapshots": 18,
  "changes": [ /* Change[] — see below */ ] }
```

`POST /watchlists/{id}/analyze`  (runs Claude on changes with no insight yet)
```json
{ "insights": [ /* Insight[] */ ], "alerts_sent": 1 }
```

`POST /watchlists/{id}/collect-and-analyze` → both, in order. **This is the "Collect now" button.**

---

## Read models

`GET /watchlists/{id}/creatives?competitor_id=&active=true`
```json
[{ "id": 101, "competitor_id": 11, "creative_id": "CR0123…", "format": "text|image|video",
   "platform": "SEARCH|YOUTUBE|…|null", "target_domain": "…", "image_url": null,
   "details_url": "https://adstransparency.google.com/…", "first_shown": "2026-07-01",
   "last_shown": "2026-09-01", "active": true, "first_seen_run_id": 1, "last_seen_run_id": 4,
   "text": { "headline": "…", "description": "…" } }]
```

`GET /watchlists/{id}/serp?keyword_id=21`  (latest run; share-of-voice table)
```json
{ "keyword": { "id": 21, "term": "…" }, "run_id": 4,
  "ads": [{ "position": 1, "block": "top", "advertiser_domain": "…", "title": "…",
            "description": "…", "displayed_link": "…", "is_tracked_competitor": true,
            "competitor_id": 11 }],
  "share_of_voice": [{ "advertiser_domain": "…", "appearances": 3, "avg_position": 1.7 }] }
```

`GET /coffee/keywords?keywords=coffee+nearby&output=json|md|html|csv&location=&depth=4&limit=25&refresh=false`

Top coffee keywords for a seed term, ranked by how many advertisers are observably competing on them. **This is the one endpoint that queries SerpApi live** — it answers "what is the paid block for this term right now", which no stored run can. Cost: `1 + depth` searches, plus up to 3 more if the seed has no advertisers of its own and the scan escalates up the commercial ladder; `searches_used` reports the exact figure and the disk cache makes a repeated call free. Off-market seeds are rejected with 400 **before** any search is spent.

Every keyword carries the evidence it was scored on, and `scoring` returns the formula and weights used, so any score can be recomputed by hand from that keyword's `signals`. Nothing about bids, budgets, spend or impression share is reported — SerpApi does not return it.

| evidence | meaning |
|---|---|
| `targeting_keyword` | an advertiser's own ad URL named it (Google expanded `{keyword}` into the click URL) |
| `sponsored_query` | ads were served against this exact query |
| `ad_copy` | two or more advertisers write the phrase in their copy |
| `autocomplete` | a Google suggestion only, no advertiser behind it |

```json
{ "query": "coffee subscription", "location": "United States", "searches_used": 4,
  "summary": { "queries_scanned": 3, "ads_seen": 8, "advertisers": 5,
               "keywords_found": 14, "keywords_recovered_from_ads": 2,
               "ads_exposing_a_keyword": 2, "competition": "low",
               "confidence": "high", "escalated_to": [] },
  "scoring": { "formula": "score = 100 * min(1, (6*targeting_keyword_advertisers + …) / 30)",
               "weights": { "…": 6.0 }, "reference": 30.0, "competition_bands": { "…": "…" } },
  "queries": [{ "query": "coffee subscription", "advertisers": 4, "ads": 2 }],
  "keywords": [{ "keyword": "coffee subscription gift", "score": 75.0,
                 "evidence": "targeting_keyword", "recovered_from_ad": true,
                 "advertiser_count": 4, "advertisers": ["beanbox.com", "…"],
                 "competition": "medium", "match_types": ["exact"], "ads": 7,
                 "signals": { "targeting_keyword_advertisers": 4, "…": 0 },
                 "seen_on_queries": ["coffee subscription gift"],
                 "example_ad": { "advertiser_domain": "beanbox.com", "title": "…" } }],
  "advertisers": [{ "advertiser_domain": "drinktrade.com", "ads": 7,
                    "recovered_keywords": ["coffee subscription gift"] }],
  "warnings": [] }
```

`docs/samples/` holds real output in the `output=csv` columns plus `from_seed` (and `market`, where two were scanned):

| file | keywords | with advertisers | scanned |
|---|--:|--:|---|
| `coffee-keywords-scan.csv` | 84 | 19 | 5 seeds, United States |
| `tea-keywords-scan.csv` | 305 | 75 | 18 seeds — types (green, black, chai, Indian, iced, milk, matcha, boba, herbal), intent, and local terms across the Bay Area and Texas |
| `meal-kit-keywords-scan.csv` | 171 | 49 | 10 seeds, Bay Area + Texas |
| `juice-keywords-scan.csv` | 161 | 33 | 10 seeds, local intent, Bay Area + Texas |

Rows with `advertiser_count` 0 are autocomplete suggestions and say so in `evidence` — nothing is presented as more than the data supports. The vocabularies behind each market are `VERTICALS` in `app/coffee/engine.py`; the endpoint itself stays coffee-only (`discover` defaults to `COFFEE` and the route never passes anything else), so these were generated by running the same engine from a script.

`output=md` returns Markdown, `output=html` a standalone report page, `output=csv` a spreadsheet (`rank,keyword,score,evidence,recovered_from_ad,advertiser_count,advertisers,match_types,competition,ads,seen_on_queries`; list cells joined with `;`). Errors are always JSON: `400` bad parameter or off-market keyword · `401` invalid SerpApi key · `429` SerpApi rate limit or quota · `502` SerpApi failed.

`GET /watchlists/{id}/export.csv` → the watchlist's competitors and keywords as CSV (`Content-Disposition: attachment`).

`POST /watchlists/import.csv?name=&vertical=&geo=&location=` → the CSV as the request body with `Content-Type: text/csv`. Builds a watchlist in one step and returns `{ watchlist_id, name, competitors, keywords }`.

```bash
curl -X POST 'localhost:8000/api/v1/watchlists/import.csv?name=Specialty%20Coffee' \
     -H 'Content-Type: text/csv' --data-binary @coffee.csv
```

Both directions use one shape, so an exported file can be edited in a spreadsheet and imported back:

```
type,name,domain,term
competitor,BeanLoop,beanloop.example,
keyword,,,coffee subscription
```

A `type` column is honoured when present; without one, a row with a domain is a competitor and a row with a term is a keyword. URLs and `www.` are reduced to a domain, duplicates dropped, and a competitor with no name gets one from its domain. Caps: 50 competitors, 100 keywords, 1 MB — a run costs `competitors + 3 × keywords` searches. Bad input returns 400 naming the row and the problem.

`services/api/seed/` holds ready-made watchlists in this shape — `bay_area_coffee.csv`, `tea_bay_area.csv` and `local_services_sf.csv`, each 4 competitors and 5 keywords so a run costs 4 + 3×5 = 19 searches. Competitors are advertisers actually seen in that market's paid block (named by Google's own `source` field), and every keyword had advertisers behind it.

`services/api/seed/bay_area_coffee.csv` is a ready-made Bay Area coffee watchlist in this shape — 4 competitors and 5 keywords, so a run costs 4 + 3×5 = **19 searches**. Every row came out of `GET /coffee/keywords` rather than guesswork: the four advertisers were observed in the San Francisco paid block, and each keyword had advertisers behind it there (`coffee roasters san francisco` returned 14 ads from 8 advertisers; `coffee subscription`, `best coffee subscription` and `specialty coffee beans` were recovered from advertisers' own ad URLs).

```bash
curl -X POST 'localhost:8000/api/v1/watchlists/import.csv?name=Specialty%20Coffee%20%E2%80%94%20Bay%20Area&vertical=specialty%20coffee&location=San%20Francisco,%20California,%20United%20States' \
     -H 'Content-Type: text/csv' --data-binary @services/api/seed/bay_area_coffee.csv
```

These three routes are additive: they live in `app/coffee/` on their own router and change nothing in `routers/watchlists.py`, the collectors, the diff engine or the seed. Registering them is one line in `main.py`.

`GET /watchlists/{id}/trends?keyword_id=21`
```json
{ "keyword": { "id": 21, "term": "…" }, "run_id": 4,
  "timeline": [{ "date": "2026-06-07", "value": 42 }],
  "related_rising": [{ "query": "…", "value_text": "Breakout", "value_num": null }],
  "related_top":    [{ "query": "…", "value_text": "100", "value_num": 100 }] }
```

`GET /watchlists/{id}/changes?since=<iso>&kind=&limit=50`
```json
[{ "id": 501, "run_id": 4, "kind": "creative_launched", "severity": "medium",
   "subject_type": "competitor", "subject_id": 11, "subject_label": "…",
   "detected_at": "…", "insight_id": 31,
   "payload": { "creative_id": "…", "format": "image", "details_url": "…" } }]
```
`payload` shape by kind:
- `creative_launched|creative_dropped`: `{ creative_id, format, details_url, image_url?, text? }`
- `creative_surge`: `{ before, after, delta_pct }`
- `new_serp_advertiser|serp_advertiser_left`: `{ advertiser_domain, position?, block?, title? }`
- `serp_position_shift`: `{ advertiser_domain, from_position, to_position, from_block, to_block }`
- `trend_spike|trend_decline`: `{ latest, trailing_mean, ratio }`
- `rising_query`: `{ query, value_text }`

`GET /watchlists/{id}/insights?limit=20`
```json
[{ "id": 31, "run_id": 4, "created_at": "…", "model": "…", "confidence": 0.78,
   "summary": "…", "why_it_matters": "…",
   "recommended_actions": [{ "action": "…", "rationale": "…", "effort": "low", "urgency": "now" }],
   "change_ids": [501, 502], "changes": [ /* Change[] (embedded, lite) */ ] }]
```

---

## Onboarding

`GET /onboarding/verticals?q=&limit=8` → `[{ "id": 71, "name": "Food & Drink" }]` —
Google Trends taxonomy search, backs the typeahead.

`POST /onboarding/analyze` `{name, domain, description}` — reads the company's own site.
Costs Anthropic tokens, **no SerpApi quota**. Persists nothing.

```json
{ "vertical": { "id": 71, "name": "Food & Drink" },
  "keywords": ["coffee subscription"],
  "competitors": [{ "domain": "bluebottlecoffee.com", "name": "Blue Bottle", "reason": "DTC roaster" }],
  "assets": [{ "kind": "brand", "key": "primary_color", "value": "#B5121B" }],
  "site_read": true }
```

`site_read: false` means the page could not be fetched and the answer came from the
description alone — the UI says so rather than presenting it as read.

`POST /onboarding/create` `{name, domain, description, vertical_id, keywords, competitors, assets}`
→ 201. Verifies each competitor against the Ads Transparency Center — **one search each** —
and builds the watchlist with the company's own domain tracked as `is_self`.

```json
{ "watchlist_id": 1,
  "competitors": [{ "domain": "bluebottlecoffee.com", "verified": true }],
  "skipped": [{ "domain": "madeup.invalid", "reason": "no advertiser found" }],
  "searches_used": 2 }
```

`skipped` is not an error — a domain that buys no ads would cost a search every run
forever. `"could not be checked"` means SerpApi was unreachable, which is not evidence
the company does not advertise; the watchlist is still created.

---

## Alerts

`GET /alerts?limit=50` — workspace-wide notification feed, newest first. One call;
replaces `GET /watchlists` followed by `GET /watchlists/{id}/insights` per watchlist.

```json
[{ "id": 31, "watchlist_id": 1, "watchlist_name": "Specialty Coffee — Bay Area",
   "severity": "high", "summary": "…", "why_it_matters": "…",
   "created_at": "2026-09-02T18:04:11Z",
   "delivery": { "channel": "slack", "status": "sent",
                 "target": "https://hooks.slack.com/services/T04…/B07…/***",
                 "sent_at": "…", "error": null } }]
```

`id` is the **insight** id — the feed is insight-centric because that is what a person
reads. `delivery` is `null` for insights that were never dispatched (alerts only fire
above `min_severity`); those still belong in the feed.

`delivery.target` and `delivery.error` are **redacted server-side**. A webhook URL is a
credential, and httpx puts the full URL in its error text — see `docs/SECRETS.md`.

---

## Reports

`GET /watchlists/{id}/report?audience=cfo|marketing&format=pdf|docx|md&days=7` → file download (`Content-Disposition: attachment`).
Audience-tailored AI executive summary (headline, paragraphs, decisions, watch-next), KPI strip, recommended actions, what changed (severity-sorted), competitor activity, per-keyword paid block / share of voice / demand (+ Trends chart in PDF). Header `X-Report-Model` says whether Claude or the deterministic fallback wrote the summary.

`GET /watchlists/{id}/report/data?audience=&days=` → the assembled JSON payload (for previews/tests).

## Demo helpers (disabled when `ENV=prod` unless `DEMO_ENDPOINTS=true`)

`POST /demo/seed` body `{ "mode": "synthetic" | "live", "vertical"?: "meal kits" }`
→ `{ "watchlist_id": 1, "runs": [1,2], "changes": 9, "insights": 3 }`
Synthetic mode invents fictitious advertisers (no quota, no real brands). Live mode uses `services/api/seed/demo_config.json` (git-ignored; copy from `.example`) and spends quota.

`POST /demo/reset` → wipes all tables (local only).

---

## Types (TypeScript mirror lives in `apps/web/lib/types.ts`)

```ts
export type Severity = "low" | "medium" | "high";
export type ChangeKind =
  | "creative_launched" | "creative_dropped" | "creative_surge"
  | "new_serp_advertiser" | "serp_advertiser_left" | "serp_position_shift"
  | "trend_spike" | "trend_decline" | "rising_query";
```
