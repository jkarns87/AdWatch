# Cost model — what we scrape, what it costs, what we charge

Source of truth for the Usage page (`services/api/app/plans.py`) and the "Feasibility" answer on Devpost.
Prices below are SerpApi list prices on 2026-09-02; the blended rate used in the product is **$0.010/search**.

## 1. Unit of cost: one SerpApi search

Every call to SerpApi is one search against a monthly quota, regardless of engine. Cached, errored and failed
searches are free. Plans (per month): Free 250 · Starter $25 / 1,000 ($0.025) · Developer $75 / 5,000 ($0.015) ·
Production $150 / 15,000 ($0.010) · Big Data $275 / 30,000 ($0.0092) · Enterprise custom. Throughput caps scale with
the plan (50/hr on Free, 3,000/hr on Production).

The AI analyst adds roughly $0.03 per analyze run (structured diff in, strict JSON out — a few thousand tokens);
it is a rounding error next to the search spend and is included in the margins below.

## 2. What each SerpApi engine gives us (and what it can't)

| Engine | What we pull | Fields we keep | Cadence that matters | Not available |
|---|---|---|---|---|
| **Google Ads Transparency Center** (`google_ads_transparency_center`) | Every creative an advertiser is currently running, by `advertiser_id` or free-text/domain; filters: `platform` (SEARCH, YOUTUBE, MAPS, SHOPPING, PLAY), `creative_format` (text/image/video), `region`, `start_date`/`end_date`; `num` up to 100 + `next_page_token` | `ad_creative_id`, `format`, `image`/`link`, `width`×`height`, `target_domain`, `first_shown`, `last_shown`, `details_link`; with `get_advertiser=true`: legal name + country | **Daily.** Creatives live for days–weeks; `first_shown`/`last_shown` give lifecycle without polling faster | Spend, impressions, CTR, targeting. (Spend/impression *ranges* exist for political ads only.) |
| **Google Search** (`google`) — `ads` block | The live paid block for a keyword at a given `location`/`gl`/`hl`/`device` | `position`, `block_position` (top/bottom), `title`, `description`, `displayed_link`, `link`, `tracking_link`, `source`, `sitelinks`, `extensions`; plus `shopping_results` (PLA: price, merchant) and local/hotel/vehicle ad variants | **Hourly-ish.** The auction changes by daypart and device; sampling 2–4×/day per keyword reveals ad schedules and share of voice | Bids, quality score, auction insights, per-advertiser impression share |
| **Google Trends** (`google_trends`) | `TIMESERIES` (interest over time, up to **5 queries per call**), `RELATED_QUERIES` (rising/top, 1 query per call), `GEO_MAP_0` (interest by region), `RELATED_TOPICS` | `timeline_data[date, value]`, `related_queries.rising[query, value, extracted_value]`, `interest_by_region` | **Daily** for the timeseries (Trends resolution is daily anyway); **weekly** for related queries (computed over the window, moves slowly) | Absolute search volume (values are indexed 0–100) |

Derived metrics we compute from the above (no extra calls): creative lifecycle (launched / dropped / surge),
share of voice per keyword (appearances × position), position shifts, new/leaving advertisers, demand spikes
and declines (latest vs trailing mean), breakout queries, dayparting inference (SERP samples by hour).

## 3. Searches per watchlist

For a watchlist with **C** competitors and **K** keywords, one full run costs

```
C  (Ads Transparency Center, one per competitor)
+ K  (Google Search paid block, one per keyword)
+ ⌈K/5⌉  (Trends TIMESERIES, batched 5 keywords per call)      ← today's code does K, not ⌈K/5⌉
+ K  (Trends RELATED_QUERIES, one per keyword)
```

**Today's scheduler** (everything, every 6 h, no batching) on a 5-competitor / 10-keyword watchlist:
4,200 searches/month ≈ **$42/watchlist/month**. That doesn't support any sane price point — it is the
naive number the Usage page shows as "current cadence."

**Per-source cadence** (what a plan actually sells): creatives 1×/day, SERP 2×/day, Trends timeseries 1×/day
batched, related queries 1×/week → **853 searches/month ≈ $8.53/watchlist/month** for the same alerts,
because creatives change daily and demand moves weekly; only the paid SERP block moves by the hour.

## 4. Plans, COGS and margin

