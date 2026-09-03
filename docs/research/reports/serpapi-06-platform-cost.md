# SerpApi: Platform, Quota & Cost-Control Reference for AdWatch

Research date: **2026-09-03**. All claims cite live documentation at serpapi.com, and the
high-value claims are additionally **verified by live measurement** against a real API key
(Free Plan + extra credits). Inference is marked `INFERRED`. Doc silence is marked explicitly.

Measurement artifacts: `raw/` (every request/response + before/after account reading),
`ledger.jsonl` (every account poll), `exp1-cache.json` … `exp7-async.json`.
**Budget used: 10 billed searches of the 100 allotted.** No API key appears in any saved file
(audited: 1,137 files scanned, clean).

---

## 0. Executive answers to the two highest-value questions

| Question | Answer | Evidence |
|---|---|---|
| **Does a cache hit cost a search?** | **No. Free.** | Doc + measured: 12 cache hits in 0.48 s → **credit delta 0/−1** (ambient noise ~1/s). All 12 returned the *identical* `search_metadata.id` as the original — SerpApi replays the stored search record, it does not create a new one. |
| **Is the Search Archive API free?** | **Yes, free.** | Measured: 12 archive fetches in 0.47 s → **credit delta 0**. No new `search_metadata.id` created. Retention **31 days** (documented). Docs are *silent* on cost — this is a measured result, not a documented one. See §4 caveat. |

**Verdict on AdWatch's current cost model: it OVER-REPORTS spend.** AdWatch counts one search
per API call. In reality cache hits (within 1 h, identical params), archive re-fetches,
Account API calls, and Locations API calls are all free, and all 4xx validation errors are free.
See §11 for the corrected accounting rules.

---

## 1. Account API

**Endpoint:** `GET https://serpapi.com/account.json` (also `…/account`)
**Params:** `api_key` (required) — the only parameter.
**Cost:** free. *"Account API is free of charge, and using it will not be counted toward your monthly quota."*
Source: <https://serpapi.com/account-api>

**Measured:** ~60 account polls issued during this research produced no attributable credit
consumption (repeated 3 s idle windows containing 2 account calls returned delta 0).

### Response — verbatim documented example

```json
{
  "account_id": "5ac54d6adefb2f1dba1663f5",
  "api_key": "SECRET_API_KEY",
  "account_email": "demo@serpapi.com",
  "account_status": "Active",
  "plan_id": "bigdata",
  "plan_name": "Big Data Plan",
  "plan_monthly_price": 250.0,
  "plan_renewal_date": "2026-10-03",
  "searches_per_month": 30000,
  "plan_searches_left": 5958,
  "extra_credits": 0,
  "total_searches_left": 5958,
  "this_month_usage": 24042,
  "this_hour_searches": 87,
  "last_hour_searches": 42,
  "account_rate_limit_per_hour": 6000
}
```

### Field semantics

| Field | Meaning | Note for AdWatch |
|---|---|---|
| `account_id` | Account identifier | |
| `api_key` | Echoes the key back | **Strip before logging.** AdWatch must never persist this response raw. |
| `account_email` | Billing email | |
| `account_status` | e.g. `Active` | Good health-card signal |
| `plan_id` / `plan_name` | e.g. `free` / `Free Plan` | |
| `plan_monthly_price` | Float USD | Doc example says `250.0` for Big Data while the pricing page says **$275** — the doc example is stale. Do not use this field for pricing. |
| `plan_renewal_date` | Next billing date; **`null`** for accounts with no active monthly plan | This is the "reset date". Must be null-guarded. |
| `searches_per_month` | Plan quota | |
| `plan_searches_left` | Remaining **plan** searches | **Not the right "remaining" number** — see below |
| `extra_credits` | Purchased/rollover credits | |
| `total_searches_left` | `plan_searches_left + extra_credits` | **This is the field the health card should display** |
| `this_month_usage` | Searches used this month | See caveat below |
| `this_hour_searches` / `last_hour_searches` | Rate-limit buckets | Use for back-off headroom |
| `account_rate_limit_per_hour` | Hourly throughput ceiling | Compare against `this_hour_searches` |

### MEASURED: how the quota fields actually interact

Live account observed over ~15 minutes and 10 billed searches:

