# SerpApi `google` engine — the paid surface, for AdWatch

**Research date:** 2026-09-03
**Method:** current live docs (serpapi.com) + **107 live API calls** (102 billable, 5 cache hits) against a real key.
**Raw responses:** `scratchpad/raw/*.json` (API key stripped from every file; leak check clean).
**Budget:** 150 allowed, **102 billable searches spent**. Account before: 14,323 searches left. After: 13,907 (delta includes concurrent agents sharing the key).

Every claim below is tagged **[DOC]** (documented), **[OBS]** (observed in my saved responses), or **[INFERRED]**.

---

## 0. Executive summary — read this first

Three findings invalidate parts of AdWatch's current design. They matter more than the field inventory.

1. **The `ads` array is wildly non-deterministic.** Nine identical back-to-back `no_cache=true` calls for `best vpn` returned **5, 1, 0, 0, 6, 1, 1, 0, 0** ads. A *single* search sees on average **20.4% of the advertiser universe**, and has a **44.4% chance of returning zero ads** on a query that demonstrably has six advertisers. AdWatch diffs one sample against the previous one sample — that pipeline will emit mostly noise. **[OBS]**
2. **SerpApi caches identical searches for 1 hour and serves them free.** Four identical calls returned the *same* `search_metadata.id`. A scheduled diff that doesn't set `no_cache=true` may diff a byte-identical cached response and see no change at all. **[DOC]** + **[OBS]**
3. **Ad extensions barely exist.** Across **113 real ads**, `extensions[]` appeared on 27% and contained *only* Google's "N visits in past month" traffic annotation. There is **no** callout, structured-snippet, promotion, price-extension, or call-extension field. Sitelinks are the only genuine ad extension exposed. **[OBS]**

The zero-extra-cost wins are in §7. The biggest is that AdWatch currently discards ~90% of every response it already pays for.

---

## 1. Every paid / commercial block the `google` engine can return

