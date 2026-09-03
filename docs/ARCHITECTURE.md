# AdWatch — Architecture

## Components

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CONTROL PLANE  (Xano — time-boxed; Postgres fallback)                    │
│  auth · workspaces · users · watchlist/competitor/keyword CRUD · alert    │
│  preferences · webhook dispatch · static hosting for the web app          │
└──────────────┬───────────────────────────────────────────────────────────┘
               │ JWT (workspace_id claim)
┌──────────────▼───────────────────────────────────────────────────────────┐
│  WEB  (Next.js 15, app router)                                            │
│  /               watchlists                                               │
│  /w/[id]         overview: insight feed · change timeline · competitors   │
│                  creative grid · keyword share-of-voice · trend sparkline │
└──────────────┬───────────────────────────────────────────────────────────┘
               │ REST  /api/v1/*   (docs/API_CONTRACT.md)
┌──────────────▼───────────────────────────────────────────────────────────┐
│  DATA PLANE API  (FastAPI)                                                │
│                                                                           │
│   routers/      watchlists · collect · analyze · creatives · serp ·       │
│                 trends · changes · insights · demo                        │
│   collectors/   serpapi_client  → ads_transparency / google_search /      │
│                                   google_trends  (+ disk cache)           │
│   engine/       normalize · diff · analyst (Claude)                       │
│   alerts/       webhook (Slack/Discord-compatible)                        │
│   seed/         synthetic + live seeding                                  │
└──────────────┬───────────────────────────────────────────────────────────┘
               │ SQLAlchemy
┌──────────────▼───────────────────────────────────────────────────────────┐
│  POSTGRES 16                                                              │
└──────────────────────────────────────────────────────────────────────────┘
```

Why the split: the *data plane* is pure compute over public web data and belongs in a portable container. The *control plane* is generic SaaS plumbing (auth, tenancy, CRUD, notifications) — exactly what Xano is good at and what we don't want to hand-build in 24 hours. If Xano slips, the same tables live in Postgres and the API serves them; only `apps/web/lib/auth.ts` changes.

## Collection loop

```
POST /watchlists/{id}/collect
  for each competitor:  ads_transparency(text=domain)      → snapshot(kind=ads_transparency)
                         normalize → upsert creatives (first_seen/last_seen/active)
  for each keyword:      google(q=term, gl, hl)             → snapshot(kind=search_ads)
                         normalize → insert serp_ads (position, block, advertiser_domain)
                         google_trends(TIMESERIES)          → snapshot(kind=trends)
                         google_trends(RELATED_QUERIES)     → snapshot(kind=related_queries)
                         normalize → trend_points, related_queries
  diff(previous_run, this_run)                              → changes[]
  return {run_id, snapshots, changes}

POST /watchlists/{id}/analyze
  changes where insight_id IS NULL, grouped by competitor/keyword
  → Claude (structured JSON out) → insights[] → link changes → dispatch alerts
```

A **run** is one `collect` invocation; every snapshot carries `run_id` so "previous run" is unambiguous.

## Change taxonomy (diff engine output)

| kind | subject | trigger | default severity |
|---|---|---|---|
| `creative_launched` | competitor | creative_id present now, absent in previous run | medium |
| `creative_dropped` | competitor | creative_id absent now, present before | low |
| `creative_surge` | competitor | active creative count up ≥ 50% and ≥ 3 | high |
| `new_serp_advertiser` | keyword | advertiser domain in ads block now, not before | high |
| `serp_advertiser_left` | keyword | advertiser domain gone from ads block | medium |
| `serp_position_shift` | keyword | tracked competitor moved ≥ 2 positions or changed block (top↔bottom) | medium |
| `trend_spike` | keyword | latest value ≥ 1.5× trailing-4 mean and ≥ 20 | high |
| `trend_decline` | keyword | latest value ≤ 0.6× trailing-4 mean | low |
| `rising_query` | keyword | related query marked Breakout or ≥ +300%, confirmed in ≥ 2 of 3 draws and inside the watchlist's market | medium |
| `ad_copy_changed` | keyword | an advertiser present in both runs rewrote its title or description | medium |
| `ad_sitelinks_changed` | keyword | an advertiser's sitelink set changed (compared as a set — order varies between identical calls) | low |
| `product_price_changed` | keyword | a listing's price moved ≥ 2% for the same (merchant, title) | high on a cut ≥ 10%, else medium |
| `product_promo_appeared` | keyword | a listing gained a promotion it did not have | medium |
| `brand_conquest` | competitor | an advertiser other than the brand owner appeared on that brand's term | high |
| `brand_conquest_ended` | competitor | a conqueror left the brand term | low |
| `brand_undefended` | competitor | the owner left its own brand term while others still bid on it | high |
| `brand_defended` | competitor | the owner returned to its own brand term | low |

Baseline rule: the first run for any subject produces **no changes** (there's nothing to diff). The seed script creates two runs so the UI is never empty.

Absence rule: an empty response is not evidence of absence. An Ads Transparency call
returning nothing leaves existing creatives active rather than retiring them — a domain
missing from the index, a transient error and an exhausted quota are indistinguishable
at that point, and retiring on it wiped a competitor's whole history in one pass.
Product listings follow the same principle from the other side: their *set* churns
between identical draws, so only price and promotion moves are reported, never a
listing appearing or vanishing.

Sampling rule: Google samples the rising-query bucket. Four uncached draws of one term
gave pairwise Jaccard 0.10-0.25, with 13 of 23 queries appearing in exactly one draw,
so a single draw is not evidence. Each run takes three and keeps what two agree on.

## Data model (Postgres)

```
workspaces      id, name, xano_workspace_id?, created_at
watchlists      id, workspace_id, name, vertical, geo (default "US"), created_at
competitors     id, watchlist_id, name, domain, advertiser_id?, created_at
keywords        id, watchlist_id, term, kind ('keyword'|'brand'), owner_competitor_id?,
                created_at
runs            id, watchlist_id, started_at, finished_at, status, searches_used
snapshots       id, run_id, watchlist_id, kind, subject_type, subject_id, fetched_at,
                serpapi_search_id?, raw JSONB
creatives       id, competitor_id, creative_id (unique w/ competitor), format, platform?,
                target_domain?, image_url?, details_url?, first_shown?, last_shown?,
                total_days_shown?, first_seen_run_id, last_seen_run_id, active
serp_ads        id, keyword_id, run_id, position, block ('top'|'bottom'), advertiser_domain,
                title, description?, displayed_link?, link?, source?, sitelinks JSON?
product_listings id, keyword_id, run_id, merchant, title, price, original_price?, promo?,
                rating?, reviews?
trend_points    id, keyword_id, run_id, date, value
related_queries id, keyword_id, run_id, query, bucket ('rising'|'top'), value_text, value_num?
changes         id, watchlist_id, run_id, kind, severity, subject_type, subject_id,
                payload JSONB, detected_at, insight_id?
insights        id, watchlist_id, run_id, model, summary, why_it_matters,
                recommended_actions JSONB, confidence, created_at
alerts          id, insight_id, channel, target, status, sent_at?, error?
```

`keywords.kind` distinguishes a market term the customer chose from a brand term the
collector provisions per competitor. Brand terms take the paid-block call only — demand
for a company's name is not the signal — and they never count against the plan's keyword
limit, since charging for a row the system created would make adding a competitor
silently cost a keyword. Every consumer that iterates a watchlist's keywords must filter
on `kind`; forgetting to put brand terms in share-of-voice tables and keyword counts.

`creatives.total_days_shown` is days actually served, not the span between first and
last shown — measured 4 to 947 days on one advertiser. It is the closest thing to a
performance signal public ad-library data offers, and drives the report's proven-creatives
ranking.

`serp_ads.sitelinks` stores titles only. The hrefs are `google.com/goto` redirects that
differ between identical calls, so storing them would churn the diff for nothing. The
same applies to `link`: resolving an advertiser from it yields `google.com` every time,
so `advertiser_domain` is derived from `displayed_link`.

`product_listings` come from the `immersive_products` block that rides free on the paid
search response. They carry no click-tracking link, so they evidence merchandising
presence and price rather than paid placement — which is why they are a separate table
from `serp_ads`.

Deleting any of this goes through `app/purge.py`, which owns the one foreign-key-ordered
delete chain shared by the delete endpoints and the demo reset. A test asserts the chain
covers every table with a foreign key into the watchlist graph, because the chain existed
in two places once and drifted.

`raw` on snapshots is the full SerpApi response — cheap, and it's our audit trail + replay source if normalization needs fixing later (re-normalize from raw, no quota spent).

## AI analyst contract

Input: watchlist context (vertical, our competitors, our keywords) + a list of changes (structured, ≤ 30). Output — strict JSON:

```json
{
  "summary": "one paragraph, plain English, no brand hype",
  "why_it_matters": "what this signals about competitor strategy or demand",
  "recommended_actions": [
    {"action": "…", "rationale": "…", "effort": "low|medium|high", "urgency": "now|this_week|monitor"}
  ],
  "confidence": 0.0
}
```

The prompt tells the model it is a paid-search analyst, must only reason from the supplied changes, must not invent metrics, and should prefer 2–3 concrete actions over generic advice.

**No `temperature`.** anthropic 1.x removed it from `Messages.create()`, and passing it
raised `TypeError` on every call — which the broad `except` swallowed into the
deterministic fallback. Insights appeared, cards rendered, runs succeeded, and Claude was
never once reached in production. The only trace was `status="fallback"` in the ledger
and a "0 tokens" figure that read like a metering bug. `tests/test_analyst_call.py`
checks the kwargs against the *installed* SDK signature, because a stub accepting
`**kwargs` would have passed the whole time.

`max_tokens` is 2000. At 900, three of seven briefs were cut off mid-JSON and rendered as
a wall of unterminated text at 0% confidence; a truncated brief (`stop_reason ==
"max_tokens"`) is now treated as a failed one and degrades to the honest fallback.

Parse with a tolerant JSON extractor; on failure store the raw text as `summary` and
`confidence: 0` — prose is still readable, only JSON debris is thrown away.

The analyst's model calls all happen before the result loop, so `run_analyze` commits
before invoking them. Holding the read transaction open across the batch left the
connection idle-in-transaction long enough for Postgres to close it, and the first write
afterwards failed on a request whose collect had already succeeded.

## Non-goals for v1

Own-account Google Ads API, bid changes, non-Google channels, multi-user roles, billing, historical backfill beyond what SerpApi returns, mobile.
