# SerpApi Google Trends — Exhaustive Research for AdWatch

**Date of research:** 2026-09-03
**Method:** Live documentation review + **89 real API calls (71 billed searches)** against the production SerpApi Google Trends engines.
**Raw responses:** `./raw/*.json` (api_key stripped; leak-scanned clean).
**Budget:** 150 authorized / **71 spent**. Account `total_searches_left` 14,321 → 13,917 (the 404 total delta includes concurrent sibling agents sharing this key; see §0.1).

---

## 0. Executive summary — the two answers that matter

### 0.1 Multi-query comparison costs **1 search, not 5** — MEASURED

**This is a 5x cost lever and AdWatch is not using it.**

Tight before/after measurement around a single 5-term comparison call:

```
before:  total_searches_left = 14307
call:    engine=google_trends&q=car insurance,auto insurance,vehicle insurance,
         car insurance quotes,cheap car insurance&geo=US&date=today 12-m
         &data_type=TIMESERIES&no_cache=true
after:   total_searches_left = 14306
DELTA = 1
```

Confirmation burst (robust to sibling-agent noise on the shared key):

```
5 calls x 5 terms each = 25 terms total
before 14160 -> after 14152   DELTA = 8
per-request billing predicts 5 (+3 sibling noise). per-term billing predicts 25.
```

Result unambiguous: **billing is per HTTP request.** SerpApi documents this as
"The number of results returned per response will not affect the number of credits used" and
"Only successful searches are counted toward your monthly searches. Cached, errored, and failed searches are not."
— https://serpapi.com/pricing

The single call returned all 5 fully-populated series (53 weekly points each) plus an `averages` array.

**Hard limit is 5**, proven by the error response to a 6-term query:

```
q=a,b,c,d,e,f  ->  {"error": "Maximum number of queries accepted is 5, divided by a comma (,)."}
```

Docs agree: "Maximum number of queries per search is 5" and "maximum length for each query is 100 characters" — https://serpapi.com/google-trends-api

**Which data_types accept 5 queries (MEASURED):**

| data_type | multi-query | observed behaviour |
|---|---|---|
| `TIMESERIES` | yes, up to 5 | all 5 series returned + `averages` |
| `GEO_MAP` | **requires ≥2** | single query → error |
| `GEO_MAP_0` | single only | multi → `"Please change the data_type to one that supports multiple queries."` |
| `RELATED_TOPICS` | single only | as above |
| `RELATED_QUERIES` | single only | as above |

**AdWatch impact:** AdWatch's TIMESERIES call currently sends one term. It can send five for the same one search — but see §0.2, because **naively batching terms silently corrupts the values.** Read §2 before implementing.

### 0.2 Trends values are **NOT comparable run-over-run** — MEASURED, and this is a live bug

Two independent failure modes, both proven.

**(a) Google returns discrete random sample draws. Identical inputs → different numbers.**

Five identical calls, single query, **frozen absolute window** `2025-01-01 2025-12-31`, `no_cache=true`, spread over ~30 minutes:

```
q3_abs_run1 vs q3_abs_run2   differ  0/53   maxΔ=0
q3_abs_run1 vs q3_abs_run3   differ 42/53   maxΔ=5   meanΔ=1.53
q3_abs_run1 vs q4_abs_late1  differ 42/53   maxΔ=5   meanΔ=1.53
q3_abs_run1 vs q4_abs_late2  differ  0/53   maxΔ=0
q3_abs_run3 vs q4_abs_late1  differ  0/53   maxΔ=0

-> distinct sample draws observed: 2 across 5 identical calls
     draw#1: run1, run2, late2
     draw#2: run3, late1
```

Nothing about the request changed. Not the window (absolute, historical, closed). Not the query. Not the geo. Google served **one of two different sample realizations at random per request**, and 42 of 53 points differ between them by up to 5 index points.

On a **relative** window (`today 12-m`) the same experiment gave **maxΔ = 8**.

This is not drift over time and not a slow re-index — it is a coin flip per request. AdWatch cannot distinguish it from a real demand change.

**(b) Rescaling: a term's value depends on the largest term in its comparison group.**

Same term `car insurance`, same geo/date, varying group composition:

```
                    min  max   mean
SOLO (1 term)        41  100  66.34
TRIPLE               41  100  66.32   <- identical to solo on 52/53 points
FIVE-TERM            41  100  66.34   <- identical to solo on 53/53 points
PAIR w/ "facebook"    8   19  12.66   <- identical to solo on  0/53 points
```

