# Changelog

## 2026-09-03 — post-submission

Started as a research pass over the SerpApi surface (~1,000 live searches, seven parallel
streams — see [`research/README.md`](research/README.md)). It found that two of the three
collectors had never worked in production. Everything below followed from that.

### Silent collector failures

All of these shipped, all produced no error, and all left a run reporting success.

| Bug | Effect | Fix |
|---|---|---|
| ATC normalizer matched `id` / `creative_id` | the engine sends `ad_creative_id`; a 40-creative response normalized to `[]` | 0 → 248 creatives on the demo watchlist |
| Keyword collector used `engine=google` | that engine omits the paid block: 0 ads on 6 of 6 commercial queries | `engine=google_ads`, 2–6 per query, same cost |
| `domain_of` returned the whole breadcrumb | `urlparse` has no `/` to end the netloc, so one advertiser read as two between runs | matched pair of false new/disappeared events gone |
| `fresh=True` never sent `no_cache` | SerpApi replayed one stored record for an hour | repeated sampling is now genuinely independent |
| One draw of rising queries treated as evidence | 4 uncached draws agreed on 10–25%; 13 of 23 queries appeared once | 3 draws, majority wins — suppressed 20 of 38 as noise |
| `app/market.py` was never called | the drift guard existed and was never hung; a coffee watchlist reported "concerts" up 400% | filtered at the diff |
| Empty ATC response retired every creative | a missing domain, an API error and an exhausted quota are indistinguishable | absence is no longer evidence of absence |
| Duplicate creative in one response | two inserts of one key failed a 92-row batch, losing the run | deduped within the batch |
| `total_days_shown` stored, never read | the strongest performance proxy in ad-library data was invisible | drives the report's proven-creatives ranking |

Two database faults surfaced under the longer runs: the request held one pooled connection
across minutes of network I/O and Postgres closed it, and the DB machine itself was a
256 MB instance hitting its resource limit. The first was fixed by releasing the
transaction before the model calls; the second by scaling the machine.

### New signals — all riding free on calls already made

`ad_copy_changed`, `ad_sitelinks_changed`, `product_price_changed`,
`product_promo_appeared`. Ad copy had been stored since the first run and never compared.
Product listings come from `immersive_products`, which appears on the same paid-search
response, so competitor pricing costs nothing extra.

Product events are price-and-promotion only, deliberately: prices measured stable with
zero spurious movement, while the listing *set* churns between identical draws.

### Brand conquesting

`brand_conquest`, `brand_conquest_ended`, `brand_undefended`, `brand_defended`, plus
`GET /watchlists/{id}/brands` for standing state. Measured: 7 of 8 brand SERPs carried
ads, every one of those had a competitor bidding on the brand, and in 4 of 7 the owner was
absent from its own name.

Brand terms ride the keywords table with a `kind` flag and cost one search each — no
trends, no related-query draws. They never count against the plan's keyword limit.

### Product

- Plan limits **enforced** on creation (402), where before they were only reported.
- Platform-admin role for cross-workspace plan changes, with an append-only `plan_change`
  audit table. No endpoint grants the flag, on purpose.
- Delete for watchlists and competitors, sharing one foreign-key-ordered chain with the
  demo reset — a completeness test found `company_assets` missing from both.
- Weekly report gained proven creatives and brand defence, capped per competitor so one
  prolific advertiser cannot own the table.
- Creative grid sorts ascending/descending and shows a six-month window.
- Video exclusion at normalization: `creative_format` filters server-side but takes one
  value, so keeping text and image would double the ATC cost.
- Demo seeded live from three real advertisers instead of synthetic `.example` domains.

### Cost

Per run = competitors + 5 × market keywords + brand terms. The demo watchlist went from 18
searches to **31**. The old number was cheaper because a third of what it collected was
noise and two collectors returned nothing. See [`COST_MODEL.md`](COST_MODEL.md) § 7,
including the unresolved cache-accounting question.

### Method notes worth keeping

**Agents were reliable about the external API and unreliable about this repo.** Several
confidently reported defects in code they had not read — a `link`-diff storm, a wrong
quota field, "no export of any kind" — and none were real. Every one of their SerpApi
findings held up under verification.

**Cache discipline decides whether a measurement means anything.** The first attempt at
measuring related-query stability returned a Jaccard of 1.00 and looked like proof. It was
measuring SerpApi's server-side cache through a flag that only cleared our own disk cache.
The real answer was 0.10–0.25.

**Green tests are not evidence the output is right.** The proven-creatives table passed
every test and returned ten rows from a single competitor, because one advertiser's 92
creatives monopolised a global top-10. Only reading the rendered report showed it — the
same way the truncated insight cards were found.

Tests: 246 → **359** Python, 47 → **58** web.