| Plan | Price | Limits | Cadence | Searches / mo | Search COGS | + AI | Gross margin |
|---|---|---|---|---|---|---|---|
| **Free** | $0 | 1 watchlist · 2 competitors · 3 keywords · 250 searches | daily everything | ~190 | $0 (inside SerpApi Free) | $1.80 | lead-gen |
| **Team** | $79 | 3 watchlists · 5 competitors · 10 keywords each · 3,000 searches | creatives 1×/day · SERP 2×/day · demand 1×/day · related 1×/wk | ~2,560 | $25.60 | $5.40 | **~61 %** |
| **Agency** | $299 | 10 watchlists · 10 competitors · 15 keywords each · 15,000 searches | same as Team, priority collection | ~13,540 | $135.40 | $18.00 | **~49 %** |

Margins improve at scale: the Big Data tier ($0.0092) lifts Agency to ~52 %, and SerpApi's Enterprise pricing
goes lower. Two further levers are already in the design: the SerpApi response cache (a second workspace watching
the same competitor or keyword within the cache window costs nothing — cross-tenant dedupe is the real moat at
scale) and skipping Trends on keywords whose timeseries hasn't moved in 14 days.

## 5. Budget guard — how cost is enforced in the product

1. **Every run records `searches_used`** (`runs` table, from the SerpApi client counter). `GET /usage` sums it per
   workspace for the calendar month, projects month-end at both cadences, and prices it.
2. **The plan lives in the control plane** (`workspace.plan` in Xano) and is returned with token introspection
   (`/auth/me` → `workspace.plan`), so the data plane knows the budget for every request without a second lookup.
3. **Soft limits now:** the Usage page flags watchlists over plan size and shows budget used; owners can switch
   plans in one click (`POST /workspace/plan`).
4. **Hard limits next:** the Xano scheduler reads `GET /usage` before each collection and skips workspaces at
   100 % of budget; the data plane rejects `collect` when over budget with a 402 that the UI turns into an upgrade
   nudge. No surprise bills, ever — the customer's ceiling is the plan, not an invoice.

## 6. Where the searches go — worked example (Team plan, 3 watchlists at max size)

| Source | Calls / day | Calls / month | Share |
|---|---|---|---|
| Ads Transparency Center | 15 | 450 | 18 % |
| Google Search paid block | 60 | 1,800 | 70 % |
| Trends timeseries (batched) | 6 | 180 | 7 % |
| Trends related queries | ~4 | 129 | 5 % |
| **Total** | **~85** | **~2,560** | |

The SERP block is 70 % of spend — which is also where the hourly signal is. Selling "SERP samples per day" as the
knob between Team and Agency tiers is honest and maps 1:1 to cost.

## 7. What changed the per-run cost (2026-09-03)

Two corrections made runs more expensive, both deliberately:

| Change | Cost | Why it is worth paying |
|---|---|---|
| Related queries take **3 draws**, not 1 | +2 searches per market keyword per run | One draw is not evidence. Four uncached draws of one term agreed on 10-25 % of results; 13 of 23 queries appeared in exactly one draw. Suppressed 20 of 38 rising queries as noise on live data. |
| Every competitor gets a **brand term** | +1 search per competitor per run | 7 of 7 measured brand SERPs carrying ads had a competitor bidding on the brand, and in 4 of 7 the owner was absent from its own name. The highest-value alert public data supports. |

**Per run = competitors + 5 × market keywords + brand terms.** The demo watchlist
(3 competitors, 5 keywords) went from 18 searches to **31**.

Brand terms take the paid-block call only — demand for a company's name is not the
signal, and collecting trends for it would cost three more searches each.

Two things that cost nothing and were being discarded: **product listings**
(`immersive_products`) ride free on the paid-search response, and **ad copy and sitelinks**
were already stored and simply never compared.

The old 18 was cheaper because a third of what it collected was noise and the two
headline collectors returned nothing at all. A cheap number that is wrong is not a saving.

### Cache accounting, unresolved

Measured: SerpApi serves cached responses (identical params within ~1h) **free**, and a
Search Archive re-fetch by `search_id` is also free with 31-day retention. The ledger
counts every call as billed, so it **over-reports** spend. The correction is not applied
yet: the supporting measurement for which error responses are billed rests on differencing
SerpApi's quota counter, and the same session observed that counter swinging ±13 with no
searches issued. Verify against SerpApi's own dashboard before changing published numbers.
