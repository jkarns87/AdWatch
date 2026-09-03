# SerpApi — Google Ads Transparency Center: Exhaustive Engine Research for AdWatch

**Date:** 2026-09-03
**Method:** Live documentation read (raw HTML pulled with `curl`, not training memory) **plus 72 live API requests** against a real key.
**Raw responses:** `scratchpad/raw/*.json` (see index at end). All saved responses have `search_parameters.api_key` removed and the key string replaced with `REDACTED`; a full-tree `grep` for the key returns nothing.

> **CONFIDENTIALITY NOTE — READ BEFORE REUSING THIS DOC.**
> Advertiser names, advertiser IDs, creative IDs, landing-page URLs and ad copy in this report were pulled from live Google Ads Transparency Center data for **internal research only**. Do not paste real advertiser names, their ad copy, their `obfuscatedCustomerId`/`adGroupId` values, or their landing-page URLs into public submission copy, marketing material, demos, or documentation. Use synthetic examples in anything user-facing.

---

## 0. Executive summary

There are **two** engines, not one:

| Engine | Purpose | Cost |
|---|---|---|
| `google_ads_transparency_center` | List creatives for an advertiser or a target domain | 1 search per page |
| `google_ads_transparency_center_ad_details` | One creative → variations, per-region footprint, real landing URL | 1 search per creative |

AdWatch uses only the first, and reads 10 of the ~14 available list fields. The five highest-value untapped items, in order:

1. **`link` is being diffed but is non-deterministic** — a live bug. 100% of link-bearing creatives changed `link` between two runs 10 minutes apart, because of two nonce query params. Fixing this is free and removes false-positive churn.
2. **`link` hides `adGroupId` + `obfuscatedCustomerId` + `versionId`** — campaign structure and creative-revision signals, already inside data AdWatch downloads and discards. Zero extra cost.
3. **`total_days_shown`** — present on 100% of creatives, never read. Zero extra cost.
4. **`platform` faceting** — genuinely partitions the creative set; reveals channel-mix shifts. 4 extra searches per advertiser per run.
5. **Detail call `regions[]`** — per-country `first_shown`/`last_shown` for one creative (up to 17 countries observed). 1 search per creative.

The two things that do **not** work the way you'd hope:
- **Keyword/topic advertiser discovery does not exist.** `text` accepts a bare registrable domain and nothing else. 9/9 non-domain queries returned zero results.
- **The detail call does not give you search-ad headline copy.** 12/12 text-format creatives across 5 advertisers returned a single flattened `image` and nothing else — including the exact creative SerpApi's own docs use as its text-ad example.

---

## 1. Complete parameter surface

### 1.1 `engine=google_ads_transparency_center` (list)

Source: <https://serpapi.com/google-ads-transparency-center-api> (raw HTML pulled 2026-09-03).

| Parameter | Req | Type | Allowed values | Default | Notes |
|---|---|---|---|---|---|
| `engine` | **Yes** | string | `google_ads_transparency_center` | — | |
| `api_key` | **Yes** | string | — | — | |
| `advertiser_id` | Conditional | string | `AR…` ID, or comma-separated list | — | Optional *only if* `text` is present. From the ATC advertiser URL. |
| `text` | Conditional | string | See §4 — **bare registrable domain only** | — | Alternative to `advertiser_id`. |
| `platform` | No | enum | `PLAY`, `MAPS`, `SEARCH`, `SHOPPING`, `YOUTUBE` | all platforms | |
| `political_ads` | No | bool | `true` / `false` | `false` | **Requires `region`.** When `true`, returns *only* political ads. |
| `get_advertiser` | No | bool | `true` / `false` | `false` | Adds the `advertiser` block. Single `advertiser_id` only. Docs: "an additional request is made". |
| `region` | No | integer | 239 codes, see §1.3 | anywhere | |
| `start_date` | No | string | `YYYYMMDD` | — | |
| `end_date` | No | string | `YYYYMMDD` | — | Docs: for a single day set `end_date = start_date + 1 day`. |
| `creative_format` | No | enum | `text`, `image`, `video` | all | |
| `num` | No | integer | **1–100** | `40` | |
| `next_page_token` | No | string | opaque | — | From `serpapi_pagination.next_page_token`. |
| `no_cache` | No | bool | | `false` | Cache TTL 1h. Cached searches are free. Mutually exclusive with `async`. |
| `async` | No | bool | | `false` | Retrieve via Searches Archive API. |
| `zero_trace` | No | bool | | `false` | Enterprise only. |
| `output` | No | enum | `json`, `html`, `md` | `json` | |
| `json_restrictor` | No | string | field selector | — | Payload size only — **does not reduce search cost**. |

**OBSERVED vs DOCUMENTED — parameter validation** (all verified live, all HTTP 400, all presumed unbilled per the pricing FAQ):

