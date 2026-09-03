# SerpApi integration brief — for the Python API developers

Owners: @divya2030 @semmaguptam. Everything below is already scaffolded in `services/api/app/collectors/` — your job is to **verify it against live responses, harden the normalizers, and keep quota under control**. Nothing outside these four calls is required for the demo.

## 0. Setup (5 min)

```bash
cd services/api && cp ../../.env.example ../../.env      # put SERPAPI_API_KEY in .env
export DATABASE_URL=postgresql+psycopg://adwatch:adwatch@localhost:5432/adwatch
uvicorn app.main:app --reload
curl -s localhost:8000/api/v1/health                      # serpapi_key: true
```

SerpApi base: `GET https://serpapi.com/search.json?engine=…&api_key=…` — one HTTP call = **one search** against the quota. Free plan: **250 searches/month, 50/hour**. Cached results (same params within ~1h) are free on SerpApi's side; we also cache to disk (`SERPAPI_CACHE_DIR=.cache/serpapi`) so **re-running a collect in dev costs nothing**. Pass `?fresh=true` to `/collect` to bypass.

## 1. The four calls we make

Per watchlist run (`app/engine/collect.py::run_collect`):

| Step | Engine | Params we send | Per | Cost |
|---|---|---|---|---|
| A | `google_ads_transparency_center` | `text=<domain>` **or** `advertiser_id=<AR…>`, `num=100`; optional `region`, `creative_format=text|image|video`, `platform=SEARCH|YOUTUBE|MAPS|SHOPPING|PLAY` | competitor | 1 |
| B | **`google_ads`** | `q=<keyword>`, `gl=us`, `hl=en`, `device=desktop`, `google_domain=google.com`, `num=10`, **`location=<watchlist.location>`** (required — see below) | market keyword | 1 |
| C | `google_trends` | `q=<keyword>`, `geo=US`, `date="today 3-m"`, `data_type=TIMESERIES` | market keyword | 1 |
| D | `google_trends` | same as C with `data_type=RELATED_QUERIES`, **taken 3× with `no_cache=true`** | market keyword | 3 |
| E | `google_ads` | as B, on a competitor's brand name | brand term | 1 |

**Cost per run = competitors + 5 × market keywords + brand terms.** Demo watchlist
(3 competitors, 5 keywords, 3 brand terms) = **31 searches**.

### Why `google_ads` and not `google`

Measured 2026-09-03, identical query, location and minute:

| query | `engine=google` | `engine=google_ads` |
|---|---|---|
| crm software | 0 | 5 |
| car insurance quotes | 0 | 6 |
| espresso machine | 0 | 4 |
| meal kit delivery | 0 | 6 |
| running shoes | 0 | 2 |
| project management software | 0 | 6 |

Same cost, and the response is a superset — organic results, related searches and AI
overview all still come back. AdWatch is a paid-search product and was reading the engine
that omits the paid block; every SERP-derived number before this fix was zero.

`google_ads` also **requires** `location`: without one it errors and returns nothing, so
the client falls back to a country derived from `gl` rather than collecting silently
empty.

### Why three related-query draws

Google samples the rising bucket. Four genuinely uncached draws of one term gave pairwise
Jaccard **0.10-0.25**, with 13 of 23 queries appearing in exactly one draw and the
breakout flag stable in 0 of 2 cases. Diffing one draw against one draw reported that
churn as demand. Three draws, majority wins, measured to suppress 20 of 38 rising queries
as noise on live data.

Every draw must be genuinely fresh. `fresh=True` now sends `no_cache=true`; before that
it bypassed only our disk cache while SerpApi replayed its stored record for an hour, and
a stability measurement over those "draws" returned a meaningless Jaccard of 1.00.

## 2. What we read from each response (`app/collectors/normalize.py`)