The normalization rule (INFERRED from this data, consistent with Google's docs):
**the 100 is assigned to the single highest point across ALL terms in the group; every series is scaled against that one peak.**

Consequence: adding terms is harmless *only while every added term is smaller than the current maximum*. The moment a larger term enters the group, **every other series is rescaled downward** — here by a factor of 5.32.

**Is Monday's value comparable to Friday's?**
- Same query, same group, same absolute window: **only up to ±5 index points of sampling noise** (±8 on relative windows). Not exactly comparable.
- Relative window (`today 12-m`): additionally the window slides, so the peak that defines 100 can leave the window entirely — a step-change in every stored value with no demand change.
- Different group composition between runs: **completely incomparable**, off by an arbitrary multiplicative factor.

**AdWatch's concrete bugs today:**
1. Any "demand spike" threshold below ~8 index points fires on pure sampling noise.
2. Because the window is relative, stored history rebases whenever the trailing peak rolls out of the window.
3. If AdWatch ever batches terms to exploit §0.1, values become incomparable to previously stored single-term values.

**(c) RELATED_QUERIES is far worse — and AdWatch uses it.**

Four identical `RELATED_QUERIES` calls, `no_cache=true`, minutes apart:

```
RISING bucket (25 entries each):
  run1 vs run2:  Jaccard=0.16   18 added, 18 removed
  run1 vs run3:  Jaccard=0.02   24 added, 24 removed   <- 96% churn
  run2 vs run3:  Jaccard=0.06   22 added, 22 removed
  run1 vs run4:  Jaccard=1.00    0 added,  0 removed   <- same draw

TOP bucket (25 entries each):
  run1 vs run2:  Jaccard=0.79    3 added,  3 removed
  run1 vs run3:  Jaccard=0.61    6 added,  6 removed, 17/19 values changed
  run1 vs run4:  Jaccard=1.00    0 added,  0 removed
```

Between two identical calls, **up to 24 of 25 rising queries changed**. Example churn:

```
vanished after run1 : comcast business, comcast business cable, comcast business internet, ...
appeared in run2    : allstate renters insurance quote, cable internet providers, comcast fiber, ...
```

**Essentially every "new rising query" change event AdWatch emits is noise.** The `rising` bucket is not a stable set and must not be diffed as one. The `top` bucket is usable but still churns ~3-6 of 25 entries per run.

**Workarounds — all validated below in §7.4:** anchor-term stitching (proven to <2% error), fixed absolute windows, N-of-M consensus across repeated draws, ranking instead of level thresholds, and raising event thresholds above the measured noise floor.

---

## 1. Every `data_type` value and its complete response shape

Source: https://serpapi.com/google-trends-api. All five verified live; a sixth value rejected.

Undocumented values are rejected cleanly and **free of charge**:
`data_type=NOT_A_REAL_TYPE` → `{"error":"Unsupported `NOT_A_REAL_TYPE` data type parameter."}`

### 1.1 `TIMESERIES` — Interest over time (default)
Doc: https://serpapi.com/google-trends-interest-over-time

Field inventory (from `jq 'paths(scalars)'`, indices collapsed):
```
interest_over_time.timeline_data[].date
interest_over_time.timeline_data[].timestamp
interest_over_time.timeline_data[].partial_data
interest_over_time.timeline_data[].values[].query
interest_over_time.timeline_data[].values[].query_index
interest_over_time.timeline_data[].values[].value            (string)
interest_over_time.timeline_data[].values[].extracted_value  (int)
interest_over_time.averages[].query
interest_over_time.averages[].value
```

Observed sample (5-term call, first point):
```json
{"date":"Aug 31 – Sep 6, 2025","timestamp":"1756598400","values":[
 {"query":"car insurance","query_index":0,"value":"43","extracted_value":43},
 {"query":"auto insurance","query_index":1,"value":"24","extracted_value":24},
 {"query":"vehicle insurance","query_index":2,"value":"3","extracted_value":3},
 {"query":"car insurance quotes","query_index":3,"value":"3","extracted_value":3},
 {"query":"cheap car insurance","query_index":4,"value":"3","extracted_value":3}]}
```
`averages`: `[{"query":"car insurance","value":66}, {"query":"auto insurance","value":36}, ...]`

Notes:
- `averages` is **omitted for single-query searches** (documented; confirmed — absent in all solo runs).
- `partial_data: true` marks the final, still-accumulating bucket. AdWatch should **drop or flag partial points** — they are guaranteed to change next run for real (not noise) reasons.
- Docs: multiple geos and multiple date ranges are supported *only* for TIMESERIES, and the list length must equal the query count.

### 1.2 `GEO_MAP` — Compared breakdown by region (**requires ≥2 queries**)
Doc: https://serpapi.com/google-trends-compared-breakdown

```
compared_breakdown_by_region[].geo
compared_breakdown_by_region[].location
compared_breakdown_by_region[].coordinates.lat / .lng   (city-level only)
compared_breakdown_by_region[].max_value_index
compared_breakdown_by_region[].values[].query
compared_breakdown_by_region[].values[].value            ("60%")
compared_breakdown_by_region[].values[].extracted_value  (60)
```

Observed (`q=car insurance,auto insurance&geo=US`, 51 rows):
```json
{"geo":"US-WY","location":"Wyoming","max_value_index":0,"values":[
  {"query":"car insurance","value":"60%","extracted_value":60},
  {"query":"auto insurance","value":"40%","extracted_value":40}]}
```

**This is the single most under-appreciated endpoint for AdWatch.** Values are **share-of-voice percentages that sum to 100 within each region** — not a 0-100 index rescaled against a floating peak. A share metric is *far* more stable run-over-run than the index, because it is a ratio between the compared terms rather than a value anchored to a sampled maximum. **INFERRED** (not separately stress-tested across draws, but it follows from the construction): this is the most diff-safe numeric surface in the entire Trends API.

### 1.3 `GEO_MAP_0` — Interest by region (single query)
Doc: https://serpapi.com/google-trends-interest-by-region

```
interest_by_region[].geo
interest_by_region[].location
interest_by_region[].max_value_index
interest_by_region[].value / .extracted_value
interest_by_region[].coordinates.lat / .lng   (city-level only)
```
Observed (`geo=US`, 51 rows = 50 states + DC), values are a 0-100 index rescaled to the top region:
```json
{"geo":"US-WY","location":"Wyoming","max_value_index":0,"value":"100","extracted_value":100}
{"geo":"US-ND","location":"North Dakota","max_value_index":0,"value":"78","extracted_value":78}
```
Note `geo` is **absent** on city-level rows, which carry `coordinates` instead.

### 1.4 `RELATED_TOPICS` (single query)
Doc: https://serpapi.com/google-trends-related-topics

```
related_topics.rising[] / related_topics.top[]
  .topic.value   <- Freebase mid, e.g. "/m/02qvly"
  .topic.title
  .topic.type
  .value / .extracted_value
  .link / .serpapi_link
```
Observed: 25 rising, 24 top.
```json
{"topic":{"value":"/m/02qvly","title":"Auto insurance","type":"Insurance category"},"value":"75","extracted_value":75}
{"topic":{"value":"/m/0yp40c9","title":"Comcast Business","type":"Subsidiary"},"value":"Breakout","extracted_value":109800}
```
**`topic.value` is directly reusable as `q`** — see §6.

### 1.5 `RELATED_QUERIES` (single query)
Doc: https://serpapi.com/google-trends-related-queries

```
related_queries.rising[] / related_queries.top[]
  .query  .value  .extracted_value  .link  .serpapi_link
```
Observed: 25 rising + 25 top.
- `top` values are a 0-100 index.
- `rising` values are `"Breakout"` or `"+250%"`; `extracted_value` for Breakout is a huge synthetic number (observed up to **121,100**). Do not treat it as a percentage.
- **`value` is localized.** With `hl=es`, `"Breakout"` became `"Aumento puntual"`. **Never string-match on `"Breakout"`** — branch on `extracted_value` magnitude instead.
- Contamination is real: `car insurance` returned Comcast/Xfinity queries in the rising bucket. Google's own artifact, not SerpApi's.

---

## 2. Multi-query comparison — exact syntax and the correct way to use it

**Syntax:** comma-separated in `q`. Max 5. Max 100 chars per query. Terms and topic mids can be mixed.

```
q=car%20insurance,auto%20insurance,vehicle%20insurance,car%20insurance%20quotes,cheap%20car%20insurance
```
Verified working with mixed types in one call:
```
q=jaguar,/m/0h5wslk,/m/043vc
-> averages: [{"jaguar":11},{"/m/0h5wslk":7},{"/m/043vc":17}]
```

**Cost: 1 search.** (§0.1)

**The trap:** batching rescales everything (§0.2b). Two safe patterns:

**Pattern A — fixed anchor slot (recommended).** Reserve slot 0 for a stable, high-volume anchor term that is always the largest in the group. Every batch then normalizes against the same peak, so batches are mutually comparable and comparable over time. Proven in §7.4: recovered a term's value from a distorted group to within 1.4%.

**Pattern B — brand-vs-competitor share.** Put your brand and up to 4 competitors in one group and store only **within-group ratios** (`brand / sum(all)`), never the raw 0-100 values. Ratios are invariant to the group's scale factor. `GEO_MAP` gives you this natively as percentages (§1.2).

---

## 3. The `date` parameter grammar and granularity — MEASURED

Docs list the accepted values (https://serpapi.com/google-trends-api); **granularity is undocumented by SerpApi**, so the table below is measured.

### 3.1 Relative windows

| `date` | points returned | step | granularity |
|---|---|---|---|
| `now 1-H` | 58 | 60s | **per-minute** |
| `now 4-H` | 238 | 60s | per-minute |
| `now 1-d` | 181 | ~8 min | 8-minute |
| `now 7-d` | 169 | 3600s | hourly |
| `today 1-m` | 32 | 1d | daily |
| `today 3-m` | 93 | 1d | daily |
| `today 12-m` | 53 | 7d | weekly |
| `today 5-y` | 262 | 7d | weekly |
| `all` (2004→) | 273 | ~30d | monthly |

Sub-hourly granularity on `now 1-H` / `now 4-H` is a genuinely useful surprise — it is finer than Google Trends' own UI exposes conveniently.

### 3.2 Absolute ranges

- `yyyy-mm-dd yyyy-mm-dd` — 2004 to present
- `yyyy-mm-ddThh yyyy-mm-ddThh` — only within a ~1 week span

Measured, and **the granularity cutoffs pinned by bisection**:

| range | span | points | granularity |
|---|---|---|---|
| `2026-08-01 2026-08-31` | 31d | 31 | daily |
| `2026-01-01 2026-08-31` | 243d | 243 | daily |
| `2025-12-06 2026-08-31` | **268d** | 269 | **daily** |
| `2025-12-01 2026-08-31` | **273d** | 40 | **weekly** |
| `2021-09-01 2026-08-31` | **1825d** | 262 | **weekly** |
| `2021-06-01 2026-08-31` | **1917d** | 63 | **monthly** |
| `2020-01-01 2026-08-31` | 2434d | 80 | monthly |
| `2026-08-28T00 2026-09-02T23` | 6d | 144 | hourly |

**Cutoffs: daily → weekly between 268 and 273 days (~269d / ~9 months). Weekly → monthly at ~1826 days (5 years).**

Practical rule for AdWatch: to keep **daily** points, always request a window of **≤268 days**. `today 12-m` silently gives you weekly data — if AdWatch wants daily resolution it must use an absolute ≤268-day range.

Multiple date ranges (comma-separated, one per query) are supported for `TIMESERIES` only, and must match the query count.

### 3.3 `tz`

Minutes offset, `-1439`..`1439`, default `420`. **MEASURED: `tz` only changes the rendered `date` label — the `timestamp` is unchanged.**
```
tz=0     first point: "Sep 2, 2026 at 4:16 PM"  timestamp=1788365760
tz=-720  first point: "Sep 3, 2026 at 4:16 AM"  timestamp=1788365760
```
**AdWatch must key its time series on `timestamp`, never on the `date` string.** A `tz` config change would otherwise silently re-label every stored point and produce a full-series phantom diff.

---

## 4. Category and property filtering

### 4.1 `cat`
Full list: https://serpapi.com/google-trends-categories (downloadable JSON). Default `0` = all.
Useful IDs for paid search: `7` Finance, `12` Business & Industrial, `18` Shopping, `37` Banking, `47` Autos & Vehicles, `60` Jobs, `279` Credit & Lending, `811` Credit Cards, `960` Job Listings.

**MEASURED — `cat` is a powerful free disambiguator.** `q=jaguar`, RELATED_QUERIES:

| `cat` | top related queries |
|---|---|
| `0` (all) | jaguar car, jaguar for sale, 2026 jaguar, jaguar pace, jaguar xf |
| `47` (Autos) | jaguar for sale, jaguar car, jaguar type f, jaguar pace, jaguar xf |
| `66` (Animals) | leopard, jaguar leopard, animal jaguar, panther, black jaguar, cheetah |

Same term, completely different intent universe. Costs nothing extra.

### 4.2 `gprop`
Accepted: empty (web, default), `images`, `news`, `froogle` (Google Shopping), `youtube`.
`gprop=shopping` → `{"error":"Unsupported `shopping` property."}` — the value really is `froogle`.

### 4.3 **Does `gprop=froogle` give a distinct purchase-intent signal? YES — MEASURED**

`q=running shoes`, `geo=US`, `today 12-m`, web vs froogle:

- Pearson r = **0.934** over the full year — the broad seasonality agrees, so froogle is not noise.
- But the recent-weeks divergence is dramatic:

```
  week                    web  froogle
  Jun 21 – 27, 2026        55       36
  Jun 28 – Jul 4, 2026     31       16
  Jul 12 – 18, 2026        23        3
  Aug 9 – 15, 2026         41        4
  Aug 30 – Sep 5, 2026     23        5
```

Web interest holds at ~23-41% of its peak while shopping intent collapses to 3-5%. (Each series is independently normalized, so read the **shapes and the ratio over time**, not the absolute gap.) Informational interest persisting while commercial intent evaporates is exactly the signal a paid-search team wants — it is the classic "traffic is fine, conversions are dying" leading indicator.

Peak weeks differ per vertical, confirming these are genuinely different populations:
`web` Apr 12-18 · `froogle` May 10-16 · `youtube` May 3-9 · `news` Apr 26-May 2 · `images` Jul 12-18.

**Related-queries vocabulary also diverges — Jaccard 0.28 (only 11 of 25 shared):**

| web top | froogle top |
|---|---|
| men's running shoes, women's running shoes, **nike**, **nike shoes**, **on running shoes**, **adidas shoes** | best running shoes, running shoes women, **budget running shoes**, **best running shoes 2026**, **marathon running shoes**, **daily trainer running shoes**, **rose gold running shoes** |

Web skews to **brand** navigation; froogle skews to **commercial modifiers** (budget/best/year) and **product attributes** (colorway, use case). For keyword expansion, the froogle vocabulary is materially closer to converting paid-search queries.

---

## 5. Geo granularity — MEASURED, with two corrections to the docs

`geo` list: https://serpapi.com/google-trends-locations. Empty = Worldwide.
`region` (for GEO_MAP / GEO_MAP_0): `COUNTRY`, `REGION`, `DMA`, `CITY`.

| test | result |
|---|---|
| `geo=US`, `GEO_MAP_0`, default region | 51 rows (states + DC) |
| `geo=US`, `region=DMA` | **210 rows, Nielsen DMA codes** — `{"geo":"759","location":"Cheyenne WY-Scottsbluff NE",...}` |
| `geo=US`, `region=CITY` | error: "Google Trends hasn't returned any results" |
| `geo=US-CA`, `region=CITY` | **28 rows with lat/lng** — `{"coordinates":{"lat":34.05,"lng":-118.24},"location":"Los Angeles",...}` |
| `geo=US-CA`, `TIMESERIES` | works, 53 points |
| `geo=US-CA-807`, `TIMESERIES` | **error: "Unsupported `US-CA-807` geographic location."** |
| `geo=759`, `TIMESERIES` | **works, 53 points** |

**Two corrections worth knowing:**
1. **DMA targeting works, but the geo value is the bare numeric code (`759`), not Google's `US-CA-807` form.** The docs don't say this. Get the codes from a `region=DMA` GEO_MAP_0 call, then feed them straight back as `geo` for per-DMA time series. This maps 1:1 onto Google Ads geo-targeting.
2. `region=CITY` needs a **sub-country** `geo`; it fails at country level.

`include_low_search_volume=true` (GEO_MAP / GEO_MAP_0 only): no effect on `geo=US` (51 rows either way — every state has volume). Tested on `geo=LU` + `region=CITY`: no results with or without. **INFERRED:** it matters only for mid-sized geos where some sub-regions sit just under Google's reporting floor.

---

## 6. Related engines

### 6.1 `google_trends_autocomplete` — entity disambiguation. **It works, and it is cheap.**
Doc: https://serpapi.com/google-trends-autocomplete. Params: `engine`, `q` (required), `hl`, plus standard SerpApi params.

**MEASURED**, `q=jaguar`:
```json
{"q":"jaguar",            "title":"jaguar",              "type":"Search term"}
{"q":"/m/0h5wslk",        "title":"Jaguar",              "type":"Car make"}
{"q":"/m/043vc",          "title":"Jacksonville Jaguars","type":"Football team"}
{"q":"/g/11c5b2ln3x",     "title":"Jaguar",              "type":"Topic"}
{"q":"/m/012n8f5h",       "title":"Jaguar F-Pace",       "type":"Luxury"}
{"q":"/m/0661r43",        "title":"Jaguar F-Type",       "type":"Sports car"}
```

The `q` field is **directly usable as the `q` parameter** — proven by follow-up calls:

| `q` sent | top related queries returned |
|---|---|
| `jaguar` (string) | jaguar car, jaguar for sale, 2026 jaguar, jaguar xf |
| `/m/0h5wslk` (Car make) | jaguar, jaguar for sale, jaguar car, used jaguar, new jaguar, **audi** |
| `/m/043vc` (Football team) | jaguars, jaguars vs, jacksonville, jags, **bills** |

Complete separation of the two senses. **Yes — this lets AdWatch target the entity rather than the ambiguous string.**

**Two gotchas:**
1. **`/g/` Knowledge Graph IDs do NOT work.** `q=/g/11c5b2ln3x` → `"Google Trends hasn't returned any results for this query."` Only `/m/` Freebase mids resolve. Filter autocomplete results to `/m/` prefixes.
2. Entities and strings can be mixed in one 5-term comparison, which is the clean way to measure contamination:
   `q=jaguar,/m/0h5wslk,/m/043vc` → averages 11 / 7 / 17. The *football team* out-draws the car brand, and the raw string sits between them. A brand tracker keyed on the string `"jaguar"` would be majority-NFL noise.

`related_topics[].topic.value` (§1.4) is the same kind of mid, so RELATED_TOPICS doubles as a free entity discovery source.

### 6.2 `google_trends_trending_now` — the highest value-per-search endpoint tested
Doc: https://serpapi.com/google-trends-trending-now

Params: `engine`, `geo` (default `US`), `hours` ∈ {4, 24 (default), 48, 168}, `category_id` (19 categories, https://serpapi.com/google-trends-trending-now-categories), `only_active`, `hl`.
Geo supports sub-country (`US-CA` etc.): https://serpapi.com/google-trends-trending-now-locations

```
trending_searches[].query
trending_searches[].search_volume          <- ABSOLUTE, not an index
trending_searches[].increase_percentage
trending_searches[].active
trending_searches[].start_timestamp / .end_timestamp
trending_searches[].categories[].id / .name
trending_searches[].trend_breakdown[]      <- related query strings
trending_searches[].serpapi_google_trends_link
trending_searches[].news_page_token / .serpapi_news_link
```

**MEASURED yields, all for 1 search each:**

| call | rows |
|---|---|
| `geo=US` (default 24h) | **440** |
| `geo=US&hours=4&only_active=true` | 36 |
| `geo=US&hours=168&category_id=3` (Business/Finance) | 177 |
| `geo=US-CA` | 169 |

```json
{"query":"chatgpt","search_volume":500000,"increase_percentage":100,"active":true,
 "categories":["Technology"],"trend_breakdown":[44 related queries]}
```

Three things make this uniquely valuable:

1. **`search_volume` is an absolute number — the only absolute-volume signal in the entire Trends surface.** It is **bucketed to a 1-2-5 ladder** (measured distinct values: 100, 200, 500, 1k, 2k, 5k, 10k, 20k, 50k, 100k, 200k, 500k), so treat it as an order-of-magnitude band, not a count. `increase_percentage` is likewise bucketed (50, 75, 100, 200 … 1000).
2. **`trend_breakdown` is free keyword expansion.** `chatgpt` carried 44 related queries: `chat gpt`, `is chatgpt down`, `chatgpt login`, `claude ai`, … The 440-row US call yielded thousands of related query strings for one search.
3. Because volume is absolute and bucketed, **it is genuinely comparable run-over-run** — unlike everything else in this API. This is the one endpoint where AdWatch's diff-and-threshold model works without correction.

**Refresh cadence:** not documented by SerpApi. `hours=4` returning 36 rows vs 440 at 24h implies continuous updating. **INFERRED:** effectively real-time, with SerpApi's own 1-hour cache the binding constraint unless `no_cache=true`.

### 6.3 Discontinued engines
- `google_trends_trending_now` with `frequency=realtime` — **discontinued by Google** (https://serpapi.com/google-trends-trending-now-realtime)
- `google_trends_trending_now` with `frequency=daily` — **discontinued by Google** (https://serpapi.com/google-trends-trending-now-daily)

Do not build on either.

### 6.4 `google_trends_news`
Doc: https://serpapi.com/google-trends-news. Requires `page_token` from a Trending Now row's `news_page_token`. Returns `news[]` with `title`, `link`, `source`, `date`, `thumbnail`. Costs 1 search **per trend expanded** — expensive at scale; use only for trends that already passed a filter.

---

## 7. Normalization semantics — the correctness section

### 7.1 What Google actually does
Per https://support.google.com/trends/answer/4365533:
- "Each data point is divided by the total searches of the geography and time range it represents to compare relative popularity."
- "The resulting numbers are then scaled on a range of 0 to 100 based on a topic's proportion to all searches on all topics."
- "While only a sample of Google searches are used in Google Trends, this is sufficient because we handle billions of searches per day."

SerpApi's own explainer (https://serpapi.com/blog/google-trends-numbers-from-0-to-100-what-is-it/) adds that values change when you "Change the time period, Compare to other keyword, Select a specific city or region", and that "A score of 0 means there was not enough data for this term".

So a value is a function of **(term set, geo, time window, category, property, and the random sample draw)**. Change any one and the number changes.

### 7.2 The three independent reasons two values may not be comparable
1. **Sampling.** Different draw → up to ±5 (absolute window) or ±8 (relative window) index points. §0.2a.
2. **Rescaling by group max.** Group composition changes → arbitrary multiplicative factor (observed 5.32x). §0.2b.
3. **Sliding window.** A relative window's peak can roll out of range, rebasing the whole series.

### 7.3 Are the docs ambiguous? Partly — so here is what is measured vs stated
Google documents the *normalization* clearly. **Neither Google nor SerpApi documents the sampling non-determinism** — that identical requests return different numbers. That behaviour is well known in the research community (it motivates the calibration literature, e.g. West, *Calibration of Google Trends Time Series*, CIKM 2020, https://dlab.epfl.ch/people/west/pub/West_CIKM-20.pdf) but it is **not in the vendor docs**. Everything in §0.2 is my own measurement, not a documented guarantee, and the specific magnitudes (±5 / ±8, 2 draws, 96% rising-bucket churn) are from one term on one afternoon — the *existence* of the effect is solid, the exact magnitude will vary by term volume.

### 7.4 Workarounds — validated

**Anchor-term stitching — PROVEN to <2% error.**
Two groups sharing anchor `car insurance`:
```
grpA = car insurance, geico, progressive insurance
       averages: car insurance=66, geico=21, progressive=11
grpC = car insurance, geico, facebook          (facebook is much larger)
       averages: car insurance=12, geico=4,  facebook=81
```
Anchor mean: grpA 66.3, grpC 12.5 → scale factor **k = 5.319** (stdev 0.134 across 53 points).
Rescale grpC by k: `geico -> 21.3`. Ground truth from grpA: **21**. Error **1.4%**.

Note the degenerate-but-useful case: when the anchor is *already* the largest term in both groups, k = 1.000 exactly (measured, stdev 0.000) — the groups are natively on the same scale. **This is why Pattern A in §2 works: keep a dominant anchor in slot 0 and you never need to rescale at all.**

**Other mitigations, in order of effort:**
- **Use absolute windows, not relative.** Removes failure mode 3 entirely.
- **Store `timestamp`, never the `date` label** (§3.3).
- **Drop or flag `partial_data` points.**
- **Threshold above the noise floor.** Nothing below ~±8 index points on a relative window is a signal. Prefer a percentage-of-baseline test with a floor, plus a minimum absolute delta.
- **N-of-M consensus for RELATED_QUERIES.** Since draws are discrete, issue the call 3x with `no_cache=true` (3 searches) and only emit an event for entries present in ≥2 draws. This directly kills the 96%-churn problem.
- **Prefer ratio/share surfaces over index surfaces**: `GEO_MAP` percentages (§1.2), within-group ratios (§2 Pattern B), and Trending Now's absolute `search_volume` (§6.2) are all structurally more diff-safe than a 0-100 index.
- **Rank, don't level.** Diff the *ordering* of the `top` bucket rather than the values; ordering was materially more stable than values (Jaccard 0.61-1.00 on `top` vs 0.02-0.16 on `rising`).

### 7.5 SerpApi's cache interacts with this — MEASURED
Repeating an identical query inside the 1-hour cache window returns the **same `search_metadata.id`**, byte-identical data, and **costs 0 searches**:
```
call 1 (fresh)        id=6a999d4cc75443919d07684b
call 2 (repeat)       id=6a999d4cc75443919d07684b   identical series, delta=0 credits
call 3 (no_cache)     id=6a999d4ed1a72be81fa8ac97   new draw
```
Implication both ways: AdWatch runs <1h apart will diff against a cached identical response and see **zero change** (falsely stable); runs with `no_cache=true` get a fresh draw and may see **phantom change**. Neither is a real signal. Pick a schedule >1h and understand which regime you are in.

---

## 8. Untapped opportunities, ranked by value-per-search

All costs are additional searches per monitored subject per run.

| # | `event_kind` | Trigger | Why paid search cares | Cost |
|---|---|---|---|---|
| **1** | `trending_now_surge` | New row in `google_trends_trending_now` (`geo`, `category_id`) whose `query` matches a watched brand/product regex, or `increase_percentage ≥ 300` with `search_volume ≥ 10k` | The **only absolute-volume, genuinely diff-safe** signal available. Catches demand spikes hours before they appear in weekly TIMESERIES. Bid up / raise budget caps same-day. | **1 per geo — covers ALL terms at once (440 rows)** |
| **2** | `competitor_share_shift` | `GEO_MAP` with brand + 4 competitors; a region's `extracted_value` share moves >5pp vs prior run | Share-of-voice percentages are ratio-based, so **immune to the rescaling bug**. Tells you exactly which DMAs a competitor is gaining in — maps onto geo bid modifiers. | **1 for 5 brands** |
| **3** | `batch_demand_shift` | Move AdWatch's TIMESERIES to a 5-term group with a fixed anchor in slot 0 (§2 Pattern A) | Same signal AdWatch has now, **5 terms for the price of 1**, and the anchor makes values comparable across runs — fixing the existing bug while cutting cost 5x. | **0 (replaces existing call), −4 vs 5 separate calls** |
| **4** | `shopping_intent_divergence` | `gprop=froogle` TIMESERIES alongside web; froogle drops >25% while web stays flat (or vice versa) | Measured to genuinely diverge (§4.3). Commercial intent collapsing while informational interest holds is a **leading indicator of conversion-rate decline** — the highest-value early warning in the list. | 1 |
| **5** | `dma_demand_hotspot` | `GEO_MAP_0` + `region=DMA` (210 rows, 1 search); a DMA's rank rises >20 places | Nielsen DMA codes map **1:1 onto Google Ads geo targeting**. Actionable without translation. Feed the bare code back as `geo` for follow-up. | **1 for 210 DMAs** |
| **6** | `entity_contamination_alert` | Compare `brand string` vs its `/m/` mid in one call; ratio shifts >20% | Proves how much of a brand term's volume is actually the brand (§6.1: "jaguar" was majority-NFL). Prevents bidding on contaminated volume. One-time per brand, then periodic. | 1 (+1 autocomplete, once) |
| **7** | `rising_query_consensus` | Replace today's single RELATED_QUERIES call with 3x `no_cache`, emit only entries in ≥2 draws | **Fixes a live bug.** Today ~all rising-query events are noise (§0.2c). Cost rises but signal goes from ~0 to real. | +2 |
| **8** | `category_intent_split` | Same term at `cat=0` vs a vertical `cat`; divergence indicates intent drift | Cheap disambiguation without entity IDs; catches a term drifting into a different meaning (seasonal/news-driven). | 1 |
| **9** | `breakout_topic_emergence` | `RELATED_TOPICS` rising with `type` in {Company, Brand, Subsidiary} and Breakout | Surfaces **new competitors as entities**, not strings — catches a rival brand launching before it shows up in query data. Same consensus caveat as #7. | 1 (×3 for consensus) |
| **10** | `intraday_demand_spike` | `date=now 1-d` (8-min points) or `now 4-H` (per-minute); >3σ vs trailing | Sub-hourly resolution for launch-day / news-cycle monitoring. Too noisy and too expensive for routine use; reserve for active-campaign windows. | 1 per poll |

**Recommended first three changes, in order:**
1. **#3** — free, cuts cost 5x, and fixes the comparability bug in the process.
2. **#1** — one call per geo replaces per-term polling and gives absolute volumes.
3. **#7** — costs +2 searches but converts an existing, actively-misleading event into a real one.

---

## 9. Operational notes (measured)

- **Errors cost 0 searches.** Verified: 3 deliberately malformed calls, `total_searches_left` delta = **0**. Parameter validation is free — validate aggressively before spending.
- **Error messages are precise and machine-usable:**
  `"Maximum number of queries accepted is 5, divided by a comma (,)."`
  `"Unsupported `ZZZZ` geographic location."`
  `"Unsupported `shopping` property."`
  `"Please change the `data_type` to one that supports multiple queries."`
  `"Google Trends hasn't returned any results for this query."`
- **"No results" is returned as an `error`, not an empty series.** AdWatch must treat it as *absence of data*, not as zero demand — a low-volume term will produce this intermittently.
- **No rate limiting observed.** 89 calls in ~45 min, `account_rate_limit_per_hour: 200000`. No 429s, no throttling, no upstream Trends blocks.
- **`csv=true`** returns a `csv` array of raw CSV lines (`"Category: All categories"`, `"Week,car insurance: (United States)"`, …) alongside the JSON. Not useful for AdWatch; the JSON is richer.
- **`hl` localizes value labels** — `"Breakout"` → `"Aumento puntual"` under `hl=es`. Pin `hl=en` or branch on `extracted_value`.
- **`json_restrictor`** can trim payloads (e.g. `interest_over_time.timeline_data[].{timestamp,values}`) — no cost change, but worthwhile for the 440-row Trending Now response.

---

## 10. DOCUMENTED vs OBSERVED

| Claim | Documented | Observed | Verdict |
|---|---|---|---|
| Max 5 queries per search | yes | yes (6 → error) | confirmed |
| 5-term call costs 1 search | implied by pricing | **delta = 1**, burst 25 terms → 5 | **confirmed empirically** |
| Errored/cached searches are free | yes | delta = 0 for both | confirmed |
| `data_type` values (5) | yes | all 5 work; 6th rejected | confirmed |
| GEO_MAP requires ≥2 queries | yes | yes | confirmed |
| `region` options COUNTRY/REGION/DMA/CITY | yes | DMA→210 rows; CITY needs sub-country geo | **partly corrected** |
| DMA as a `geo` value | not documented | `US-CA-807` fails; **bare `759` works** | **undocumented, corrected** |
| `/g/` Knowledge Graph IDs as `q` | not stated | **fail**; only `/m/` mids work | **undocumented gotcha** |
| Autocomplete `q` reusable as `q` | yes ("Topics are encoded… use Autocomplete API") | yes, full sense separation | confirmed |
| Granularity by window length | **not documented by SerpApi** | full table measured; cutoffs 269d / 1826d | **newly measured** |
| `tz` affects timestamps | ambiguous | **label only; timestamp unchanged** | **clarified** |
| `gprop=froogle` is a distinct signal | not addressed | r=0.934 but large recent divergence; vocab Jaccard 0.28 | **newly measured** |
| `include_low_search_volume` effect | yes (GEO_MAP only) | no effect on US; untestable on LU | inconclusive |
| Identical requests return identical data | **not addressed anywhere** | **NO — 2 discrete draws, ±5/±8 pts** | **undocumented; critical** |
| RELATED_QUERIES bucket stability | **not addressed anywhere** | **rising churns up to 96% between identical calls** | **undocumented; critical** |
| Anchor stitching corrects rescaling | community technique only | **works to 1.4% error** | **validated** |
| Trending Now `search_volume` absolute | field documented, semantics not | **absolute, bucketed 1-2-5 ladder** | **clarified** |
| Trending Now refresh cadence | not documented | continuous (INFERRED) | inferred |

---

## 11. Sources

- https://serpapi.com/google-trends-api
- https://serpapi.com/google-trends-interest-over-time
- https://serpapi.com/google-trends-related-queries
- https://serpapi.com/google-trends-related-topics
- https://serpapi.com/google-trends-compared-breakdown
- https://serpapi.com/google-trends-interest-by-region
- https://serpapi.com/google-trends-autocomplete
- https://serpapi.com/google-trends-trending-now
- https://serpapi.com/google-trends-trending-now-categories
- https://serpapi.com/google-trends-trending-now-locations
- https://serpapi.com/google-trends-trending-now-realtime (discontinued)
- https://serpapi.com/google-trends-trending-now-daily (discontinued)
- https://serpapi.com/google-trends-news
- https://serpapi.com/google-trends-locations
- https://serpapi.com/google-trends-categories
- https://serpapi.com/pricing
- https://support.google.com/trends/answer/4365533
- https://serpapi.com/blog/google-trends-numbers-from-0-to-100-what-is-it/
- https://dlab.epfl.ch/people/west/pub/West_CIKM-20.pdf (calibration / stitching literature)
- https://www.chris-green.net/post/trends-stitcher (anchor stitching technique)
- Live measurements: 89 calls, 71 billed, raw JSON in `./raw/`