| Probe | Result |
|---|---|
| `num=200`, `num=500` | `` `num` parameter must be an integer between 1 and 100. `` → **max is exactly 100.** The docs never state the bound. (`raw/num-200.json`, `raw/num-500.json`) |
| `region=9999` | `` Unsupported `9999` region parameter. `` (`raw/err-badregion.json`) |
| `creative_format=carousel` | `` Unsupported `carousel` creative_format parameter. `` (`raw/err-badformat.json`) |
| `platform=TIKTOK` | `` Unsupported `TIKTOK` for platform. `` (`raw/err-badplatform.json`) |
| neither `advertiser_id` nor `text` | `` Missing query `advertiser_id` parameter. `` (`raw/err-noquery.json`) |
| `political_ads=true` without `region` | `` `political_ads` parameter can only be used with `region`. `` (`raw/pol-noregion.json`) |

### 1.2 `engine=google_ads_transparency_center_ad_details` (detail)

Source: <https://serpapi.com/google-ads-transparency-center-ad-details>.

| Parameter | Req | Type | Notes |
|---|---|---|---|
| `engine` | **Yes** | string | `google_ads_transparency_center_ad_details` |
| `api_key` | **Yes** | string | |
| `advertiser_id` | **Yes** | string | |
| `creative_id` | **Yes** | string | `CR…` |
| `region` | No | integer | Defaults to `anywhere` |
| `no_cache`, `async`, `zero_trace`, `output`, `json_restrictor` | No | — | Same semantics as the list engine |

There is **no** `num`, no pagination, no date range, no format filter on this engine.

**OBSERVED:** passing `region` adds an integer `search_information.region` field (undocumented) but did **not** change `regions[]` or `ad_creatives` in my A/B test (`raw/det-purple-text.json` vs `raw/det-purple-text-us.json`). An invalid `creative_id` returns `{"error": "Failed to retrieve data."}` with no `search_information` (`raw/det-brev-s1.json`).

### 1.3 Region codes

Source: <https://serpapi.com/google-ads-transparency-center-regions>, machine-readable at <https://serpapi.com/google-ads-transparency-center-regions.json> (saved as `raw/../regions.json`).

- **239 regions** (the rendered HTML page is easy to miscount; the JSON is authoritative — I counted it programmatically).
- Keys are **integers-as-strings**; values are country names. `{"2008":"Albania", …, "20277":"Canary Islands"}`.
- These are Google geo-target country criteria IDs. US = `2840`, UK = `2826`, Canada = `2124`, Germany = `2276`, Australia = `2036`.
- Omitting `region` searches "anywhere".

---

## 2. Complete response surface

### 2.1 List engine — observed field inventory

Verified across 627 creatives for a B2B SaaS advertiser plus a DTC mattress brand and a coffee-equipment retailer.

| Field | Type | Coverage (n=627) | AdWatch reads? |
|---|---|---|---|
| `advertiser_id` | string | 100% | yes |
| `advertiser` | string | 100% | yes (as advertiser_name) |
| `ad_creative_id` | string | 100% | yes (as creative_id) |
| `format` | `text`\|`image`\|`video` | 100% | yes |
| `first_shown` | int, Unix epoch | 100% | yes |
| `last_shown` | int, Unix epoch | 100% | yes |
| `details_link` | string URL | 100% | yes |
| `serpapi_details_link` | string URL | 100% | yes (as details_url) |
| **`total_days_shown`** | int | **100%** | **NO** |
| `image` | string URL | 70% | yes |
| **`width`** | int | **67%** | **NO** |
| **`height`** | int | **67%** | **NO** |
| `link` | string URL | 30% | yes — **and this is a bug, see §6.1** |
| **`target_domain`** | string | 0% on `advertiser_id` searches; 100% on `text` searches | **NO** |
| `minimum_views_count` / `maximum_views_count` | int | political only | **NO** |
| `minimum_budget_spent` / `maximum_budget_spent` | string `"400 USD"` | political only | **NO** |

Envelope: `search_metadata` (`id`, `status`, `json_endpoint`, **`markdown_endpoint`** — undocumented, `created_at`, `processed_at`, `google_ads_transparency_center_url`, `raw_html_file`, `prettify_html_file`, `total_time_taken`), `search_parameters` (echo), `search_information.total_results`, `advertiser` (only with `get_advertiser=true`: `id`, `name`, `legal_name`, `country_code`, `country`), `ad_creatives[]`, `serpapi_pagination` (`next_page_token`, `next`).

**DOCUMENTED vs OBSERVED:**
- `link` and `image` are documented as unconditional. **Observed: mutually near-exclusive and format-driven.** Video → `link` (175/177). Text → neither `link` nor `image` in 397/411 cases. So "which media field is populated" is itself a weak format signal.
- `total_results` is a **rounded estimate, not a count.** A 700-`total_results` advertiser enumerated to exactly **627** creatives. A domain search reported 2,000 and 500,000 in the docs' own example. **Never treat `total_results` as a creative count** — it will produce bogus "competitor scaled up 12%" events.
- Empty result set returns `search_information.results_state: "Fully empty"` (**undocumented**) *plus* a top-level `error` string, while `search_metadata.status` is still `"Success"`. AdWatch must not branch on `status` alone. (`raw/plat-PLAY.json`, `raw/region-uk.json`)

