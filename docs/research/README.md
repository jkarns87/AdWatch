# SerpApi surface research — 2026-09-03

Seven parallel research streams against the **live** SerpApi API, roughly 1,000 real
searches. Every claim below was measured against a saved response, not read from a doc
page — several doc pages turned out to be stale, and two agent findings about *our own*
code were wrong because they were inferred rather than read.

Full reports in [`reports/`](reports/). They name real advertisers, which is fine for
internal notes but **must not reach public submission copy** — see the naming rule at
the top of `docs/DEVPOST.md`.

---

## What this changed in the product

Four silent collector bugs, all shipped, all fixed in `5a68e61`:

| Bug | Effect | After |
|---|---|---|
| ATC normalizer matched `id` / `creative_id`; the engine sends `ad_creative_id` | every creative dropped | 0 → 100 |
| Keyword collector used `engine=google`, which omits the paid block | 0 ads on 6 of 6 commercial queries | 2–6 per query |
| `domain_of` returned the whole breadcrumb (`urlparse` has no `/` to end the netloc) | one advertiser read as two between runs | bare domain |
| `fresh=True` bypassed only our disk cache, never sent `no_cache` | repeat samples replayed one stored record | distinct `search_id`s |

Then five signals that were already in responses we pay for and were being discarded
(`97f1511` onward): ad `sitelinks`, ad `source`, `total_days_shown`, `immersive_products`,
and ad copy — which was stored from day one and never compared.

---

## The findings that decided design

**`engine=google_ads` is the right engine, and it is not optional.**
Identical query, location and minute: `google` returned 0 ads on all six of *crm
software, car insurance quotes, espresso machine, meal kit delivery, running shoes,
project management software*; `google_ads` returned 2–6 on every one. Same 1-search
cost, superset response — organic results, related searches and AI overview all still
come back. It also **requires** `location`; without one it errors and returns nothing,
which is why the client now falls back to a country derived from `gl`.

**Rising related-queries are a sample, not a census.**
Four genuinely uncached draws of one term: pairwise Jaccard 0.10–0.25, 13 of 23 queries
appearing in exactly one draw, and the breakout flag stable in 0 of 2 cases. We had been
diffing one draw against one draw and reporting the churn as demand. Now three draws,
majority wins — which discarded 20 of 38 rising queries on live data.

**Trend values rescale, but our spike detector was never exposed to it.**
Values are renormalised per query and per group, so a value from one run is not
comparable to the same query's value in another. `diff_trends` compares the latest point
to its own trailing window *inside one response*, so it is scale-invariant by
construction. Worth knowing, not worth changing.

**Batching 5 trend terms into 1 search was rejected.**
It genuinely costs 1 search, not 5 — a real 5× saving. But every term in a group is
rescaled against the largest, so a low-volume keyword batched with a dominant one
collapses toward zero and `SPIKE_MIN_VALUE = 20` stops firing for it entirely. Cheaper
and broken is not cheaper.

**Product listings ride free on the call we already make.**
`immersive_products` appears on `google_ads` responses for commercial queries — 24–60
items, with merchant, title, price, rating and reviews at 100% coverage. One live search
returned 2 ads *and* 60 listings. Events are deliberately price-and-promotion only:
prices were measured stable with zero spurious movement, while the listing *set* churns
between identical draws, so presence and absence would bury the real signal.

**Cache hits and Search Archive re-fetches are free.**
Twelve identical requests in 0.48s returned one `search_metadata.id` and cost one
search; twelve archive re-fetches cost zero. Our ledger counts every call as billed, so
it over-reports. Not yet changed — the error-billing half of that finding rests on
counter differencing, and the same report measured the counter swinging ±13 with no
searches issued.

**`json_restrictor` is a trap.** It cuts payload 99.3% but saves no quota, strips
`search_metadata` (losing `search_id`), and *busts the cache* — the same query with a
restrictor got a new id and a fresh billed scrape. `output=md` gives −85% bytes and
stays cached.

---

## Hard negatives — do not build these

- **SerpApi exposes no search volume, CPC, or competition score.** Not on any engine.
  SerpApi says so itself. The closest proxies are the Trends 0–100 relative index,
  autocomplete rank order, and ad density as a competition signal. Do not surface a
  volume number sourced from SerpApi.
- **The Ads Transparency Center cannot discover advertisers by keyword.** `text` takes a
  registrable domain only; topic and brand-name searches returned nothing. It is
  enrichment, never discovery. Discovery happens on the SERP.
- **ATC creative detail does not return search-ad headline text** — 12 of 12 text
  creatives came back as a flattened image, including SerpApi's own documented example.
- **`google_product` is shut down**, and the documented `shopping_results`,
  `product_result` and `product_sites` blocks never appeared. Those doc pages are stale.
- **PAA trees are dead** — all 32 observed items returned as `ai_overview` stubs with no
  snippet or link. Harvest the four question strings free; don't page the tree.
- **No webhooks.** Async plus free archive polling is the documented pattern.

---

## Still on the table

Ranked by value per search. Nothing here is started.

1. **Brand-conquesting alerts.** 7 of 8 brand SERPs carried ads and **7 of 7 had a
   competitor bidding on the brand**; in 4 of 7 the brand owner was absent from its own
   name. 1 search per brand term per run. The highest-value alert not yet built.
2. **Share of presence.** Ads are non-deterministic — repeated identical calls returned
   wildly different advertiser sets, and one report treated that as noise to suppress.
   It is also the signal: an advertiser appearing in 18 of 24 daily polls is holding
   ~75% presence, the closest honest proxy for impression share obtainable without the
   customer's own account. Costs nothing beyond polling already planned.
3. **Advertiser identity resolution.** `domain_of(ad.link)` fails 100% of the time now —
   every destination is a `google.com/goto` redirect. `displayed_link` is the only
   reliable field, and ~25% of advertisers on a commercial SERP are affiliates rather
   than competitors. Needs a real resolution strategy before discovery ships.
4. **ATC enrichment of SERP-discovered advertisers.** 23 of 23 domains resolved to an
   `advertiser_id`; 70% unambiguous, and a dominance rule reached 96% correct
   attribution. One cacheable search per domain, not a per-run cost.
5. **Geo monitoring.** Advertiser sets across metros were *fully disjoint* — real
   signal, 1 search per keyword per metro.
6. **Local Services Ads** — 20 advertisers with stable ids for 1 search, and
   `local_results.places[].ad:true` flags paid local placement for free.
7. **`trending_now`** — 440+ rows for one search, carrying the only *absolute* (bucketed)
   volume figures anywhere in the API.

---

## Method notes

Two lessons worth keeping.

**Agents inferred bugs in code they had not read.** Two reports confidently described
defects in AdWatch — a `link`-diff false-positive storm, a wrong quota field on the
health card. Neither was real; we key creatives on `creative_id` sets, and
`providers.py` already reads `total_searches_left`. Their *SerpApi* findings held up
under verification. Findings about the external API were trustworthy; findings about our
repo were not.

**Cache discipline decides whether a measurement means anything.** The first attempt at
measuring related-query stability returned Jaccard 1.00 and looked like proof. It was
measuring SerpApi's one-hour server-side cache through a flag that only cleared our own
disk cache. The real answer was 0.10–0.25. Any repeated-sampling measurement against
this API is worthless without `no_cache=true` and a check that the `search_id`s differ.