The authoritative list of result sub-pages for `engine=google` is the "Google Search API" section of the SerpApi sidebar (https://serpapi.com/search-api). Ad-relevant members:

| Block | JSON key | Doc URL | Observed live? |
|---|---|---|---|
| Text ads | `ads` | https://serpapi.com/google-ads | **Yes** — 113 ads / 40 responses |
| Shopping (PLA) | `shopping_results` | https://serpapi.com/inline-shopping | **No — never appeared** in 159 responses |
| Immersive products | `immersive_products` | https://serpapi.com/immersive-result | **Yes** — the live shopping block |
| Local ads | `local_ads` | https://serpapi.com/local-ads | **No** — never appeared |
| Paid local pack entry | `local_results.places[].ad` | undocumented on the local-pack page | **Yes** — mobile/tablet |
| Product result | `product_results` | https://serpapi.com/product-result | Yes (rare) |
| Flight result | `flight_results` | https://serpapi.com/flight-result | Not observed |

> **Critical URL correction.** `https://serpapi.com/google-ads-shopping-results` and `https://serpapi.com/google-ads-local-results` belong to the **separate `engine=google_ads` API**, *not* to `engine=google`. Do not build against them expecting the `google` engine to return those shapes.

### 1.1 `ads[]` — the text-ad block

**Observed field census across 113 live ads** (`raw/*.json`, all `engine=google`):

| Field | Type | Present | Notes |
|---|---|---:|---|
| `position` | Integer | **100%** | 1-based, **restarts per block** — not globally unique |
| `title` | String | **100%** | Headline. Pipe-separated H1\|H2\|H3 |
| `link` | String | **100%** | **Often a `google.com/goto?url=` or `aclk?` redirect, NOT the advertiser URL** |
| `displayed_link` | String | **100%** | Vanity path, e.g. `https://www.nordvpn.com`. **The reliable domain source** |
| `tracking_link` | String | **100%** | Google `aclk` click URL |
| `source` | String | 94.7% | Advertiser display name (`NordVPN™`, `Forbes`) |
| `description` | String | 91.2% | Ad body. **Callouts/structured snippets are buried in here as prose** |
| `block_position` | String | **90.3%** | `top` (46.9%) / `bottom` (43.4%) / **missing (9.7%)** |
| `sitelinks[]` | Array | 69.0% | See §2 |
| `extensions[]` | Array<String> | 27.4% | See §2 — only traffic annotations |
| `thumbnail` | String | 22.1% | SerpApi-proxied or `tpc.googlesyndication.com` image |
| `reviews` | Integer | 7.1% | Seller-rating review count |

**Advertiser identity** → `source` (best), fallback `displayed_link`. **Do not use `link`** — it is a Google redirect ~half the time.
**Position** → `position` + `block_position` (both needed; `position` restarts within each block).
**Price** → not present on text ads in any live sample (see §8).

**[OBS] Data-quality trap:** `source` is not always a brand. In `raw/geo_austin_2.json` one ad's `source` is the sentence *"Free consultations for accident victims across all case types, with no upfront costs ever."* Normalise on `displayed_link`'s registrable domain, not `source`.

**[DOC] but NOT observed** — the docs page https://serpapi.com/google-ads shows these on `ads[]`, none of which reproduced in Sept-2026 traffic (see §8): `price`, `extracted_price`, `rating`, `reviews` on hotel ads; `vehicles_for_sale[]` (`title`,`thumbnail`,`price`,`extracted_price`,`condition`,`mileage`,`extracted_mileage`,`dealership`,`location`,`link`); `links[]` (`text`,`tracking_link`,`image`) for mobile location extensions; `phone` (mentioned in the page's prose only, never in any sample JSON — **undocumented-by-example**).

### 1.2 `immersive_products[]` — the live shopping block

`shopping_results` is what https://serpapi.com/inline-shopping documents for `engine=google`. **It never appeared in 159 live responses.** What actually returns is `immersive_products`. **[OBS]**

Observed fields: `category`, `title`, `thumbnail`, `source`, `source_logo`, `price`, `extracted_price`, `original_price`, `extracted_original_price`, `rating`, `reviews`, `delivery`, `location`, `extensions[]`, `immersive_product_page_token`, `serpapi_link`.

`category` values observed: `Popular products`, `More products`, `In stores nearby`, `Shop by store`, `Deals`, `Deals on <X>`.

**[INFERRED]** No `category` value marks these explicitly "Sponsored", so `immersive_products` is a *commercial* block mixing paid and organic listings — treat it as merchandising/price intelligence, not proof of ad spend.
**Cost note:** `serpapi_link` / `immersive_product_page_token` point at `engine=google_immersive_product` — following them is **+1 search each**.

### 1.3 `local_results.places[].ad` — paid local pack (undocumented, high value)

**[OBS]** In `raw/dev_pilawyer_mobile.json` and `raw/dev_pilawyer_tablet.json`, a local pack entry carries `"ad": true`. This flag is **not documented** on https://serpapi.com/local-pack or https://serpapi.com/local-results.

The paid place object carries: `position`, `title`, `type`, `rating`, `reviews`, `description` (e.g. `"15+ years in business"`), `lsig`, `images[]`, `links.phone`, `links.website`, `links.directions`, `place_id`, `place_id_search`, `provider_id`, `gps_coordinates.{latitude,longitude}`, **`ad: true`**, `address`, `hours`, `phone`.

This is the **only place a competitor phone number appears** in the whole `google` response. It appears on **mobile/tablet, where `ads` is empty**, and it was more stable than text ads across the geo matrix.

### 1.4 Blocks that did not materialise

`local_ads` (https://serpapi.com/local-ads — documented shape: `local_ads.{title,badge,see_more_text,link,tags[],ads[]}` with `ads[].{position,title,link,rating,rating_count,type,service_area,hours,years_in_business,phone,thumbnail,highlighted_details[]}`) never appeared across six home-services queries (`emergency plumber`, `locksmith`, `hvac repair`, `garage door repair`, `electrician near me`, `house cleaning service`) in Austin. **[OBS]** Google Local Services Ads appear to be served through the dedicated `engine=google_local_services` API instead. **[INFERRED]**

---

## 2. Ad extensions — the definitive answer

This was flagged as the highest-value question. **The honest answer is that SerpApi's `google` engine exposes only one real ad extension type.**

### Sitelinks — YES, `ads[].sitelinks[]`
318 sitelink objects observed across 113 ads (69% of ads carry them).

| Subfield | Present |
|---|---:|
| `title` | 318 / 318 (100%) |
| `link` | 318 / 318 (100%) |
| `snippets[]` (Array<String>) | **30 / 318 (9.4%)** |

`snippets` is documented as standard on https://serpapi.com/google-ads but is present on fewer than one in ten live sitelinks. **[OBS]**

### Callouts, structured snippets, promotions, prices, phone — **NO**

`ads[].extensions[]` is present on only 27.4% of ads, and **every single observed value** across 113 ads was a Google traffic annotation:

```
20x  "1M+ visits in past month"
 7x  "100K+ visits in past month"
 4x  "10K+ visits in past month"
```

That is the complete observed value set. There is **no** `callouts`, `structured_snippets`, `promotion`, `price_extension`, `call_extension`, or `phone` field on `ads[]` in live data. **[OBS]**

The docs page prose claims ads "can contain … `phone` …" (https://serpapi.com/google-ads) but no sample JSON on that page shows `phone`, and I never observed it. **[OBS]**

> **Consequence for AdWatch.** "Extension changes as a competitive signal" is only viable for **sitelinks** (a genuinely rich, 69%-coverage signal) and for **the `description` string**, into which Google folds callout and structured-snippet text. Detecting a *callout* change means diffing `description` prose, not a typed field. A competitor's phone number is reachable only via `local_results.places[].ad`.

---

## 3. Parameters that change what paid results you see

All descriptions quoted from https://serpapi.com/search-api. All params below were sent live and echoed back in `search_parameters` (`raw/p_*.json`, `raw/ctry_*.json`, `raw/num*.json`).

### Materially changes the paid block

| Param | Doc text / behaviour | Effect on ads | Verdict |
|---|---|---|---|
| **`no_cache`** | "Cache expires after 1h. **Cached searches are free.**" | Without it you may get a byte-identical cached response — a silent no-op diff. With it, results are fresh *and volatile*. | **MUST SET** for a diffing product |
| **`location`** | "defines from where you want the search to originate… recommended to specify at the city level… If omitted, the search may take on the location of the proxy." | **Decisive.** 6/6 baseline queries with no `location` returned **zero ads**. Adding `location=Austin` made `personal injury lawyer` return 2 ads. Metro-to-metro advertiser sets were **disjoint** (§4). | **MUST SET** |
| **`device`** | `desktop` (default) / `tablet` / `mobile` | **Decisive.** `best vpn` Austin: desktop 6 ads, **mobile 0**, tablet 1. `student loan refinance`: desktop 6, mobile 0, tablet 0. Confirmed across 3 repeats — mobile consistently 0 text ads. **But** mobile is where `local_results.places[].ad` appeared. | Desktop for text ads; mobile for paid local pack |
| **`gl` / `google_domain`** | country code / Google domain | Changes advertiser set: `best vpn` — UK → {Cybernews, NordVPN}; Canada → {Cybernews, NordVPN, **Surfshark**, Top10VPN}; Germany (`hl=de`) → 0 ads. | Set both, matched |
| **`uule`** | "Google encoded location… can't be used together with `location`." | Accepted and echoed; returned ads where the plain `location` control returned 0 (single sample, confounded by volatility). Equivalent addressing mechanism to `location`. | Alternative to `location` |

### Does NOT materially help the paid block

| Param | Observed | Verdict |
|---|---|---|
| **`start`** | `start=10` → **0 ads in both samples**, organic=10. Ads are page-1 only. | **Never page for ads** — pure wasted spend |
| **`num`** | `num=100` did **not** expand organic (still 9 results) and did not surface extra ad blocks; bottom-block ads already appear at `num=10`. Google deprecated `num=100` in 2025. **[INFERRED]** | Leave at 10 |
| `safe`, `filter`, `cr` | Accepted, echoed; ad counts within volatility noise | Ignore |
| `tbs=qdr:w`, `lr=lang_en`, `nfpr=1` | Accepted; **collapsed `organic_results` to 0** in my tests (over-restrictive). `lr=lang_en` still returned 2 ads with 0 organic. | Avoid — they break organic context |
| `lat`/`lon`/`radius` | "can't be used together with `location` and `uule`". `radius` range: Desktop 1..199, Tablet 1..1000 (metres) | Only if you need sub-city precision |

**`json_restrictor`** (https://serpapi.com/json-restrictor) — restricts returned fields to shrink payload. Same search cost; useful for bandwidth, not quota.

---

## 4. Geo granularity

**Mechanism.** `location` takes a **canonical name** from the free Locations API: `GET https://serpapi.com/locations.json?q=Austin&limit=5` (https://serpapi.com/locations-api — "This API is free to use", does **not** consume a search).

Each entry returns `id`, `google_id`, `name`, **`canonical_name`**, `country_code`, **`target_type`**, `reach`, `gps[lon,lat]`. `target_type` is the granularity ladder — observed values include **`DMA Region`** (`Austin, TX,Texas,United States`, reach 5.56M) and **`City`** (`Austin,Texas,United States`, reach 4.87M); the full set also includes Country, State, County, Postal Code, Airport, University.

Pass either `canonical_name` **or** the `id` as the `location` value. AdWatch's freeform string is therefore **risky**: the docs warn "If several locations match the location requested, we'll pick the most popular one." A freeform `"Austin"` may silently resolve to the DMA rather than the city — a different ad auction. **Resolve through `/locations.json` once and persist the `canonical_name` or `id`.**

Precision ladder, most to least precise: `lat`+`lon`+`radius` (metres) → `uule` → `location` canonical name (City) → `location` (DMA/State) → `gl` alone (country) → nothing (proxy location, **which yielded zero ads**).

**Is metro monitoring a real feature? Yes — decisively.** `personal injury lawyer`, 3 samples per metro (`raw/geo_*.json`):

| Metro | Text-ad advertisers (union of 3) | Paid local pack |
|---|---|---|
| Austin | Briggle & Polan PLLC; The Doan Law Firm | Briggle & Polan |
| New York | *(0 text ads in all 3 runs)* | Cohen & Cohen |
| Los Angeles | Vardanyan Law Firm | Attorney Big Al; Sweet James |

**Overlap between metros: zero.** Local-intent verticals are entirely different auctions per metro. Note NYC returned no text ads at all across 3 runs yet still exposed a paid local-pack advertiser — reinforcing §1.3.

---

## 5. Organic context around the ads

All of these arrive in the **same response AdWatch already pays for**. Observed presence across 159 `engine=google` responses.

| Key | Fields | Use for AdWatch |
|---|---|---|
| **`ai_overview`** | Two shapes: **inline** `{text_blocks[], references[]}` (49%) or **deferred** `{page_token, serpapi_link}` (4%); absent 47%. `references[].{index,title,link,source,snippet,thumbnail,source_icon}`; `text_blocks[].{type,snippet,snippet_highlighted_words[],reference_indexes[],list[],video,top_stories[]}` | **Presence is highly stable** — 9/9 identical no_cache runs all had it while ads swung 0→6. A far better change signal than ads. 96% of the time content is inline and **free**; only 4% needs a 2nd search |
| **`organic_results[]`** | `position`, `title`, `link`, `redirect_link`, `displayed_link`, `snippet`, `snippet_highlighted_words[]`, `source`, `favicon`, `about_this_result.source.{description,icon,source_info_link}`, `about_this_result.{regions[],languages[]}` | Share-of-page; detect a competitor holding both a paid and organic slot |
| **`related_searches[]`** | `query`, `link`, `serpapi_link`, `block_position` | Keyword expansion — free candidate keywords |
| **`related_questions[]`** | `question`, `snippet`, `title`, `link`, `displayed_link`, `source_logo`, `list[]`, `table[][]`, `date`, `next_page_token`, `serpapi_link`, `serpapi_ai_overview_link` | Intent/messaging themes |
| **`search_information`** | `total_results`, `query_displayed`, `organic_results_state`, `time_taken_displayed`, `results_for`, `spelling_fix` | **`total_results` is unreliable** — same query returned 142, 161, 3,600 and 195,000,000 depending on filters. Do **not** trend it |
| `local_results` | `places[]` (§1.3), `more_locations_link` | Paid local pack |
| `local_map` | `image`, `link`, `gps_coordinates` | Geo confirmation |
| `refine_this_search[]`, `filters[]` | `query`, `link`, `serpapi_link`, `thumbnail`; `filters[].parameters.uds` | Google's own query refinements |
| `things_to_know`, `perspectives`, `discussions_and_forums`, `inline_videos`, `inline_images` | 42 / 9 / 6 / 13 / 5 distinct paths | SERP-composition change detection |
| `serpapi_pagination` / `pagination` | `current`, `next`, `next_link`, `other_pages{}` | Not useful — ads are page-1 only |

**AI Overview detectability and stability: excellent.** Presence was 100% consistent across 9 identical uncached calls (`text_blocks` count wobbled 6→4 once; `references` was 12 every time). Contrast with ads at 0–6. **[OBS]**

**Does AI Overview displace ads?** Across 80 responses: P(ads>0 | AIO present) = **38.3%** vs P(ads>0 | AIO absent) = **18.2%**. AIO presence *correlates with more ads*, not fewer. **[INFERRED — confounded]**: commercial queries attract both; this is not evidence of causation, and it does not support an "AIO is eating our ads" narrative.

---

## 6. DOCUMENTED vs OBSERVED

| Claim | Doc | Live (159 responses / 113 ads) |
|---|---|---|
| `ads[].block_position` always present | https://serpapi.com/google-ads | **Missing on 9.7% of ads.** Normalise to null, don't assume top/bottom |
| `block_position` can be `middle` / `right` | Doc prose lists top/bottom/middle/right | Only **`top`** and **`bottom`** observed |
| `ads[].sitelinks[].snippets` standard | Doc sample shows it | Only **9.4%** of sitelinks |
| `ads[]` carries `price`/`extracted_price`/`rating`/`reviews` (hotel ads) | Doc sample "hotels in dusseldorf" | **Never observed.** My own `hotels in dusseldorf` (gl=de) run returned 1 ad with none of these |
| `ads[].vehicles_for_sale[]` | Doc sample "2019 suvs for sale" | **Never observed** — my `2019 suvs for sale` run returned 0 ads |
| `ads[].links[]` (mobile location ext.) | Doc mobile sample | **Never observed** |
| `ads[].phone` | Doc prose only, no sample | **Never observed** |
| `shopping_results` on `engine=google` | https://serpapi.com/inline-shopping | **Never observed.** `immersive_products` returns instead |
| `local_ads` block | https://serpapi.com/local-ads | **Never observed** across 6 home-services queries |
| `local_results.places[].ad` | **Undocumented** | **Observed** — the paid local-pack flag |
| `ads[].extensions[]` = "additional callout text" | Doc | Only "N visits in past month" traffic annotations |

**[INFERRED]** The docs' richer ad shapes (hotel price ads, vehicle ads, mobile location links) are real SerpApi parsers built from 2023–2025 samples, but those Google ad formats either no longer serve to datacenter IPs or now route through vertical engines (`google_hotels`, `google_immersive_product`). Build defensively: treat every `ads[]` field except `position`/`title`/`link`/`displayed_link`/`tracking_link` as optional.

---

## 7. Untapped opportunities, ranked by value-per-search

### Tier 0 — ZERO extra searches (already in responses AdWatch pays for and discards)

AdWatch reads only `ads`. Everything below is in the same JSON body.

| # | `event_kind` | Trigger | Why a paid-search team cares | Cost |
|---|---|---|---|---|
| 1 | `ad_sitelink_set_changed` | Set-diff of `ads[].sitelinks[].title` per advertiser | The single richest creative signal available. New sitelinks = new landing pages, new promos, campaign restructure. 69% ad coverage. Backed by `raw/sweep_vpn.json` (NordVPN 4 sitelinks incl. "NordVPN deal: buy for less now") | **0** |
| 2 | `ad_copy_changed` | `ads[].description` or `title` differs for a stable advertiser | Callouts and structured snippets are folded into `description` — this is the *only* way to catch them. Messaging/offer pivots | **0** |
| 3 | `paid_local_competitor_changed` | `local_results.places[].ad == true` set-diff | Undocumented. Only source of competitor **phone**, **address**, **rating**, **hours**, **years_in_business**. Present on mobile/tablet where `ads` is empty. Backed by `raw/dev_pilawyer_mobile.json` | **0** |
| 4 | `ai_overview_appeared` / `_disappeared` | `ai_overview` key presence flips | 100% stable across 9 runs vs ads' 0–6 swing. AIO onset restructures the whole SERP and is a genuine organic-traffic threat. Content is inline & free 96% of the time | **0** |
| 5 | `ai_overview_citation_changed` | Set-diff `ai_overview.references[].link` domains | Who Google's AI cites for your money keyword. Direct content/PR target list | **0** |
| 6 | `serp_composition_changed` | Presence-diff of top-level keys (`immersive_products`, `local_results`, `things_to_know`, `perspectives`, `discussions_and_forums`, `inline_videos`) | SERP feature shifts change CTR economics on every position | **0** |
| 7 | `share_of_page_changed` | Ratio of paid slots to `organic_results` length; competitor in both | Real estate share — the metric a paid team actually reports upward | **0** |
| 8 | `product_price_moved` | `immersive_products[].extracted_price` / `extracted_original_price` per `source` | Live competitor pricing and discounting for retail keywords | **0** |
| 9 | `related_searches_changed` | `related_searches[].query` set-diff | Free keyword-expansion candidates straight from Google | **0** |
| 10 | `ad_traffic_tier_changed` | `ads[].extensions[]` "N visits in past month" band shifts (10K→100K→1M) | The one thing `extensions` is good for: a coarse advertiser-scale proxy | **0** |
| 11 | `seller_rating_changed` | `ads[].reviews` delta | Seller-rating extension movement (7% of ads) | **0** |

### Tier 1 — costs extra searches, high value

| # | `event_kind` | Trigger | Why | Cost |
|---|---|---|---|---|
| 12 | `advertiser_presence_rate_changed` | Track per-advertiser **presence rate over N samples**, alert on a rate shift, not on a single absence | **This is the fix for the volatility problem.** Turns a 44%-false-negative signal into a real one | **N× per keyword** (N≥5) |
| 13 | `geo_advertiser_delta` | Same keyword across metro `location` values | Metro advertiser sets are **disjoint**. Reveals geo-targeted competitors invisible nationally | +1 per metro |
| 14 | `mobile_paid_local_delta` | Same keyword `device=mobile` for the paid local pack | Mobile has 0 text ads but real paid local placements | +1 per keyword |

### Tier 2 — low value / avoid

| Action | Verdict |
|---|---|
| Paging with `start=10+` for more ads | **Zero ads on page 2.** Pure waste |
| `num=100` for a bigger page | No effect on organic count or ad blocks |
| Following `immersive_product_page_token` | +1 search per product — only for deep price work |
| Trending `search_information.total_results` | Varies 142 → 195,000,000 for the same query. Meaningless |
| Deferred `ai_overview.page_token` fetch | Only 4% of responses; skip unless AIO text is core |

---

## 8. Concrete recommendations for AdWatch

1. **Set `no_cache=true` on every scheduled collection.** Otherwise you may diff a cached response and detect nothing for up to an hour. (Cached calls are free — useful for dev/replay, fatal for production diffing.)
2. **Always send a `location`.** Six commercial queries with no `location` returned **zero ads**. This is likely the single biggest cause of "no ads found" in AdWatch today.
3. **Resolve `location` through the free `/locations.json` API and store `canonical_name` or `id`.** Freeform strings silently resolve to the most popular match — City vs DMA are different auctions.
4. **Stop treating one search as one observation.** Sample N≥5 per keyword per run and model **presence rate**. At N=1 you miss 80% of advertisers and see nothing at all 44% of the time. At N=5, P(seeing zero ads) drops to 0%.
5. **Never emit `advertiser_disappeared` from a single sample.** It will fire constantly and destroy user trust in the brief.
6. **Use `displayed_link`, not `link`, for `target_domain`.** `link` is a Google redirect roughly half the time.
7. **Make `block_position` nullable** — missing on 9.7% of ads. And `position` restarts per block, so key ads on `(block_position, position)` or on advertiser domain.
8. **Add `device=mobile` collection for local verticals** to capture `local_results.places[].ad` — the only source of competitor phone numbers.
9. **Widen the parser to `immersive_products`, not `shopping_results`.** The documented key does not appear in live `engine=google` traffic.
10. **Ship the Tier-0 events first.** They need no additional quota — only a wider read of JSON already being paid for and thrown away.

---

## 9. Source URLs

- https://serpapi.com/search-api — parameters (`location`, `uule`, `lat`/`lon`/`radius`, `device`, `no_cache`, `gl`, `hl`, `cr`, `lr`, `tbs`, `safe`, `nfpr`, `filter`, `start`, `json_restrictor`)
- https://serpapi.com/google-ads — `ads[]`
- https://serpapi.com/inline-shopping — `shopping_results` (stale for `engine=google`)
- https://serpapi.com/immersive-result — `immersive_products`
- https://serpapi.com/local-ads — `local_ads`
- https://serpapi.com/local-pack , https://serpapi.com/local-results — local pack (`ad` flag undocumented)
- https://serpapi.com/ai-overview — `ai_overview`
- https://serpapi.com/organic-results , https://serpapi.com/related-searches , https://serpapi.com/related-questions
- https://serpapi.com/locations-api — free Locations API
- https://serpapi.com/advanced-google-query-parameters — `as_*` params
- https://serpapi.com/json-restrictor , https://serpapi.com/google-domains , https://serpapi.com/google-countries
- `engine=google_ads` (separate API): https://serpapi.com/google-ads-api , https://serpapi.com/google-ads-shopping-results , https://serpapi.com/google-ads-local-results

## 10. Reproduction

Raw responses in `scratchpad/raw/`: `base_*` (no location), `loc_*`/`geo_*` (location matrix), `sweep_*` (16 verticals), `dev_*` (device matrix), `nc_*` (uncached volatility, 15), `ctry_*` (country), `lsa_*` (home services), `shop_*`/`rich_*` (commerce), `num*`/`start10_*`, `p_*` (parameter tests), `uule_austin`.

API key stripped from all files; `grep -rl "$KEY" .` returns zero matches.