### 2.2 Detail engine — observed field inventory

`search_information`: `format`, `last_shown` (Unix epoch), `region_name`, `more_ads_by_advertiser`, `ad_funded_by`, `region` (int, undocumented, only when `region` passed), and `regions[]`.

`regions[]` per entry: `region` (int code), `region_name`, `first_shown` (optional), `last_shown`, `times_shown` (optional, bucketed string e.g. `"1000 - 2000"`).

`ad_creatives[]` — **this array is the creative's variations, not a list of creatives.** Observed 1–4 variations, mean 2.9. Documented keys: `call_to_action`, `title`, `headline`, `long_headline`, `snippet`, `visible_link`, `link`, `image`, `advertiser_logo`, `advertiser_logo_alt`, `sitelink_texts[]`, `sitelink_descriptions[]`, `video_link`, `raw_video_link`, `video_duration`, `thumbnail`, `height`, `width`, `channel_name`, `channel_icon`, `rating`, `reviews`, `reviews_link`, `address`, `is_verified`, `extensions[]`, `carousel_data[]{image, image_aspect_ratio, image_headline, button_link, button_text}`, `images[]{image, link, tag}`.

**Undocumented field observed:** `advertiser_name` — the *brand* display name (e.g. `"Breville"`, `"Purple®"`), distinct from the list engine's legal-ish `advertiser` (`"Breville USA Inc"`, `"Purple Innovation, LLC."`) and from `advertiser.legal_name`. Useful, but undocumented and therefore able to vanish.

**Type instability — must be handled:**
- `regions[].last_shown` came back as **YYYYMMDD integers** (`20260903`) in every live response I captured, while SerpApi's own doc examples show **Unix epochs** (`1755820800`) for the same field, and one doc example mixes both in one payload. Parse defensively: `value > 20000000 && value < 30000000` ⇒ YYYYMMDD, else epoch.
- `video_duration` documented as `HH:MM:SS`; doc sample shows `"00:00:15"`; **live response gave `"0:23"`**.
- `long_headline` can be `null`.
- `advertiser_logo` is sometimes rehosted under `https://serpapi.com/searches/<search_id>/images/<hash>.png` rather than googlesyndication. Those are tied to a search ID and are **not** durable — do not persist them as stable asset identity. (Undocumented.)

---

## 3. Is there a separate creative-detail call? Yes — and here is the honest delta

**Endpoint:** `engine=google_ads_transparency_center_ad_details`, params `advertiser_id` + `creative_id` (+ optional `region`). **Cost: 1 search per creative.** No batching, no pagination.

15 detail calls made across 5 advertisers.

**What the detail call adds over the list row:**

| Gain | Evidence |
|---|---|
| **Per-region footprint** with per-country `first_shown`/`last_shown` | 1–17 regions, mean 3.7. One coffee-retailer creative ran in 17 countries with distinct per-country start dates (`raw/det-brev-text.json`). |
| **Creative variations** (asset-level rotation) | One SaaS video creative returned 4 variations sharing one video/landing URL but with 3 distinct headlines — RSA-style asset rotation, invisible from the list. (`raw/det-hubspot-video.json`) |
| **Real landing-page URL** | Detail `link` = `https://www.hubspot.com/crm/e010a`, `https://www.breville.com/en-us/shop/ovens`, `https://purple.com/pillows`. The **list** `link` is a `displayads-formats.googleusercontent.com` *preview* URL — a completely different thing. |
| `times_shown` on non-political ads | Rare: **2 of 59 region rows (3%)**. Not something to build a feature on. |
| `carousel_data[]` | 10-card carousel with per-card headline + destination (`raw/det-purple-image.json`). |
| `ad_funded_by`, `advertiser_name`, `channel_name`, `extensions` | Present on richer formats. |

**What the detail call does NOT give you — the critical caveat:**

> **12 of 12 text-format creatives returned `ad_creatives: [{"image": "…"}]` and nothing else.** No headline, no snippet, no sitelinks, no landing URL.

This held across all five advertisers I tested **and for the exact creative SerpApi's documentation uses as its text-ad example** (`advertiser_id=AR12039459359856525313`, `creative_id=CR11382217505440268289`). The docs show that creative returning `title`, `headline`, `snippet`, `visible_link`, and a 5-entry `sitelink_texts`. Live, today, it returns one `image` URL. (`raw/det-doc-spaceship.json`)

The docs acknowledge this case ("the ad is returned as a single rendered image… none of the text or structure can be extracted directly") but present it as an exception. **Observed, for text format it is the rule.** Breakdown by format:

| Detail format | Copy extractable | Image-only |
|---|---|---|
| `text` | **0** | **10** |
| `image` | 2 | 0 |
| `video` | 2 | 0 |

