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
| `rising_query` | keyword | related query marked Breakout or ≥ +300% | medium |

Baseline rule: the first run for any subject produces **no changes** (there's nothing to diff). The seed script creates two runs so the UI is never empty.

## Data model (Postgres)

```
workspaces      id, name, xano_workspace_id?, created_at
watchlists      id, workspace_id, name, vertical, geo (default "US"), created_at
competitors     id, watchlist_id, name, domain, advertiser_id?, created_at
keywords        id, watchlist_id, term, created_at
runs            id, watchlist_id, started_at, finished_at, status, searches_used
snapshots       id, run_id, watchlist_id, kind, subject_type, subject_id, fetched_at,
                serpapi_search_id?, raw JSONB
creatives       id, competitor_id, creative_id (unique w/ competitor), format, platform?,
                target_domain?, image_url?, details_url?, first_shown?, last_shown?,
                first_seen_run_id, last_seen_run_id, active
serp_ads        id, keyword_id, run_id, position, block ('top'|'bottom'), advertiser_domain,
                title, description?, displayed_link?, link?
trend_points    id, keyword_id, run_id, date, value
related_queries id, keyword_id, run_id, query, bucket ('rising'|'top'), value_text, value_num?
changes         id, watchlist_id, run_id, kind, severity, subject_type, subject_id,
                payload JSONB, detected_at, insight_id?
insights        id, watchlist_id, run_id, model, summary, why_it_matters,
                recommended_actions JSONB, confidence, created_at
alerts          id, insight_id, channel, target, status, sent_at?, error?
```

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

The prompt tells the model it is a paid-search analyst, must only reason from the supplied changes, must not invent metrics, and should prefer 2–3 concrete actions over generic advice. Temperature low. Parse with a tolerant JSON extractor; on failure store the raw text as `summary` and `confidence: 0`.

## Non-goals for v1

Own-account Google Ads API, bid changes, non-Google channels, multi-user roles, billing, historical backfill beyond what SerpApi returns, mobile.