```
plan_name            "Free Plan"
searches_per_month   250
plan_searches_left   250      <- NEVER moved
this_month_usage     0        <- NEVER moved
extra_credits        14059 -> 13774   <- all consumption landed here
total_searches_left  14309 -> 14024   <- tracked extra_credits exactly
plan_renewal_date    null
account_rate_limit_per_hour  200000
```

Two consequences AdWatch's health card must handle:

1. **Extra credits are drawn down first.** On this account `plan_searches_left` stayed pinned at
   250 and `this_month_usage` stayed at 0 while thousands of credits drained. A health card that
   displays `plan_searches_left` (or `searches_per_month - this_month_usage`) would have shown
   "250 remaining, 0 used" indefinitely while real capacity fell. **Display
   `total_searches_left`.** `INFERRED` (from this account's behaviour): `this_month_usage` counts
   only plan searches, not extra-credit searches, so it is not a reliable "spent this month"
   figure for credit-funded accounts.
2. **`plan_renewal_date` is `null` here**, so "resets in N days" must degrade gracefully. Docs
   confirm: *"`plan_renewal_date` is `null` for accounts without an active monthly plan."*

### MEASURED WARNING: the counter is eventually-consistent and non-monotonic

Polling `account.json` every 2 s while issuing **no** searches produced deltas including
**+5, −13, +8, −10** (see `ledger.jsonl`, `scan*` entries). The remaining-credit figure can move
**backwards and forwards** between reads.

> **Do not difference `total_searches_left` to compute per-call cost, and do not present it as a
> precise real-time ledger.** Treat it as an eventually-consistent gauge. AdWatch's own ledger
> (counting billed calls locally) is the more accurate instrument; the Account API is for
> reconciliation and headroom display only. Round/soften it in the UI.

---

## 2. `json_restrictor`

**Current name is `json_restrictor`.** Supported on **all engines**.
Docs: <https://serpapi.com/json-restrictor> and the SerpApi-parameters block of
<https://serpapi.com/search-api>.

Doc text: *"Parameter defines the fields you want to include in the output, reducing payload size
for faster response."* and *"Restrict your response to the fields you need for smaller, faster
results and more efficient client-side parsing."*

### Syntax (documented operators)

| Operator | Example | Meaning |
|---|---|---|
| Object index `.<string>` | `foo.bar` | Field `bar` of object `foo` |
| Array index | `foo[0]` | First item of array `foo` |
| Full array | `foo[]` | All items of array `foo` |
| Array slice | `foo[0:2]` | First two items (half-open: includes first index, not last) |
| Subquery `.{q1, q2, …}` | `foo.{bar, baz[].qux}` | Fields `bar` and `baz[].qux` of `foo` |

Documented examples: `organic_results` · `local_map, organic_results[0]` ·
`organic_results[0:3]` · `organic_results[].title` · `organic_results[].{title, snippet}` ·
`organic_results[].{title, sitelinks.inline[].link}`

### MEASURED: what it does and does not save

| | bytes | wall time |
|---|---|---|
| `q=running shoes` full JSON | **200,565** | 5.42 s |
| same + `json_restrictor=organic_results[].{title,link}` | **1,216** | 5.08 s |
| `q=wireless earbuds` full JSON | **194,521** | 7.24 s |
| same + restrictor (metadata preserved) | **1,374** | 4.50 s |

- **Payload: ~99.3% reduction.** Real and large.
- **Latency: essentially unchanged for the scrape itself.** The upstream fetch still happens; only
  transfer and parse shrink. Do not promise a latency win.
- **Cost: NO saving. It does not reduce quota.** The docs claim only payload size and parsing
  efficiency — they say nothing about cost — and measurement confirms a full billed scrape occurs.

### THREE MEASURED GOTCHAS — all cost- or correctness-relevant

**(a) `json_restrictor` strips `search_metadata` entirely.**
With `json_restrictor=organic_results[].{title,link}` the response top-level keys were
**`["organic_results"]` only**. No `search_metadata`, so **no `search_id` and no `status`** —
AdWatch would lose the archive handle its diff engine needs and lose the error/status
discriminator. Fix: request it explicitly. This works and was verified:

```
json_restrictor=search_metadata.{id,status,total_time_taken},
                search_information.organic_results_state,
                organic_results[].{title,link}
```
→ 194,521 → **1,374 bytes** while retaining `search_metadata.id` and `status`.

**(b) `json_restrictor` is part of the cache key — it BUSTS the cache and can cost you a search.**
Measured sequence on identical `q=wireless earbuds`:

| call | params | `search_metadata.id` | wall | interpretation |
|---|---|---|---|---|
| x1 | plain | `…fb6a` | 7.24 s | fresh scrape, **billed** |
| x2 | plain | `…fb6a` (same) | 0.44 s | **cache hit, free** |
| x3 | plain + `json_restrictor` | `…20fc` (**new**) | 4.50 s | **fresh scrape, billed again** |
| x4 | plain + same `json_restrictor` | `…20fc` (same) | 0.05 s | cache hit, free |

Restricted queries cache among *themselves*, but a restricted call will **not** hit an
unrestricted call's cache. `INFERRED` (mechanism): `json_restrictor` participates in the cache
key, consistent with the documented rule *"A cache is served only if the query and all parameters
are exactly the same."*
→ **Rule for AdWatch: pick restricted-or-not per query signature and never mix.** Mixing
double-bills. Also fold `json_restrictor` into AdWatch's local cache-key hash, or the local cache
will return the wrong shape.

**(c) A malformed restrictor silently returns `{}` after a full billed scrape.**
`json_restrictor=organic_results[].{` (unbalanced brace) returned **HTTP 200**, body literally
`{}` (3 bytes), **no `error` key**, after a real **5.94 s** scrape. That is a paid search
returning zero usable data with no failure signal.
→ **AdWatch must validate its restrictor strings and treat an empty/`{}` response as a hard
alarm, not an empty result.**

### Related: `output=md` is a cheaper payload win with no cache penalty

`output=md` (markdown, "optimized for LLMs and AI agents"; also `/search.md` or header
`Accept: text/markdown`) — measured on the same cached query: **194,521 → 28,445 bytes (−85%)**,
and it returned the **same `search_metadata.id`**, i.e. it **served from cache** (0.73 s) rather
than re-scraping. Unlike `json_restrictor`, `output` did not bust the cache in this test.
`INFERRED`: `output` is applied post-cache while `json_restrictor` is part of the cache key.
The two can be combined (documented: *"JSON Restrictor and Markdown output can be used together
for even smaller responses"*).

---

## 3. Caching semantics — THE COST QUESTION

Source: `no_cache` in <https://serpapi.com/search-api>, verbatim:

> **"Parameter will force SerpApi to fetch the Google results even if a cached version is already
> present. A cache is served only if the query and all parameters are exactly the same. Cache
> expires after 1h. Cached searches are free, and are not counted towards your searches per
> month.** It can be set to `false` (default) to allow results from the cache, or `true` to
> disallow results from the cache. `no_cache` and `async` parameters should not be used together."

Corroborated on the pricing page FAQ (<https://serpapi.com/pricing>), verbatim:

> **"Only successful searches are counted toward your monthly searches. Cached, errored, and
> failed searches are not.** The number of results returned per response will not affect the
> number of credits used—responses with 100 results or empty result sets will both count as 1
> search."

### MEASURED confirmation

Identical query issued three times (`exp1-cache.json`):

| call | params | `search_metadata.id` | `created_at` | wall | credit delta |
|---|---|---|---|---|---|
| c1 | plain | `6a999ace759dbcfa47aa1b38` | 16:05:34 | 33.67 s | (noisy) |
| c2 | plain (repeat) | **`6a999ace759dbcfa47aa1b38`** (identical) | **16:05:34** (identical) | **0.041 s** | **0** |
| c3 | plain + `no_cache=true` | `6a999af4d1a72be10441ff23` (**new**) | 16:06:12 | 3.43 s | billed |

Noise-proof burst (`exp3-burst.json`): **12 cache hits in 0.48 s → credit delta −1**
(3 s idle controls around it: −2, 0, −2). Had they been billed the delta would have been ≤ −12.

The cache hit returns the *same stored search record* — same `id`, same `created_at`, same
`total_time_taken` (33.52). Nothing new is created, so nothing is billed.

### Answers

- **`no_cache=true`** forces a fresh upstream fetch, creating a **new, billed** search record.
- **Server-side cache TTL: 1 hour.**
- **Cache key: the query and *all* parameters exactly** — including `json_restrictor` (measured,
  §2b), including `api_key`? `INFERRED`: not tested across accounts; assume per-account.
- **A cache hit does NOT cost a search.** Definitive, documented twice and measured two ways.
- `no_cache` and `async` **should not be used together** (documented).

### Product implication (important — this is a public-page number)

AdWatch's Usage page prices the month assuming every call is billed. That is **wrong in the
over-reporting direction** whenever the same query+params repeats inside 1 h. For AdWatch's
tuned plan cadence the effect is probably small (a 6-hourly or daily cadence never lands inside
the 1 h window), **but the naive 6-hourly projection is unaffected too, for the same reason.**
Where it *does* bite is retries, manual "refresh now" clicks, multi-tenant workspaces watching
overlapping keyword/location pairs, and any backfill loop — those can collapse to free.
Recommendation: keep the projection as-is (it is conservative and defensible) but stop counting
*observed* cache hits as spend in the ledger, and label the projection "assumes no cache reuse".

---

## 4. Search Archive API

Docs: <https://serpapi.com/search-archive-api>

**Endpoint:** `GET https://serpapi.com/searches/{search_id}.json?api_key=…`
Responses also carry a token form: `search_metadata.json_endpoint` =
`https://serpapi.com/searches/{token}/{search_id}.json` (both work).

**Params:** `search_id` (required, from `['search_metadata']['id']`), `api_key` (required),
`output` (optional: `json` default, `html` for raw HTML, `json_with_pixel_position`, `.md`).

**Retention — verbatim:** *"You can retrieve the `html`, or the `json` of your search up to
**31 days** after the search has been completed."* Expired archives return **HTTP 410 Gone**
(*"The search expired and has been deleted from the archive."* —
<https://serpapi.com/api-status-and-error-codes>).

**Searches need not be complete to be retrieved:** status may be `Queued`, `Processing`,
`Success`, or an error.

### Cost — DOC SILENCE, resolved by measurement

> The Search Archive API page **does not state whether re-fetching costs a search.** I am not
> resolving that silence in the convenient direction; here is the measurement.

`exp2-archive.json` — three single re-fetches of the same `search_id`: deltas **0, −1, 0**
(ambient noise ~1 credit/s).
`exp3-burst.json` — **12 archive fetches in 0.47 s → credit delta 0**, bracketed by 3 s idle
controls of −2, 0, −2. If each cost a search the delta would have been ≤ −12.
Every fetch returned the identical stored record (`id`, `created_at`, `total_time_taken` all
unchanged) in 39–173 ms; **no new search record is created**.

Supporting doc signal: the error-codes page classifies Search Archive as an **"Extra API"**
alongside Locations and Account — *"This includes all of our APIs except for the Extra APIs
(Location API, Account API, Search Archive API etc.)"* — and the two other Extra APIs are
documented free (Account explicitly; Locations measured free, §9).

**Conclusion: Search Archive re-fetch is free.** High confidence (strong measurement + category
consistency), but flagged as *measured, not documented* — if SerpApi ever bills it, the docs
would not have warned us.

### Lever for AdWatch

This is large. Persist `search_metadata.id` with every run and AdWatch can, for **31 days**:
re-run the diff engine after a parser change, backfill new extracted fields, re-render historical
snapshots, and fetch `output=html` for debugging — **all at zero quota cost**. Combined with
§2a, ensure the restrictor always retains `search_metadata.id` or this lever is lost.

---

## 5. Async / batch

`async` is documented in the SerpApi-parameters block of <https://serpapi.com/search-api>, verbatim:

> *"Parameter defines the way you want to submit your search to SerpApi. It can be set to `false`
> (default) to open an HTTP connection and keep it open until you got your search results, or
> `true` to just submit your search to SerpApi and retrieve them later. In this case, you'll need
> to use our Searches Archive API to retrieve your results. `async` and `no_cache` parameters
> should not be used together. `async` should not be used on accounts with **Ludicrous Speed**
> enabled."*

### MEASURED full round trip (`exp7-async.json`)

Submit with `async=true` returned in **0.13 s**, HTTP 200, 786 bytes:

```json
{
  "search_metadata": {
    "id": "6a999c1a73d2240c16e73849",
    "status": "Processing",
    "json_endpoint": "https://serpapi.com/searches/<token>/6a999c1a73d2240c16e73849.json",
    "markdown_endpoint": "...",
    "created_at": "2026-09-03 16:11:06 UTC",
    "processed_at": null,
    "google_url": "...",
    "total_time_taken": 0.0
  },
  "search_parameters": { "engine": "google", "q": "noise cancelling headphones", ... }
}
```

Retrieval: poll the Search Archive endpoint. `status` went `Processing` → `Processing` → `Success`
in **2 polls (~4 s)**; the final fetch returned the full 156,602-byte result with 9 organic results.

- **Cost: 1 search, same as a sync call.** Polling is free (archive is free, §4), so async adds
  no quota cost.
- **Batch:** there is no bulk-submit endpoint. Concurrency is achieved by firing many async
  submits; the constraint is hourly throughput (§6), not a documented batch API.
- **Caveats:** don't combine with `no_cache`; don't use on Ludicrous Speed accounts.

**For AdWatch:** async is the right shape for a scheduled sweep — submit N keyword×location
searches in ~0.13 s each, then drain them from the archive for free. It converts a long-held
connection budget into a cheap poll loop and removes per-request timeout risk.

---

## 6. Rate limits and concurrency

Per-plan **throughput** (guaranteed *successful searches per hour*), from <https://serpapi.com/pricing>:

| Plan | Price/mo | Searches/mo | Throughput/hr |
|---|---|---|---|
| **Free** | $0 | **250** | **50** |
| Starter | $25 | 1,000 | 200 |
| Developer | $75 | 5,000 | 1,000 |
| Production | $150 | 15,000 | 3,000 |
| Big Data | $275 | 30,000 | 6,000 |
| Searcher | $725 | 100,000 | 20,000 |
| Volume | $1,475 | 250,000 | 50,000 |
| Infrastructure | $2,750 | 500,000 | 100,000 |
| Cloud 1M | $3,750 | 1,000,000 | 110,000 |
| … Cloud 54M | $106,050 | 54,000,000 | 640,000 |

Doc guidance, verbatim: *"N successful searches per hour is the guaranteed throughput for this
plan. To improve performance, distribute your searches evenly throughout the hour and across
multiple hours."*

**There is no documented per-plan *concurrency* (parallel-connection) cap** — the published limit
is hourly throughput only. `INFERRED`: concurrency is effectively bounded by throughput ÷ latency;
smoothing over the hour is the documented mitigation.

**Live account read:** `account_rate_limit_per_hour: 200000` on a Free Plan — i.e. this key's
hourly ceiling has been raised well above the published Free tier value of 50. **AdWatch must read
`account_rate_limit_per_hour` from the Account API rather than inferring it from `plan_name`.**

### Throttle error shape (from <https://serpapi.com/api-status-and-error-codes>)

**HTTP 429 Too Many Requests** — *"The number of requests sent using this API key exceeds the
hourly throughput limit **OR** your account has run out of searches."*

```json
{ "error": "Your account has run out of searches." }
```

> **The two conditions share status 429.** AdWatch must disambiguate by body string, not status
> code: *"…run out of searches"* is terminal for the billing period (do not retry), whereas a
> throughput 429 is transient (back off and retry). If the body does not match the
> out-of-searches string, treat it as throughput and retry with exponential back-off.
> Not measured — the 200,000/hr ceiling on this key made a safe throttle test impossible.

Full HTTP status table: `200` OK · `400` Bad Request · `401` Unauthorized · `403` Forbidden
(account deleted) · `404` Not Found · `410` Gone (archive expired) · `429` Too Many Requests ·
`500`/`503` Server Error.

---

## 7. Error semantics — and AdWatch's "soft error" accounting

Source: <https://serpapi.com/api-status-and-error-codes> plus the pricing FAQ.

Two distinct response families:

1. **Extra APIs and request-validation failures** → non-2xx, body is `{"error": "…"}` only, no
   `search_metadata`.
2. **Search APIs** → `search_metadata.status` is `Processing` → `Success` | `Error`. A top-level
   `error` key may be present **even on `Success`**: *"if a search has failed or contains empty
   results, the top level `error` key will contain an error message."*

The decisive documented sentence:

> *"Note that if a search returns empty results due to no results returned by the search engine,
> it is still considered successful from SerpApi's perspective and will have a `status` value of
> `Success`."*

…combined with the pricing FAQ: *"responses with 100 results or empty result sets will both count
as 1 search."*

### MEASURED error battery (`exp6-errors.json`)

| # | Trigger | HTTP | `search_metadata.status` | `search_id` created | Body | Billed? |
|---|---|---|---|---|---|---|
| e1 | missing `q` | **400** | — | no | `{"error":"Missing query \`q\` parameter."}` | **No** |
| e2 | invalid api_key | **401** | — | no | `{"error":"Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}` | **No** |
| e3 | `engine=not_an_engine` | **400** | — | no | `{"error":"Unsupported \`not_an_engine\` search engine."}` | **No** |
| e4 | `device=toaster` | **400** | — | no | `{"error":"Unsupported \`toaster\` device."}` | **No** |
| e5 | `location=Zzzyx Nowhere Land` | **400** | — | no | `{"error":"Unsupported \`Zzzyx Nowhere Land\` location - location parameter."}` | **No** |
| e6 | nonsense `advertiser_id` (Ads Transparency) | **200** | `Success` | **yes** `6a999bfa…` | `{"error":"Google Ads Transparency Center hasn't returned any results for this search.", …}` | **YES** |
| e7 | malformed `json_restrictor` | **200** | — (stripped) | — | `{}` (3 bytes, **no error key**), 5.94 s scrape | **YES** |
| c1 | obscure query, zero results | **200** | `Success` | **yes** `6a999ace…` | `{"error":"Google hasn't returned any results for this query.", "search_information":{"organic_results_state":"Fully empty"}, …}` | **YES** |

All 4xx validation failures returned in **0.12–0.16 s** (rejected before any scrape) with **credit
delta 0**. The 200-with-`error` cases each performed a real upstream fetch (0.58 s / 5.9 s / 33.7 s)
and created a search record.

### Classification for AdWatch

**(a) Billed** — a search record exists (`search_metadata.id` present, `status: "Success"`):
- Empty result sets: `"Google hasn't returned any results for this query."`,
  `"<Engine> hasn't returned any results for this search."` — HTTP 200, `status: Success`,
  usually with `search_information.*_state: "Fully empty"`.
- Any successful search regardless of result count.
- A malformed-`json_restrictor` `{}` response (silent, no error key).

**(b) Unbilled failure** — no search record:
- All 4xx: `400` missing/unsupported parameter, `401` invalid key, `403` deleted account,
  `404` not found, `410` archive expired, `429` throttle or out-of-searches.
- `search_metadata.status: "Error"` (HTTP 503), e.g.
  `{"error": "We couldn't get valid results for this search. Please try again later."}` —
  proxy timeouts and internal errors. Documented as not counted (*"Cached, errored, and failed
  searches are not"*). `INFERRED` for the 503/`status: Error` case specifically: not
  independently measured, since it cannot be triggered on demand.
- Cache hits (§3).

**(c) Legitimately empty but valid** — this is a **subset of (a), i.e. BILLED**:
`status: "Success"` + top-level `error` + `*_state: "Fully empty"`. Semantically empty,
financially a full search.

Note the inverse trap: `error` is **absent** when results *are* returned even if the query was
altered — spelling fixes (`spelling_fix`, `organic_results_state: "Some results for exact spelling
but showing fixed spelling"`), `query_feedback`, and `results_for` all return 200 with no `error`.

### VERDICT on AdWatch's current accounting

AdWatch logs these as "soft errors" and **keeps them as spent searches**.

- **For (a)/(c) — empty-result 200s — that is CORRECT.** They are billed. Keep counting them.
- **For (b) — 4xx validation failures and `status: "Error"` 503s — that is WRONG; AdWatch
  over-reports.** These cost nothing. A run that fails on a bad `location` string or a typo'd
  parameter currently inflates AdWatch's reported spend and its projection.

**The discriminator is not the presence of the `error` key — it is `search_metadata.status`.**
Recommended rule:

```
billed  ==  http_status == 200
        &&  search_metadata.status == "Success"
        &&  search_metadata.id is present
```

Everything else is free. Note this rule needs `search_metadata` in the response — see §2a. And
the `{}` malformed-restrictor case defeats it (no metadata at all), so treat an empty-object
response as billed *and* alarm on it.

---

## 8. Webhooks / callbacks

**There is no push mechanism.** The complete SerpApi parameter list on
<https://serpapi.com/search-api> is: `engine`, `device`, `no_cache`, `async`, `zero_trace`,
`api_key`, `output`, `json_restrictor` — **no webhook or callback parameter**. Neither the
Search API, Search Archive API, nor Account API docs describe an outbound notification.
I grepped the rendered doc pages: every occurrence of "callback" is JavaScript (reCAPTCHA
handlers, Chart.js tick formatters), not an API feature.

A generic web search surfaced a claim that SerpApi "sends the payload as a POST request to the
webhook URL" — **I could not substantiate this in any documentation and believe it conflates
user-built integrations** (SerpApi's blog has a "build a Slack bot" tutorial where the *user*
owns the webhook). Treat as unverified; do not design against it.

**The documented pattern is `async=true` + poll the Search Archive.** Because archive reads are
free (§4), polling costs nothing but wall-clock and HTTP requests — measured 2 polls / ~4 s for a
Google search. That is effectively as good as a webhook for AdWatch's batch sweeps.

---

## 9. Locations API

Docs: <https://serpapi.com/locations-api>
**Endpoint:** `GET https://serpapi.com/locations.json`
**Params:** `q` (optional, substring filter), `limit` (optional, **max 10**).

**Cost: free — MEASURED.** 10 calls in 0.48 s → credit delta **0**.
**Also measured: `api_key` is not required** — `locations.json` returned HTTP 200 with no key at all.

### Measured response (array of objects), `?q=Austin&limit=3`

```json
{
  "id": "585069b8ee19ad271e9ba949",
  "google_id": 1026201,
  "google_parent_id": 21176,
  "name": "Austin",
  "canonical_name": "Austin,Texas,United States",
  "country_code": "US",
  "target_type": "City",
  "reach": 6440000,
  "gps": [-97.7430608, 30.267153],
  "keys": ["austin", "texas", "united", "states"]
}
```

(`keys` is present in the live response but absent from the documented field list.)

### How it feeds the search engines

- Pass `canonical_name` (e.g. `"Austin,Texas,United States"`) as the search API's **`location`**
  parameter. Confirmed live: a search with `location=Austin,Texas,United States` echoed
  `"location_requested": "Austin, Texas, United States"` and
  `"location_used": "Austin,Texas,United States"` in `search_parameters`.
- An unsupported string is rejected **before** any scrape — HTTP 400,
  `{"error": "Unsupported \`…\` location - location parameter."}`, **unbilled** (§7, e5).
- **`uule`** is the alternative: Google's encoded location. Docs describe it as the parameter
  defining the encoded location; supplying `uule` bypasses `location`. Note the `google_url` in
  responses shows Google receiving `uule=w+CAIQICIaQXVzdGluLFRleGFzLFVuaXRlZCBTdGF0ZXM` —
  SerpApi encodes `location` → `uule` for you. `INFERRED`: pass `location` and let SerpApi encode;
  only use `uule` if you need a location not in the Locations API.
- `lat`/`lon`/`radius` exist for engines that support coordinate targeting (e.g. Maps/Local).

**For AdWatch:** validate every customer-entered location against `locations.json` **before**
scheduling a run. It's free, keyless, and converts a would-be 400 mid-run into a setup-time
validation. Cache `canonical_name` per watch.

---

## 10. Plans and pricing

Source: <https://serpapi.com/pricing> (full table in §6).

- **Free tier: $0, 250 searches/month, 50/hour throughput.** Includes U.S. Legal Shield. No
  `plan_renewal_date`. Free accounts can also hold `extra_credits`.
- Paid self-serve: $25 → $2,750 (Starter → Infrastructure). Cloud plans $3,750 → $106,050.
- **No per-engine restrictions by tier.** The pricing page lists one flat searches-per-month
  allowance and the same ~110 engine APIs for every tier; nothing is gated by engine.
  Tier-gated *features* are: **U.S. Legal Shield** (all listed tiers, up to $2M coverage),
  **ZeroTrace Mode** (Cloud/Enterprise only — also exposed as the `zero_trace` param, "Enterprise
  only"), **Priority support** (Cloud/Enterprise), and **Ludicrous Speed** ("can be switched on or
  off for **all paid plans**" — so *not* on Free; 2.2× faster average, 4.2× at p99, and note
  §5: `async` should not be used with it).
- SerpApi is SOC 2 Type II, SOC 3, and ISO 27001 certified; uptime SLAs "up to 99.97%".

### Billing mechanics (pricing FAQ, verbatim highlights)

- *"Only successful searches are counted toward your monthly searches. Cached, errored, and failed
  searches are not."*
- **Overage:** there is no automatic overage charge. *"You can set your plan to **Automatic Early
  Renewal**. It will trigger an early renewal once you've used all your searches."* Otherwise you
  renew manually, or requests fail with **429 `"Your account has run out of searches."`**
  → **AdWatch's health card should warn well before zero**, because the failure mode is a hard
  stop, not a soft overage.
- **Downgrade:** *"Any remaining searches from your previous plan will be added to your 'Extra
  Credits' balance."* — explains why `extra_credits` can be large on a nominally Free account.
- **Upgrade:** pay the difference, renewal date unchanged.
- **Refunds:** *"full refund within 7 days of the date you subscribed to a plan unless you've used
  more than 20% of your searches."*

---

## 11. Recommended changes to AdWatch

**Accounting corrections (fix over-reporting):**
1. Bill a search only when `http==200 && search_metadata.status=="Success" && search_metadata.id`
   is present. Stop charging the ledger for 4xx and for `status: "Error"` 503s.
2. Keep charging for empty-result 200s — those are genuinely billed.
3. When a response arrives in <~0.5 s with a `search_metadata.id` AdWatch has already seen, it is
   a **cache hit → record cost 0**. (The id is the reliable signal, not the latency.)
4. Alarm on a `{}` response — billed, no data, no error key.

**Health card:**
5. Display **`total_searches_left`**, not `plan_searches_left` (extra credits drain first and
   `this_month_usage` can stay pinned at 0).
6. Null-guard `plan_renewal_date`.
7. Read `account_rate_limit_per_hour` rather than inferring throughput from `plan_name`.
8. Present remaining quota as an approximate gauge — the endpoint is eventually consistent and
   **non-monotonic** (observed swings of ±13 with zero searches issued). Never difference it to
   compute cost.

**Cost levers, in order of value:**
9. **Persist `search_metadata.id` on every run.** 31 days of free re-fetch for the diff engine,
   parser changes, and backfills. Biggest single lever.
10. **`async=true` + free archive polling** for scheduled sweeps — same cost, far better
    throughput and no long-held connections.
11. **Validate locations against the free, keyless `locations.json`** at setup time.
12. **`json_restrictor` for bandwidth only — never claim it saves quota.** Always retain
    `search_metadata.{id,status}`, keep it consistent per query signature (it busts the cache and
    will double-bill if mixed), fold it into the local cache key, and validate the syntax.
    `output=md` is a −85% payload win that does *not* bust the cache.
13. Use `no_cache=true` deliberately, not by default — the 1 h cache is free money on retries,
    manual refreshes, and overlapping multi-tenant watches.

---

## Appendix: measurement method and honesty notes

- The test account is **shared with concurrent consumers** — ~1 credit/second was being spent by
  other processes throughout. Single before/after deltas are therefore uninformative.
- The counter is additionally **non-monotonic** (observed +5, −13, +8, −10 with zero searches),
  so it is eventually consistent, not a real-time ledger.
- Two noise-robust instruments were used instead:
  1. **`search_metadata.id` identity** — a billed search creates a new record; a free operation
     replays an existing one. Deterministic and immune to ambient noise.
  2. **Tight bursts** — 12 operations compressed into <0.5 s, bracketed by equal-length idle
     controls. A billed burst would move the counter by ≥12; ambient noise over 0.5 s is ≈0–1.
- Not measured, documented only: 429 throttle behaviour (the key's ceiling is 200,000/hr),
  `status: "Error"` 503 billing, 410 archive expiry, and cross-account cache sharing.
- Doc silence explicitly flagged rather than resolved: **Search Archive cost** (§4) and
  **per-plan concurrency limits** (§6).

### Doc URLs cited
- <https://serpapi.com/account-api>
- <https://serpapi.com/search-api>
- <https://serpapi.com/search-archive-api>
- <https://serpapi.com/json-restrictor>
- <https://serpapi.com/locations-api>
- <https://serpapi.com/api-status-and-error-codes>
- <https://serpapi.com/pricing>
- <https://serpapi.com/ludicrous-speed>