**Implication for AdWatch:** do not build "competitor changed their search ad headline" on the detail endpoint. It will silently return nothing for the exact format paid-search teams care most about. Spend detail calls on **video and image** creatives, and on **geo footprint**, which works for all formats.

---

## 4. Advertiser discovery — what actually works

**Verdict: keyword/topic discovery does not exist. Domain-based competitor discovery does, and it is genuinely useful.**

`text` was probed with 9 non-domain forms. All 9 returned zero results (`"Google Ads Transparency Center hasn't returned any results for this search."`):

| Probe | Result | File |
|---|---|---|
| `memory foam mattress` | 0 | `raw/kw-mattress.json` |
| `crm software` | 0 | `raw/kw-crm.json` |
| `espresso machine` | 0 | `raw/kw-espresso.json` |
| brand name alone | 0 | `raw/kw-brandname.json` |
| brand name, no TLD | 0 | `raw/txt-bare-hubspot.json` |
| exact legal name incl. `, LLC.` | 0 | `raw/txt-legalname.json` |
| `www.<domain>` | 0 | `raw/txt-www.json` |
| `blog.<domain>` (subdomain) | 0 | `raw/txt-sub.json` |
| `<domain>/pillows` (path) | 0 | `raw/txt-path.json` |

Bare registrable domains all worked. **`text` is effectively a `target_domain` exact-match filter.** The doc phrase "you can use anything that you would normally use in a standard Google Ads Transparency Center search" is misleading.

**What domain search is actually good for — and it is good.** A domain search returns every advertiser whose creatives *target that domain*, not just the domain owner. Live results for three domains:

- Coffee-equipment domain, 40 rows → **14 distinct advertisers**: the brand itself (16 creatives), the brand's parent entity, and 12 third parties — affiliates and arbitrage advertisers.
- B2B SaaS domain, 40 rows → **11 distinct advertisers**: the brand (28), plus a performance agency and several competitors/resellers running ads against the brand's domain.
- Mattress domain, 40 rows → 3 advertisers, brand-dominated (38/40).

So the discovery play is: **1 search per seed domain surfaces brand-term poachers, affiliates, and adjacent competitors.** That is the competitor-discovery feature AdWatch wants — it just keys on domains, so the product must ask the user for competitor *domains* (or derive them), never topics.

The response's `target_domain` field (present on 100% of `text`-search rows, 0% of `advertiser_id` rows) is what ties a creative back to the seed domain. AdWatch does not read it.

---

## 5. Pagination and cost

### Mechanics (measured, not estimated)

Enumerated a B2B SaaS advertiser at `num=100`:

| Page | Creatives | `next_page_token` |
|---|---|---|
| 1–6 | 100 each | present |
| 7 | 27 | **absent** |
| **Total** | **627 unique** | — |

**627 rows returned, 627 unique `ad_creative_id` — zero duplicates across pages.** Terminate on absence of `serpapi_pagination.next_page_token` (`total_results` said 700; the true count was 627).

**Ordering: `last_shown` descending.** Page 1 row 1 was the most recently active creative; the page-7 tail was ~12 months old. This is the single most cost-relevant fact in this report — see §5.3.

### Billing