### A — `google_ads_transparency_center` → `creatives_from_ads_transparency(raw)`
```
raw.ad_creatives[]:
  ad_creative_id        -> creative_id (string, unique per competitor)      REQUIRED
                           (NOT `id` or `creative_id` — matching those dropped every
                            creative silently; a 40-creative response normalized to [])
  format                -> "text" | "image" | "video"
  platform              -> e.g. "SEARCH", "YOUTUBE"           (may be missing)
  target_domain
  image                 -> image_url                          (image/video only)
  details_link | link   -> details_url (Google transparency page)
  first_shown           -> date  (unix ts int OR ISO string — normalizer handles both)
  total_days_shown      -> days actually served, not the first→last span. Present on
                           100% of creatives; 4 to 947 days observed on one advertiser.
  last_shown            -> date
  advertiser, advertiser_id
  headline / description / title -> text{}                    (text ads; verify field names live!)
```
Empty result (`{"error": "Google hasn't returned any results…"}`) still counts as a search and is **not** an exception — we store it and the competitor simply has 0 creatives.

**Verify live:** the exact keys for text-ad copy (`headline`/`description`) and whether `first_shown` is a timestamp or a string on your account. Fix the normalizer, not the callers. Re-normalizing from `snapshots.raw` costs no quota.

### B — `google` → `serp_ads_from_google(raw)`
```
raw.ads[]:
  position              -> int
  block_position        -> "top" | "bottom"   (anything containing "bottom" → bottom)
  title, description, displayed_link, link
  displayed_link|link   -> advertiser_domain (host, www. stripped)   REQUIRED
raw.shopping_results[]  -> (not used yet; product-listing ads — nice-to-have)
```
If `ads` is absent, the keyword had no paid block in that location at that moment — that's real data, store the empty list.

### C — `google_trends` TIMESERIES → `trend_points_from_timeseries(raw)`
```
raw.interest_over_time.timeline_data[]:
  timestamp             -> date  (preferred)   | date "Jun 7 – 13, 2026" (fallback parse)
  values[0].extracted_value -> int 0..100     | values[0].value (string) fallback
```

### D — `google_trends` RELATED_QUERIES → `related_queries_from_trends(raw)`
```
raw.related_queries.rising[] / .top[]:
  query
  value                 -> value_text  ("Breakout", "+450%", "100")
  extracted_value       -> value_num   (null for Breakout)
```

## 3. Where the data goes

```
snapshots      raw JSON per call (audit trail + replay)          kind = ads_transparency | search_ads | trends | related_queries
creatives      upsert by (competitor_id, creative_id); first_seen_run_id / last_seen_run_id / active
serp_ads       one row per ad per keyword per run
trend_points   one row per week per keyword per run
related_queries one row per query per keyword per run
changes        output of app/engine/diff.py (pure functions, unit-tested in tests/test_diff.py)
```

## 4. Definition of done for the backend lane

1. `pytest` green (diff engine contract).
2. `POST /demo/seed {"mode":"synthetic"}` → all read endpoints return data (no quota).
3. Put the **real** Bay Area coffee competitors + keywords in `services/api/seed/demo_config.json` (git-ignored; copy from `.example`), then `POST /demo/seed {"mode":"live"}` **once** (18 searches).
4. Open a few `snapshots.raw` rows and confirm every field in §2 maps. Fix `normalize.py` where it doesn't.
5. Second live run: `POST /watchlists/{id}/collect-and-analyze` → real `changes` + Claude `insights`.
6. Check `runs.searches_used` matches what SerpApi's dashboard shows.

## 5. Guard-rails

- Only `collect` may call SerpApi. Never from a read endpoint, never from the frontend.
- Handle `429`/`5xx` by failing the run (`runs.status = failed`, `error` set) — don't retry in a loop.
- Keep `SerpApiClient.searches_used` accurate; it's shown in the UI and the report.
- Don't commit `.cache/serpapi/` or `demo_config.json` (both git-ignored).

## 6. Optional engines (only if the core is done)

| Engine | Why | Cost |
|---|---|---|
| `google_trends` `data_type=GEO_MAP_0`, `region=DMA` | where local interest concentrates — good for a Bay Area brand | 1 / keyword |
| `google_shopping` | product-listing ads and price points for bagged beans | 1 / keyword |
| `google_maps` / `google_local` | the local pack for "coffee near me" (listings, ratings — a different signal than ads) | 1 / keyword |
| Ads Transparency **creative detail** page (`details_url`) | full ad copy / preview when the list call lacks it | 1 / creative — expensive, only on demand |

Docs: <https://serpapi.com/google-ads-transparency-center-api> · <https://serpapi.com/search-api> (`ads`) · <https://serpapi.com/google-trends-api>.
