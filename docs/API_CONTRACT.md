# AdWatch — API contract (web ↔ api)

Base: `http://localhost:8000/api/v1` (env `NEXT_PUBLIC_API_BASE_URL`).
All responses JSON. Errors: `{ "detail": "message" }` with 4xx/5xx.
Auth (once Xano is in): `Authorization: Bearer <xano_jwt>`; the API reads `workspace_id` from it. Until then, `X-Workspace-Id: 1` header (defaults to 1 if absent).

Frontend builds against this document. Backend implements it. **Changes to this file require a PR comment tagging both lanes.**

---

## Health

`GET /health` → `{ "status": "ok", "db": "ok", "serpapi_key": true, "anthropic_key": true }`

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