- SerpApi pricing FAQ (<https://serpapi.com/pricing>): *"Only successful searches are counted toward your monthly searches. Cached, errored, and failed searches are not. The number of results returned per response will not affect the number of credits used—responses with 100 results or empty result sets will both count as 1 search."*
- **Each page is a separate billed search.** Directly measured: balance fell by exactly 7 across the 7-page run.
- **Cached repeats are free.** An identical repeat query within the 1h TTL produced a 0 credit delta (`raw/cost2-cached-x.json`).
- `num=100` costs the same as `num=40`. Measured, and consistent with the FAQ.
- **`get_advertiser=true` cost is UNRESOLVED.** One tight measurement showed a 2-credit delta; a repeat showed noise. The docs say "an additional request is made," which suggests 2 credits. **Treat as 2 until confirmed on a private key.** Cheap mitigation: fetch the advertiser block once per advertiser at onboarding, never on the polling path.

> **Measurement caveat, stated plainly.** The key is shared with concurrently-running sibling agents. Sampling `total_searches_left` five times over 30 seconds while issuing **zero** searches showed a monotonic drain of 1–2 credits per 6 seconds. Credit-delta arithmetic on this key is therefore unreliable except where a delta landed exactly on a large expected value (the 7-page run did). The **request counts** below are exact — I counted my own HTTP calls.

### Cost to enumerate 200 creatives

| Strategy | Searches | Note |
|---|---|---|
| `num=100`, full enumeration | **2** | 2 pages covers 200. |
| `num=40` (default), full enumeration | 5 | **AdWatch should send `num=100` unconditionally.** |
| 627-creative advertiser, full | 7 | Measured. |
| + `get_advertiser=true` | +1 (probably) | Onboarding only. |
| + all 3 `creative_format` facets | +3× the above | |
| + all 5 `platform` facets | +5× the above | |

### 5.3 The cost lever nobody would guess

Because results are sorted **`last_shown` desc**, and because a creative that is still running has `last_shown` within the last day, **page 1 alone contains every currently-active creative**, provided the active set is smaller than `num`.

Measured on the 627-creative advertiser: **256 creatives (41%) had `last_shown` within the current 3-day window**; the rest were dormant. The archive retains stopped creatives for **~12 months** (oldest `last_shown` was exactly 12 months back), so full enumeration is mostly paying to re-download a year of dead ads.

**Recommendation: poll with `num=100`, page 1 only, and stop.** That is **1 search per advertiser per run** instead of 7, detects every launch and every pause, and re-enumerates fully only on a weekly/monthly cadence to catch the long tail. This is a ~7× cost reduction on the hot path with no signal loss for launch/pause events.

---

## 6. Untapped opportunities, ranked by value-per-search

### 6.1 `creative_link_churn` — **fix a live bug first. Cost: 0 searches. Do this before anything else.**

AdWatch normalizes `link`. **`link` is not stable.** Two runs of an identical query ~10 minutes apart, keyed on `ad_creative_id`:

```
creatives with link:  36/98
link changed on:      36  (100% of link-bearing creatives)
image changed:         0
details_link changed:  0
last_shown changed:    0
```

Decomposing the URL query string, exactly two params differ between runs:

```
UNSTABLE: htmlParentId, responseCallback     ← per-request render nonces
STABLE:   client, obfuscatedCustomerId, creativeId, adGroupId,
          assets, allowedVariations, sig, uiFeatures, versionId, overlay
```

**Consequence today:** every polling run emits a spurious "creative changed" event for ~30% of an advertiser's creatives (100% of the link-bearing ones). That is pure noise into the diff and into Claude's brief.

**Fix:** before hashing or diffing, drop `htmlParentId` and `responseCallback` from the `link` query string. Everything else is stable and safe to diff.

**Extra search cost: zero.** This is a normalizer change.

---

### 6.2 `campaign_structure_shift` / `creative_revised` — **highest value-per-search in the report. Cost: 0 searches.**

The same `link` you already download encodes Google-internal identifiers that are exposed nowhere else in the API. Parsed across 627 creatives of one B2B SaaS advertiser (191 had a `link`):

| Param | Coverage | What it is | What it reveals |
|---|---|---|---|
| `adGroupId` | 191/191 | Ad group ID | **33 distinct ad groups.** New ID = new ad group launched. |
| `obfuscatedCustomerId` | 191/191 | Google Ads account | **6 distinct accounts** — agency/geo/brand account splits |
| `creativeId` | 191/191 | Numeric creative ID | Joins to the ATC creative |
| `versionId` | 116/191 | Revision counter, observed 1–8 | **Bump = creative edited in place under the same `ad_creative_id`** |
| `assets` | 108/191 | Encoded asset bundle | Asset-set change detection |

**Events this enables:**

- `adgroup_launched` — an `adGroupId` not seen in the previous run appears. A paid-search team cares because a new ad group is a new targeting theme or a new product line going live — the earliest structural signal of a competitor's expansion, days before creative volume moves.
- `account_added` — a new `obfuscatedCustomerId`. Signals an agency change, a new geo entity, or a separate brand account. High-salience, low-frequency.
- `creative_revised` — `versionId` increments while `ad_creative_id` is unchanged. Today AdWatch sees nothing: the creative ID is stable and `first_shown` doesn't move, so an in-place rewrite is completely invisible. This is a real blind spot.

**Extra search cost: zero.** Parse the URL you already have. Caveat: only 30% of creatives carry `link` (mostly video), and these are undocumented URL internals that Google can change without notice — gate the parse behind a feature flag and fail soft.

---

### 6.3 `creative_longevity` (from `total_days_shown`) — **Cost: 0 searches.**

Present on **100%** of creatives, never read. Documented as "number of days the ad was **actually shown** between first and last shown" — and observed to be genuinely less than the calendar span (e.g. `first_shown` 2025-04, `last_shown` today = 520-day span, `total_days_shown` = 490), so it is a real activity-intensity measure, not a subtraction.

**Events:**
- `creative_promoted_to_evergreen` — `total_days_shown` crosses a threshold (say 90). Marks a proven winner in the competitor's rotation. A paid-search team wants to copy-test against *proven* creatives, not one-week experiments.
- `creative_stalled` — `last_shown` still recent but `total_days_shown` stopped incrementing between runs ⇒ the ad is technically live but barely serving. Budget throttling or a losing auction position.

**Extra search cost: zero.**

---

### 6.4 `format_mix_shift` and `size_mix_shift` (from `format` + `width`/`height`) — **Cost: 0 searches.**

`width`/`height` present on 67% of creatives, never read. Observed format mixes differ sharply by advertiser: mattress brand 40% image / 36% text / 24% video; SaaS brand 3% image / 59% text / 38% video; coffee retailer 26% / 62% / 12%.

- `format_mix_shift` — the ratio moves materially run-over-run. A jump in `video` share means a competitor is funding YouTube/Demand Gen, which changes auction dynamics and CPMs.
- `new_creative_size` — a `width`x`height` pair not previously seen. New display placements or a new DCO template.

**Extra search cost: zero.**

---

### 6.5 `channel_mix_shift` (from `platform`) — **Cost: 4 extra searches per advertiser per run.**

Verified that `platform` genuinely partitions, not merely re-labels: for one advertiser, SEARCH∩YOUTUBE overlap was 11 of 40 rows, and each facet returned different format compositions (SHOPPING → image+text only; MAPS → text+video only; PLAY → empty). Note a creative can appear under multiple platforms, so facet counts overlap and do not sum to the total.

- `platform_entered` — an advertiser with zero SHOPPING creatives starts returning them. Direct read on a competitor entering Shopping/PMax or launching Local campaigns. Detected via `results_state: "Fully empty"` flipping to populated.
- `platform_exited` — the inverse; a channel goes to zero.

**Cost:** 5 facet calls (page 1 only, `num=100`) instead of 1 = **+4 searches per advertiser per run.** Best run weekly rather than per-poll. Combined with the §5.3 page-1 optimization, an advertiser costs 5 searches/week for full channel visibility versus 7/run today for less information.

---

### 6.6 `geo_expansion` / `geo_exit` (from detail `regions[]`) — **Cost: 1 search per creative watched.**

The list engine gives no geography at all. The detail call gives per-country `first_shown`/`last_shown` — up to **17 countries** on a single observed creative, mean 3.7.

- `geo_expansion` — a `region` code appears in a watched creative's `regions[]` that wasn't there last run, with a `first_shown` in the last few days. A competitor launching in a new country is a market-entry signal that normally takes weeks to notice.
- `geo_exit` — a region's `last_shown` stops advancing while others keep moving. Country-level pullback.

**Cost: 1 search per creative per check.** Do **not** run this over an entire advertiser (627 creatives = 627 searches). Run it on a small watchlist — the top 5–10 creatives by `total_days_shown` (the evergreen winners from §6.3), refreshed weekly: **5–10 searches per advertiser per week**. Alternative near-free proxy: run the list engine with `region=<code>` and check for `results_state: "Fully empty"` — 1 search per region tested, and it detects presence/absence at the advertiser level rather than the creative level.

---

### 6.7 `landing_page_changed` (from detail `link`) — **Cost: 1 search per creative watched.**

The list `link` is a googleusercontent **preview** URL. The detail `link` is the **actual destination** (`…/crm/e010a`, `…/shop/ovens`, `…/pillows`). A competitor repointing a creative from a category page to a promo LP, or changing a tracking suffix, is a direct read on an offer change.

**Only works for image and video creatives** (text creatives return image-only — §3). Bundle this with §6.6: one detail call yields both geo footprint and landing URL. **Marginal cost: zero** if you're already making the call for geo.

---

### 6.8 `creative_variation_churn` (from detail `ad_creatives[]`) — **Cost: 1 search per creative watched.**

The detail `ad_creatives[]` array is the creative's **variations**: 1–4 observed, mean 2.9. One SaaS video creative carried 4 variations with 3 distinct headlines over one shared video and landing URL — asset rotation entirely invisible from the list.

- `variation_added` / `variation_headline_changed` — the variation count or headline set changes for a stable `ad_creative_id`. This is the closest thing available to "competitor is A/B testing new messaging," and it is the strongest input for Claude's brief.

**Cost: zero marginal** if bundled with §6.6/§6.7. Again image/video only.

---

### 6.9 `brand_term_poacher` (from `text` search + `target_domain`) — **Cost: 1 search per seed domain per run.**

A domain search returns every advertiser targeting that domain. Live, a single 40-row query surfaced 14 distinct advertisers on one seed domain, 11 on another — affiliates, arbitrage players, and a competing agency.

- `poacher_appeared` — an `advertiser_id` other than the brand's own appears against the user's domain. Trademark/brand-defense alert; paid-search teams act on this within hours.
- `competitor_discovered` — a new advertiser appears against a *competitor's* domain, expanding the watch list without the user naming anyone.

**Cost: 1 search per seed domain per run.** The cheapest discovery mechanism available, and the only one — there is no keyword search (§4).

---

### 6.10 Political disclosures — **not applicable to AdWatch. Cost: n/a.**

`minimum_views_count`, `maximum_views_count`, `minimum_budget_spent`, `maximum_budget_spent` are populated **only** under `political_ads=true` (verified live: all four present on 20/20 creatives of a political advertiser, absent from all 727 commercial creatives I pulled). They are the only spend/impression data in the API, and they are unreachable for commercial advertisers. `times_shown` on the detail endpoint is the sole non-political impression signal and appeared on just **2 of 59 region rows (3%)** — too sparse to build on.

**Do not promise spend or impression estimates for commercial advertisers from this engine.**

### Ranking summary

| # | Event family | Extra searches | Value |
|---|---|---|---|
| 1 | `creative_link_churn` (bug fix) | **0** | Removes false positives on ~30% of creatives every run |
| 2 | `adgroup_launched` / `account_added` / `creative_revised` | **0** | Structural signals available nowhere else |
| 3 | `creative_longevity` | **0** | Separates proven winners from experiments |
| 4 | `format_mix_shift` / `size_mix_shift` | **0** | Channel-funding shifts |
| 5 | `brand_term_poacher` / `competitor_discovered` | 1 / seed domain | Only discovery path that exists |
| 6 | `channel_mix_shift` | 4 / advertiser / run | Channel entry/exit |
| 7 | `geo_expansion` + `landing_page_changed` + `variation_churn` (one call) | 1 / creative | Deep, but image/video only |

Items 1–4 are free and should ship first. Item 5 is the discovery feature. Items 6–7 are opt-in premium.

---

## 7. Timestamp semantics and diffing (answers to "are `first_shown`/`last_shown` stable?")

- **Format:** Unix epoch seconds, UTC, on both engines' top-level fields. `regions[].last_shown` is the exception — see §2.2 type instability.
- **`first_shown`: stable.** Zero changes across two runs on 98 common creatives.
- **`last_shown`: stable within a run window, but it is a live value.** Zero changes over ~10 minutes despite second-level precision, so it appears to update at roughly daily granularity. Active creatives carried `last_shown` equal to *today* with an intraday time component. Expect it to advance daily for every running creative — so **`last_shown` must not be part of a "creative changed" hash**; use it only as the liveness signal.
- **Stopped creatives are retained ~12 months.** The oldest `last_shown` in a full 627-creative enumeration was exactly 12 months back, with a smooth monthly distribution. So "creative disappeared from the API" is a ~12-month-delayed signal, not a pause signal. **Detect a pause as "`last_shown` stopped advancing for N days," never as "row vanished."**
- **Page membership is not stable.** Two runs 10 minutes apart on page 1 (`num=100`) showed 2 creatives entering and 2 leaving, purely from `last_shown` reordering at the page boundary. **Diff by `ad_creative_id`, never by position, and treat page-boundary entries/exits as noise unless confirmed on a full enumeration.**

---

## 8. DOCUMENTED vs OBSERVED — consolidated

| Topic | Documented | Observed |
|---|---|---|
| `num` max | "40 (default)… 100 returns 100" — no bound stated | Hard bound **1–100**, HTTP 400 outside it |
| `text` | "anything you would normally use in a standard ATC search" | **Bare registrable domain only.** 9/9 other forms returned zero |
| Text-ad detail fields | `title`, `headline`, `snippet`, `sitelink_texts` shown in the flagship example | **0/12 text creatives returned any of these**, including that exact example creative. All returned `[{"image": "…"}]` |
| `regions[].last_shown` | "Integer — Unix epoch"; doc samples show both | **YYYYMMDD integers** in every live capture |
| `video_duration` | `HH:MM:SS` (`"00:00:15"`) | `"0:23"` |
| `link` / `image` on list | Both listed unconditionally | Near mutually exclusive, format-driven: video→`link` (99%), text→neither (97%) |
| `link` stability | not discussed | **Non-deterministic**; two nonce params change every request |
| `total_results` | "Count of ads matching" | **Rounded estimate.** 700 reported vs 627 actual |
| Empty results | not documented | `search_information.results_state: "Fully empty"` + top-level `error`, with `status: "Success"` |
| `advertiser_name` (detail) | absent from structure overview | Present; brand name distinct from legal name |
| `search_information.region` (detail) | absent from structure overview | Present as integer when `region` passed |
| `search_metadata.markdown_endpoint` | absent from structure overview | Present on all responses |
| `advertiser_logo` host | implied googlesyndication | Sometimes rehosted under `serpapi.com/searches/<id>/images/…` — search-scoped, not durable |
| `times_shown` | listed as a normal `regions[]` field | **3% of region rows** on commercial ads |
| Political fields | "only available for Political Ads" | Confirmed exactly: 20/20 political, 0/727 commercial |
| Result ordering | not documented | **`last_shown` descending** — the basis of the §5.3 cost optimization |

**Undocumented fields are flagged as such throughout.** The load-bearing ones for the recommendations above are the `link` URL query params (§6.2) and result ordering (§5.3); both should be feature-flagged and fail soft, since SerpApi can change either without a release note.

---

## 9. Concrete recommendations for AdWatch

**Ship now (zero search cost):**
1. Strip `htmlParentId` + `responseCallback` from `link` before diffing. Stops false-positive churn on ~30% of creatives per run.
2. Send `num=100` always (currently defaulting to 40 costs 2.5× the pages).
3. Normalize `total_days_shown`, `width`, `height`, `target_domain`.
4. Parse `adGroupId`, `obfuscatedCustomerId`, `versionId` out of `link`; emit `adgroup_launched`, `account_added`, `creative_revised`.
5. Stop treating `total_results` as a count.
6. Branch on `search_information.results_state` / top-level `error`, not on `search_metadata.status`.
7. Exclude `last_shown` from the creative-identity hash; use it only for liveness. Detect pause as "`last_shown` stopped advancing," not "row vanished."

**Cost-model changes:**
8. Hot path = page 1 only, `num=100`, 1 search per advertiser per run (was up to 7). Full enumeration weekly.
9. Move `get_advertiser=true` to onboarding only (possibly 2 credits, and the data never changes).

**New features:**
10. Domain-seeded discovery: 1 search per seed domain per run → `brand_term_poacher`, `competitor_discovered`. Product must collect competitor *domains*; there is no topic search.
11. Weekly `platform` facet sweep: +4 searches/advertiser/week → `channel_mix_shift`.
12. Detail-call watchlist: top 5–10 creatives by `total_days_shown`, **image/video only**, weekly → `geo_expansion`, `landing_page_changed`, `variation_churn` from one call each.

**Do not build:** spend or impression estimates for commercial advertisers; search-ad headline diffing via the detail endpoint; any keyword/topic competitor discovery.

---

## 10. Spend accounting

- **Balance at start:** `total_searches_left = 14326`.
- **Balance at finish:** `total_searches_left = 13974`.
- **My HTTP requests: 72** (exact count of files I wrote to `raw/`). Of those, **7 returned HTTP 400** (validation errors — not billed per the pricing FAQ) and **1 was a cached identical repeat** (free, 0 delta observed). **Billable ≈ 64**, plus up to +3 if `get_advertiser=true` bills twice ⇒ **≈ 64–67 of the 150 budget.**
- The raw balance delta of 352 is **not** my spend: the key is shared with concurrently-running sibling agents, and I measured a background drain of 1–2 credits per 6 seconds with zero calls of my own (`raw/acct-drift*`, and the sampling run in §5). Sibling files (`sweep_*`, `kw[0-9]*`, `acct-scan*`, `q_*`) are present in the same `raw/` directory.
- **Key hygiene:** the key was never echoed, logged, or written. `search_parameters.api_key` is deleted from every saved file and the key string is replaced with `REDACTED`. A recursive `grep` for the 64-char key across the entire scratchpad returns **no matches**.

---

## 11. Sources

**Documentation (read live, 2026-09-03):**
- <https://serpapi.com/google-ads-transparency-center-api> — list engine params, results, JSON structure overview, 4 worked examples
- <https://serpapi.com/google-ads-transparency-center-ad-details> — detail engine params, results, 4 worked examples
- <https://serpapi.com/google-ads-transparency-center-regions> and <https://serpapi.com/google-ads-transparency-center-regions.json> — 239 region codes
- <https://serpapi.com/google-ads-transparency-center-api/release-notes> — `get_advertiser` legal name/country (2026-08-31); image fix (2025-11-01); `platform` param (2025-01-08); destination-URL scraping (2024-07-09)
- <https://serpapi.com/google-ads-transparency-center-ad-details/release-notes> — image fix (2026-03-19); availability fix (2025-11-06)
- <https://serpapi.com/pricing> — "How are searches counted?"
- <https://serpapi.com/blog/scrape-competitors-google-ads-data-using-python/> — recursive `next_page_token` pattern; `num` max 100

**Live probe index** (all under `scratchpad/raw/`, key-redacted):

| Group | Files | Purpose |
|---|---|---|
| Discovery | `disc-text-{breville,purple,hubspot}` | Domain search, competitor surfacing |
| Enumeration | `adv-{purple,hubspot,breville}-n100`, `adv-klientboost` | Field inventory, `advertiser` block |
| Pagination | `pg-hubspot-p1`…`p7` | 627 creatives, 7 pages, exact cost |
| Cost | `cost-*`, `cost2-*` | Per-search billing, cache behaviour |
| Filters | `fmt-{text,image,video}`, `plat-{SEARCH,YOUTUBE,SHOPPING,MAPS,PLAY}` | Facet partitioning |
| Bounds | `num-{1,200,500}`, `region-{uk,none}`, `multi-adv` | Limits and multi-ID |
| Dates | `date-aug26`, `date-2024` | Date-window semantics |
| Political | `pol-{docsadv,text,noregion}` | Spend/impression disclosures |
| Detail | `det-purple-*`, `det-hubspot-*`, `det-brev-*`, `det-doc-spaceship`, `det-klientboost` | Variations, regions, landing URLs, text-ad limitation |
| Discovery limits | `kw-*`, `txt-*` | 9 negative results proving no keyword search |
| Errors | `err-*` | Validation messages |
| Stability | `stab-run2` | Re-run diff proving `link` churn |
