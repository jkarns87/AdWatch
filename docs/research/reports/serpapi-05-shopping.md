# SerpApi Shopping & Product Engines — AdWatch Research Report

**Date:** 2026-09-03
**Method:** Live SerpApi documentation (fetched, not recalled) + **40 live API calls** against a real key.
**Budget:** 40 of 150 searches spent. Raw responses in `./raw/` (`api_key` stripped from every file; key-leak grep clean).
**Account observed:** `plan_id: free`, `searches_per_month: 250`, `extra_credits: 13,907`. Note the account is **shared with other agents running in parallel**, so the account-level counter delta (~380) is not attributable to this task; the 40 figure is my own call manifest (`./mine.txt`).

---

## 0. Headline answers

| # | Question | Answer |
|---|---|---|
| 4 | Can AdWatch detect competitor product ads with **zero** extra searches? | **Yes — for price and merchant presence.** The `engine=google` response already carries `immersive_products` with merchant + price + discount. **But** that block carries no `aclk` tracking link, so it proves *merchandising presence*, not *paid placement*. |
| 2 | `google_product`? | **Dead.** Returns an error. Replaced by `google_immersive_product`. |
| 3 | Price history? | **Does not exist.** Only `price_range` (current min–max across sellers). |
| — | Biggest risk found | **Google serves two disjoint SERP variants for the same query.** A naive diff produces ~100% false-positive change events. Mitigation in §8. |

---

## 1. `google_shopping` engine

**Doc:** https://serpapi.com/google-shopping-api
**Endpoint:** `https://serpapi.com/search?engine=google_shopping`
**Uptime published on page:** 99.470%

### 1.1 Parameter surface (documented, all verified live where tested)

| Param | Req | Notes |
|---|---|---|
| `q` | Required | Optional if `shoprs` supplied |
| `location` | Optional | City-level recommended; mutually exclusive with `uule` |
| `uule` | Optional | Google-encoded location; needs matching `gl` for coordinate form |
| `google_domain` | Optional | Default `google.com` |
| `gl` | Optional | Two-letter country. **Verified:** `gl=uk` returns `£` prices |
| `hl` | Optional | Two-letter language |
| `shoprs` | Optional | Filter token. Join multiple with `\|\|`. **Verified live** |
| `min_price` / `max_price` | Optional | Overrides price filter embedded in `shoprs`. **Verified live** |
| `sort_by` | Optional | `1` = price low→high, `2` = high→low. **Verified live** |
| `free_shipping` | Optional | Boolean |
| `on_sale` | Optional | Boolean. **Verified live** |
| `small_business` | Optional | Boolean |
| `start` | Optional | **Explicitly ignored.** Doc: *"Google Shopping's current layout does not support offset pagination: the `start` parameter is ignored and every request returns the first page of results (around 40 items). The `num` parameter is still accepted and forwarded to Google, but the current layout returns a fixed page size."* |
| `device` | Optional | `desktop` (default) / `tablet` / `mobile` |
| `no_cache` | Optional | Bypass 1h cache. **Cached searches are free and don't count against quota** |
| `async`, `zero_trace`, `output`, `json_restrictor` | Optional | `zero_trace` is Enterprise-only |

**Pagination is effectively dead.** One call = ~40 results, full stop. This caps per-keyword depth and is a hard constraint on AdWatch's design.

### 1.2 Response shape — OBSERVED field inventory

Union across 3 live queries (espresso machine / running shoes / standing desk), 120 `shopping_results` items:

| Field | Presence | Carries |
|---|---|---|
| `position` | 100% | Rank |
| `title` | 100% | Product name |
| `product_id` | 100% | **Not stable across runs — see §8** |
| `product_link` | 100% | Google Shopping URL |
| `immersive_product_page_token` | 100% | **Drill-down token** |
| `serpapi_immersive_product_api` | 100% | Pre-built drill-down URL |
| `source` | 100% | **Merchant.** e.g. `Target`, `eBay - weshipnow`, `Walmart - MOEFO` |
| `source_icon` | 100% | Merchant logo |
| `price` | 100% | **String with currency symbol** (`"$243.99"`, `"£209.00"`) |
| `extracted_price` | 100% | **Numeric, currency-less** |
| `thumbnail` | 100% | Image |
| `serpapi_thumbnail` | 92% | Proxied image |
| `rating` / `reviews` | 78% | Float / int |
| `delivery` | 63% | **String only** — `"Free delivery"`, `"Free delivery on $75+"`. No numeric extraction |
| `extensions[]` | ~67% | Superset of `tag` + `"Nearby, 11 mi"` |
| `old_price` / `extracted_old_price` | 38% | Pre-discount price |
| `multiple_sources` | 39% | Bool — product sold by >1 merchant |
| `tag` | 35% | **Promotion.** `"5% OFF"`, `"62% OFF"`, `"LOW PRICE"` |
| `snippet` | 29% | Review digest, e.g. `"Quality espresso drinks (480 user reviews)"` |
| `second_hand_condition` | <1% | Condition |

**Field-to-need mapping requested:**

| Need | Field | Gap |
|---|---|---|
| Merchant | `source` | Marketplace sellers appear as `"eBay - <seller>"` — needs normalisation |
| Price | `extracted_price` (num), `price` (string) | — |
| **Currency** | **No field.** Must parse the symbol out of `price` | **Real gap.** `extracted_price` is bare |
| Delivery cost | `delivery` string | **No numeric field.** Must regex |
| Promotion/coupon | `tag`, `extensions[]` | Percentage-off only; no coupon codes at this level |
| Rating | `rating`, `reviews` | — |
| Product id | `product_id` | **Unstable — see §8** |

### 1.3 Other top-level keys (OBSERVED)

- `categorized_shopping_results[]` — 5 curated buckets × 5–8 items (`Prosumer Espresso Machines`, `Budget-Friendly…`, `In stores nearby`, `Deals on…`). Same item schema. **Far more stable than the flat array (§8).**
- `filters[]` — `{type, input_type, options[{text, shoprs, serpapi_link}]}`. Live types observed for "espresso machine": *(unnamed refine)*, Features, Product Rating, Automation, Price, Finish, Water Tank Size, **Stores**, Brand, Free shipping, Carousel Filters.
- `search_information` — `query_displayed`, `shopping_results_state`.
- `inline_shopping_results` — documented, **not present in any live response**.

### 1.4 The `Stores` filter is the most valuable undocumented-for-this-purpose feature

`filters[type="Stores"].options[]` yields a `shoprs` token per merchant.

**Verified:** passing Target's token returned **40/40 results from Target only**, across 3 independent runs. This is the clean primitive for per-competitor monitoring.

Caveat: the store list is query-derived and short (4 options for "espresso machine": Williams-Sonoma, Target, casabrews, Walmart). A watchlist competitor absent from that list cannot be filtered this way on that keyword.

### 1.5 Filter behaviour — MEASURED

| Call | n | Price range | Result |
|---|---|---|---|
| baseline | 40 | $20.32–$14,225 | 21 merchants |
| `sort_by=1` | 40 | $12.00–$118.99, ascending | **Cheapest-first works.** 1 search = cheapest sellers |
| `shoprs`=Target | 40 | $64.99–$1,799.99 | **1 merchant only** |
| `on_sale=true` | 40 | — | **40/40 carry a `tag`** |
| `min_price=100&max_price=300` | 40 | $118.99–$299.99 | Bounds respected |

---

## 2. Product-level engines

### 2.1 `google_product` is SHUT DOWN — confirmed live

**Doc:** https://serpapi.com/google-product-api

> *"Google has shutdown the Google Product service. As a result of this, our Google Product API will now return an error indicating that the Google Product service has been shutdown. The Google Immersive Product API contains the same information that was previously found in the Google Product service and should be used instead."*

**Live call** `engine=google_product&product_id=16279558464628229780` returned exactly:

```json
{ "error": "The Google Product service is no longer offered by Google." }
```

Any AdWatch design referencing `google_product`, `sellers_results.online_sellers`, `base_price`/`total_price`, or `offer_id` is dead code. That schema is still on the doc page but is unreachable.

### 2.2 `google_immersive_product` — the live replacement

**Docs:** https://serpapi.com/google-immersive-product-api and https://serpapi.com/google-immersive-product-stores
**Uptime published:** 99.774%

| Param | Req | Notes |
|---|---|---|
| `page_token` | Required | From `immersive_product_page_token` / `serpapi_immersive_product_api` on any shopping or search result |
| `more_stores` | Optional | `1`/`true`. Default returns 3–5 stores; enabled returns **up to 13** |
| `next_page_token` | Optional | From `stores_next_page_token` |

**There is no `product_id` parameter.** Entry is *only* via a token obtained from a prior search. That is an architectural constraint: AdWatch cannot address a product directly by a stable id; it must re-discover the token each run.

#### Measured seller tables (`more_stores=true`, 1 search each)

| Product | `price_range` | Stores |
|---|---|---|
| Nike Women's Run Swift 3 | `$68-$85` | **13** |
| Brooks Women's Glycerin 23 | `$175-$175` | **13** |
| Brooks Men's Adrenaline GTS 25 | `$155-$155` | **13** |
| Realspace Magellan Standing Desk | `$400-$600` | 8 |
| Mainstays Electric Standing Desk | `$134-$149` | 2 |
| Rocket Espresso Appartamento | `£1,340-£1,350` | 2 |

Sample (Nike Run Swift 3) — this is the full merchant list for one product, for **one search**:

```
Famous Footwear    $84.99  total $94.94  ship +$9.95   tag "Nearby"
DSW                $84.96  total $92.91  ship +$7.95   tag "Best price"
Rack Room Shoes    $84.99  total $84.99  ship Free
Kohl's             $85.00  total $85.00  ship Free
JCPenney           $85.00  total $85.00  ship Free
Academy Sports     $69.99  total $69.99  ship Free     discount "17% off"
Shoe Carnival      $85.00  total $94.99  ship +$9.99
Shoe Station       $85.00  total $94.99  ship +$9.99
eBay - bambo_group $79.95  total $79.95  ship Free
Lyst               $84.96  total $93.91  ship +$8.95
Belk               $85.00  total $96.95  ship +$11.95
shoeshowmega.com   $79.99  total $87.94  ship +$7.95
Uber Eats          $84.96  total $99.96  ship +$15.00
```

**`stores[]` fields (OBSERVED):** `name`, `logo`, `link`, `title`, `rating`, `reviews`, `payment_methods`, `tag` (`"Best price"`, `"Nearby"`), `details_and_offers[]`, `discount`, `price`/`extracted_price`, `original_price`/`extracted_original_price`, `shipping`/`shipping_extracted`, `total`/`extracted_total`. Documented `estimated_tax`/`extracted_estimated_tax` was **absent in all six live drill-downs** — treat as optional.

**`product_results` also returns:** `thumbnails[]`, `title`, `brand`, `rating`, `reviews`, `critic_ratings[]`, `price_range`, `about_the_product{}`, `ratings[]`, `reviews_images[]`, `user_reviews[]`, `more_options[]`, `variants[]`, `top_insights{}`, `videos[]`, `discussions_and_forums[]`, `stores_next_page_token`.

**Cost per product: 1 search** for up to 13 sellers. `more_stores=true` costs the same as without — always set it.

**Pagination beyond 13 does not work in practice.** A live call with a returned `stores_next_page_token` came back with **0 stores**. Budget 13 sellers/product, one search.

**Currency bug worth logging:** the Rocket Espresso drill-down was reached from a `gl=us` shopping result whose `price` was `$2,363.00`, yet `price_range` returned **`£1,340-£1,350`**. `price_range` cannot be trusted for currency; derive min/max from `stores[].extracted_price` instead.

---

## 3. Price history / offers

**There is no price-history endpoint on any SerpApi Google engine.** Nothing in the live docs or live responses exposes a time series.

What *does* exist:

| Surface | Field | What it gives |
|---|---|---|
| `google_immersive_product` | `price_range` | Current min–max across sellers. **Not historical.** Currency-unreliable |
| `google_immersive_product` | `stores[]` | Cross-merchant comparison table, one call — the real "price comparison in a single call" |
| `google_shopping` | `old_price` / `extracted_old_price` | Merchant's own strike-through anchor. Present on 38% of results |
| `google_shopping` | `tag` | `"62% OFF"` — implies a prior price |
| `google` → `product_result` | `typical_price` | Documented as `"Typically $289–$470"`. **Not observed live** (see §4.3) |

**Conclusion:** AdWatch must build its own price history by persisting each run's observations. That is exactly what its diff engine already does — so this is a storage question, not an API gap. `old_price` gives a same-run discount signal without needing history at all.

---

## 4. Shopping ads inside the `google` engine — THE KEY QUESTION

### 4.1 Measured answer

**Yes. AdWatch can detect competitor product presence and pricing with ZERO extra searches**, on keywords it already queries — but with one honest qualification about the word "ads".

Ten live `engine=google` calls. The block that appears is **`immersive_products`**, at the top level of the ordinary search response:

| Query | `immersive_products` | `shopping_results` | `ads` |
|---|---|---|---|
| espresso machine | **60** | absent | absent |
| running shoes | **50** | absent | absent |
| standing desk | **16** | absent | absent |
| buy espresso machine online | **60** | absent | absent |
| jeans buy | **60** | absent | absent |
| gaming mouse | **50** | absent | absent |
| espresso machine (mobile) | **30** | absent | absent |
| dyson v8 | **60** | absent | absent |
| crm software | absent | absent | absent |
| auto insurance quotes | absent | absent | **6** |

### 4.2 Exact JSON keys and fields — `immersive_products[]`

Complete observed key set across 126 items:

| Field | Presence | Value |
|---|---|---|
| `source` | **100%** | **Merchant name** — `"Target"`, `"upliftdesk.com"`, `"DICK'S Sporting Goods"` |
| `price` | **100%** | `"$79.99"` (string, currency symbol) |
| `extracted_price` | **100%** | `79.99` (numeric) |
| `title` | **100%** | Product name |
| `category` | **100%** | Block name — `"Popular products"`, `"In stores nearby"`, `"More products"`, `"Deals on Running Shoes"` |
| `thumbnail`, `source_logo` | 100% | Images |
| `immersive_product_page_token` | **100%** | **Drill-down token** |
| `serpapi_link` | 100% | Pre-built `google_immersive_product` URL |
| `rating` / `reviews` | 96% | Float / int |
| `location` | 80% | `"Nearby, 11 mi"` |
| `delivery` | 48% | `"Free delivery"` |
| `original_price` / `extracted_original_price` | **22%** | **Pre-discount anchor** |
| `extensions[]` | **21%** | **`["20% OFF"]`** |

Merchant coverage per single free call: **espresso machine → 12 distinct merchants; running shoes → 18; standing desk → 9.**

### 4.3 What is NOT there — the honest qualification

`immersive_products` has **no `link` and no `tracking_link`**. Contrast with blocks that are definitively paid:

- `ads[]` → has `tracking_link` containing `google.com/aclk?` ✅ confirmed paid
- `local_results.places[].ad: true` → `links.website` contains `aclk?` ✅ confirmed paid
- `immersive_products[]` → **no link of any kind, no `aclk`, no "Sponsored" marker**

So the precise claim AdWatch can make is: **"competitor X is merchandising product Y at price Z on keyword K"** — obtained free. It cannot claim "competitor X is running a *paid* shopping ad" from this block alone, because SerpApi does not label these as sponsored.

For most paid-search use cases this distinction is academic — Google's product grid is fed by Merchant Center and is overwhelmingly advertiser-supplied inventory — but the brief asked for precision, so: **presence and price = free and reliable; "is it a paid PLA" = not determinable from this block.**

### 4.4 Documented-but-absent blocks

The following are documented under the Google Search API but **did not appear in any of 10 live product-query responses**. Treat the doc pages as stale:

- **`shopping_results`** (https://serpapi.com/inline-shopping) — doc examples date to search IDs from May 2023. Documented fields `block_position`, `second_hand_condition`, `shipping`, `old_price`, `reviews_original`.
- **`product_result`** (https://serpapi.com/product-result) — the right-hand panel with `pricing[]` (per-merchant `name`/`price`/`original_price`/`tag`/`buying_options[]`) and **`typical_price`**. Would have been the best free price-comparison surface; not served. Tested with the doc's own example query (`dyson v8`) — returned `immersive_products` instead.
- **`product_sites`** (https://serpapi.com/product-sites) — comparison-site listings.

### 4.5 Verdict

> A single `engine=google` call AdWatch **already makes** yields 16–60 product cards, 9–18 distinct merchants, with price, discount anchor, promo tag, rating and a drill-down token — **at no incremental quota cost**. This is the highest value-per-search finding in this report.

---

## 5. Local: `google_local`, `google_maps`, Local Services Ads

### 5.1 Paid local pack inside `engine=google` — free

**Doc:** https://serpapi.com/local-results
**Measured:** `q=personal injury lawyer`, Austin TX.

`local_results.places[]` carries an explicit **`ad`** boolean:

```
ad=True   pos=1  Briggle & Polan – Austin Personal Injury  place_id=4836824054794356021  provider_id=/g/1td4_7dn  15+ years  (512) 865-6195
ad=None   pos=2  McMinn Law Firm                            place_id=17567042611799248957 provider_id=/g/1tcy98wb
ad=None   pos=3  Treviño Law, PLLC                          place_id=11804725976415936467
```

`ad: true` entries have `links.website` containing `google.com/aclk?` — **confirmed paid**. Also in this response: `ads[]` with 3 text ads (`block_position` top/bottom).

**Advertiser identity:** `title`, `place_id` (Google CID), `provider_id` (`/g/…` Knowledge Graph MID), `phone`, `address`, `gps_coordinates`, `years_in_business`.

`place_id` and `provider_id` were **stable** across the `google` and `google_local` engines for the same businesses — unlike shopping `product_id`, these are usable diff keys.

### 5.2 `google_local` — `ads_results`

**Doc:** https://serpapi.com/google-local-ads · `engine=google_local`
Documented block `ads_results[]`: `position`, `ad_title`, `displayed_link`, `title`, `type`, `rating`, `reviews`, `price`, `address`, `hours`, `place_id`, `place_id_search`, `lsig`, `thumbnail`, `gps_coordinates`, `service_options{}`.

**Live `engine=google_local&q=emergency plumber` returned only `local_map` + `local_results` (20 places) — no `ads_results`.** The block is real but not always served.

### 5.3 `google_local_services` — Local Services Ads

**Doc:** https://serpapi.com/google-local-services-api · Uptime 100%

| Param | Req | Notes |
|---|---|---|
| `q` | Required | Service term |
| `data_cid` | **Required** | Google CID of the place. **`place_id` was discontinued** — use `data_cid`. City/district level recommended |
| `hl` | Optional | Language |
| `job_type` | Optional | Subcategory, e.g. `restore_power` |
| `cid` + `bid` + `pid` | Optional | All three required together to fetch one business's detail page |

> Doc caveat: *"Google Local Services API returns empty results for places outside of the USA."*

**Live:** `q=plumber&data_cid=6745062158417646970` (Austin) → **20 `local_ads[]` for 1 search.**

Observed fields: `title`, `link`, `rating`, `reviews`, `phone`, `type`, `service_area`, `years_in_business`, `thumbnail`, `hours{currently, week[]}`, **`cid`**, **`bid`**, **`pid`**, `serpapi_link`.

```
Abacus Plumbing                4.8  6,070 rev  23 yrs  cid=689374240   bid=2555661784
Fox Service Company - Plumbing 4.8  5,570 rev  56 yrs  cid=317080543   bid=2516815328
Radiant Plumbing, AC & Elec.   4.8 17,743 rev  27 yrs  cid=6779199783  bid=9140608052
Roto-Rooter Plumbing           4.8  3,439 rev  91 yrs  cid=264203903   bid=2509568154
```

Every entry in `local_ads` is by definition a paid LSA advertiser — **no ambiguity, unlike `immersive_products`.**

Documented `badge: "GOOGLE GUARANTEED"` and `bookings_nearby` were **absent from all 20 live results.** Optional fields.

**Advertiser identity for change events:** `cid` (stable business id) + `bid` + `pid`. Use `cid` as the diff key.

### 5.4 Local change-events

| `event_kind` | Trigger | Cost |
|---|---|---|
| `local_ad_entered` / `local_ad_exited` | `local_results.places[].ad` flips true/false for a `place_id` | **0** (piggyback) |
| `lsa_competitor_entered` | New `cid` in `local_ads[]` | 1/service/city |
| `lsa_rank_shift` | Position change for a `cid` | 1/service/city |
| `lsa_review_velocity` | `reviews` delta for a `cid` | 1/service/city |
| `lsa_rating_drop` | `rating` falls | 1/service/city |

---

## 6. Cost model — 10 keywords × 5 competitors

### Measured per-call costs (all engines = 1 search)

| Call | Cost | Yield (measured) |
|---|---|---|
| `engine=google` (already made by AdWatch) | **0 incremental** | 16–60 products, 9–18 merchants, price + discount + promo |
| `engine=google_shopping` | 1 | 40 results + ~26 categorized + filters |
| `engine=google_shopping` + `shoprs` Stores | 1 | 40 results, **1 merchant only** |
| `engine=google_immersive_product` + `more_stores` | 1 | up to **13 sellers** for one product |
| `engine=google_local_services` | 1 | **20** LSA advertisers |
| Repeat identical query within 1h | **0 — free, cached** | Verified: identical `search_metadata.id` |

### Tiered arithmetic (10 keywords, 5 competitors, per run)

**Tier 0 — Piggyback. 0 searches.**
`immersive_products` on the 10 `engine=google` calls AdWatch already makes.
`10 × 0 = 0`
Yield: 10 keywords × ~12 merchants ≈ 120 merchant-price observations/run. Covers all 5 competitors wherever they merchandise.

**Tier 1 — Shopping breadth. +10 searches.**
`10 keywords × 1 google_shopping = 10`
Adds `product_id`, `tag`, `delivery`, `old_price`, 40 results + 26 categorized per keyword.

**Tier 2 — Product seller tables. +30 searches.**
Drill the top 3 products per keyword: `10 × 3 × 1 = 30`
Each yields up to 13 sellers with total landed price. This is the only way to see **all 5 competitors' prices for the same SKU**.

**Tier 3 — Per-competitor precision. +up to 50 searches.**
`10 keywords × 5 competitors × 1 = 50` using the `Stores` `shoprs` filter.
**In practice far fewer** — only ~4 store options are offered per keyword, so a competitor not in that list is unfilterable. Realistic: `10 × ~2 available competitors = ~20`.

### Recommended configuration

| Config | Searches/run | ×30 daily runs | Plan needed |
|---|---|---|---|
| Tier 0 only | **0** | **0** | none — free |
| Tier 0+1 | **10** | 300/mo | Starter $25 |
| Tier 0+1+2 | **40** | 1,200/mo | Developer $75 (5,000) |
| Tier 0+1+2+3 | **~60–90** | 1,800–2,700/mo | Developer $75 |

Adding shopping intelligence to a 10-keyword / 5-competitor watchlist costs **0 searches at minimum and 40/run for the recommended tier** — 1,200/month, comfortably inside the $75 Developer plan.

**Free lever:** the 1-hour cache is free and returns an identical `search_metadata.id`. Runs more frequent than hourly cost nothing extra unless `no_cache=true` is set.

### Plan tiers (https://serpapi.com/pricing)

Free $0/250 · Starter $25/1,000 · Developer $75/5,000 · Production $150/15,000 · Big Data $275/30,000 · Searcher $725/100k · Volume $1,475/250k · Infrastructure $2,750/500k · Cloud $3,750+/1M+.

**No engine is gated to a tier** — the pricing page states no per-engine restriction, and this Free-plan key successfully called `google_shopping`, `google_immersive_product`, `google_shopping_light` and `google_local_services`. Gated *features*: `zero_trace` (Cloud 1M+), US Legal Shield (Production+), priority support (Cloud 1M+). Speed modes multiply cost ×1/×2/×4.

---

## 7. Untapped opportunities — proposed change events

Ranked by value-per-search.

| Rank | `event_kind` | Trigger | Why a paid-search team cares | Extra searches |
|---|---|---|---|---|
| 1 | `competitor_price_cut` | `extracted_price` for a matched (merchant, title) falls ≥ threshold | Strongest actionable signal in the set. A rival undercutting you on a head term moves Shopping impression share within hours. Directly triggers bid or price response | **0** (Tier 0) |
| 2 | `promotion_appeared` | `extensions[]`/`tag` gains `"N% OFF"`, or `original_price` appears where absent | Promo start = a campaign launch. Explains a sudden CTR/CPC swing without waiting for reporting | **0** (Tier 0) |
| 3 | `competitor_entered_shopping` | New `source` appears in `immersive_products` for a watched keyword | A competitor starting product ads on your term is a budget-shift event — the earliest possible warning | **0** (Tier 0) |
| 4 | `competitor_exited_shopping` | Watched `source` absent for **N consecutive runs** | Rival paused/lost feed — an opening to raise bids. **N≥3 required, see §8** | **0** (Tier 0) |
| 5 | `local_ad_entered` | `local_results.places[].ad` flips to `true` | Service-business equivalent of #3. Free | **0** (Tier 0) |
| 6 | `undercut_alert` | Customer's own price no longer the min of `stores[].extracted_total` | Answers "am I still cheapest, landed?" — the question e-commerce teams actually ask. Uses `total`, not `price` | 1/product |
| 7 | `new_merchant_on_product` | New `name` in `stores[]` for a tracked product | New seller on your exact SKU — margin threat, sometimes an unauthorised reseller (MAP violation) | 1/product |
| 8 | `price_range_widened` | `stores[]` min/max spread grows | Signals a price war starting before any single cut looks significant | 1/product (shared with #6/#7) |
| 9 | `cheapest_seller_changed` | Top result of `sort_by=1` changes merchant | 1 search gives the whole "who is cheapest now" answer for a keyword | 1/keyword |
| 10 | `sale_breadth_shift` | Count of `on_sale=true` results changes materially | Category-wide promo intensity — is everyone discounting, or just you? | 1/keyword |
| 11 | `competitor_catalog_change` | Result count/titles shift under a `Stores` `shoprs` filter | Per-competitor assortment tracking. Precise but limited by short store list | 1/keyword/competitor |
| 12 | `lsa_competitor_entered` | New `cid` in `local_ads[]` | Service verticals — new LSA advertiser in your city | 1/service/city |
| 13 | `product_out_of_stock` | `details_and_offers[]` loses `"In stock online"` | Rival stockout = opportunity to bid up. **Weakest signal — high noise, see §8** | 1/product |

**Events 1–5 are free.** Build those first: they cover competitor price cut, promotion appearing, a competitor starting shopping ads, and the local equivalent — four of the five the brief asked for — at zero quota cost.

The fifth requested event (`product_out_of_stock`) is ranked last deliberately: it requires a paid drill-down *and* is the least reliable, because stock strings sit in a free-text array and product membership churns (§8).

---

## 8. ⚠ CRITICAL: measured result instability

This did not come from the docs. It is the single biggest implementation risk found, and it invalidates a naive diff.

### 8.1 Google serves two disjoint SERP variants for the same query

Five identical `google_shopping` calls (`q=espresso machine`, `location=Austin, Texas`, `no_cache=true`), minutes apart:

| Run | Median price | Max | Merchants | Character |
|---|---|---|---|---|
| gs_espresso | $3,380 | $14,225 | 21 | prosumer — Clive Coffee, Pro Coffee Gear, eBay |
| gs_vol_D | $2,128 | $14,117 | 21 | prosumer |
| gs_vol_E | — | — | — | prosumer |
| gs_vol_A | $329.95 | $2,999 | 17 | consumer — Best Buy, Target, Walmart |
| gs_vol_B | $299.99 | $2,999 | 15 | consumer |
| gs_vol_C | $299.99 | $2,999 | 18 | consumer |

Pairwise title overlap:

```
within consumer cluster:  A↔B 37/43   A↔C 37/43   B↔C 38/42     (~88% stable)
within prosumer cluster:  espresso↔D 28/48   E↔D 32/48          (~60% stable)
ACROSS clusters:          0/78, 0/78, 0/78, 0/78, 0/78          (ZERO overlap)
```

**Request metadata is identical** — same `google_shopping_url`, same `uule`, same 11 filters, same 4 of 5 category titles. **The variant is not observable from the response.** The only weak tell was the 5th category name (`In stores nearby` vs `Deals on Espresso Machines`).

`product_id` is **not stable**: zero overlap across runs even for the same products. **Do not use `product_id` as a diff key.**

### 8.2 But prices themselves are rock-solid

Joining on `(title, source)` — the identity key that *does* work:

- Merchant-filtered runs (`shoprs`=Target, 3 runs): **32–36 titles matched, 0 price changes.**
- `gs_vol_E` vs `gs_espresso`: 23 titles matched, **exactly 1 price change** — *LUCCA Tempo Espresso Machine, $1,590.00 → $1,482.00* (−6.8%).

**Measured noise floor for price = zero.** Every price delta observed was a real one. The churn is entirely in *which products appear*, never in what a matched product costs.

### 8.3 Required mitigations

1. **Diff key = `(normalised source, normalised title)`**, never `product_id`.
2. **Price-delta events (#1, #2, #6) are safe to fire immediately** — noise floor is 0.
3. **Presence/absence events (#3, #4, #13) must require N≥3 consecutive runs** before firing, or the two-variant flapping will emit ~100% false positives.
4. **Prefer `categorized_shopping_results` over `shopping_results`** for presence tracking — measured 5/5 stable within a variant vs 0/40 for the flat array.
5. **Prefer the `Stores` `shoprs` filter** for per-competitor tracking — merchant-pure and price-stable across all 3 runs.
6. **Normalise marketplace sellers**: `"eBay - weshipnow"`, `"Walmart - MOEFO"` must map to parent merchants or competitor matching will silently fail.
7. **Parse currency from the `price` string** — `extracted_price` is currency-less and `gl=uk` returns `£`. Never compare `extracted_price` across `gl` values.

---

## 9. DOCUMENTED vs OBSERVED

| Claim | Doc says | Live says | Verdict |
|---|---|---|---|
| `google_product` works | Shut down; use immersive | `{"error": "The Google Product service is no longer offered by Google."}` | ✅ Docs correct |
| `shopping_results` in `engine=google` | Documented with full example | **Absent in 10/10 product queries** | ❌ **Doc stale** (2023 examples) |
| `immersive_products` in `engine=google` | Documented | **Present in 8/8 product queries, 16–60 items** | ✅ + richer than documented (`category`, `location` fields undocumented) |
| `product_result` + `typical_price` | Documented | **Absent**, incl. on the doc's own `dyson v8` example | ❌ Not served |
| `start` pagination | "ignored" | Not retested; `num` capped at 40 observed | ✅ Docs correct |
| `more_stores` → up to 13 | Documented | **Exactly 13 on 3/6 products**; 2–8 on the rest | ✅ Correct, product-dependent |
| `stores_next_page_token` | "retrieving the next page" | **Returned 0 stores** | ⚠ Doesn't work |
| `estimated_tax` in `stores[]` | Documented | **Absent in 6/6 drill-downs** | ⚠ Optional |
| `badge: GOOGLE GUARANTEED` in LSA | Documented | **Absent in 20/20 live ads** | ⚠ Optional |
| `bookings_nearby` in LSA | Documented | Absent | ⚠ Optional |
| `ads_results` in `google_local` | Documented | Absent for `emergency plumber` | ⚠ Not always served |
| Cached searches free | "Cached searches are free" | Identical `search_metadata.id` on repeat | ✅ Confirmed |
| `Stores` filter | Listed as a filter type | **40/40 single-merchant, 3/3 runs** | ✅ + highest-value undocumented use |
| Currency field | Not documented | **No currency field anywhere**; symbol only in `price` string | ⚠ Real gap |
| `price_range` currency | Not discussed | **Returned `£` on a `gl=us` product** | ❌ **Bug — don't trust** |
| Result stability | Not discussed | **Two disjoint SERP variants; 0% cross-variant overlap** | ❌ **Undocumented, critical** |

---

## 10. Engine reference

| Engine | Endpoint doc | Status |
|---|---|---|
| `google_shopping` | https://serpapi.com/google-shopping-api | ✅ Live, verified |
| `google_shopping_light` | https://serpapi.com/google-shopping-light-api | ✅ Live — same 40 results + categorized + filters; **not faster in test** (3.44s vs 2.12s) |
| `google_shopping_filters` | https://serpapi.com/google-shopping-filters-api | Not tested |
| `google_product` | https://serpapi.com/google-product-api | ❌ **Shut down** |
| `google_immersive_product` | https://serpapi.com/google-immersive-product-api | ✅ Live, verified |
| `google_immersive_product` (stores) | https://serpapi.com/google-immersive-product-stores | ✅ Live; `more_stores` works, `next_page_token` doesn't |
| `google` → `immersive_products` | https://serpapi.com/immersive-result | ✅ **Live — the free win** |
| `google` → `shopping_results` | https://serpapi.com/inline-shopping | ❌ Not served |
| `google` → `product_result` | https://serpapi.com/product-result | ❌ Not served |
| `google` → `product_sites` | https://serpapi.com/product-sites | Not observed |
| `google` → `ads` | https://serpapi.com/google-ads | ✅ Live (non-product queries) |
| `google` → `local_results[].ad` | https://serpapi.com/local-results | ✅ **Live — free paid-local flag** |
| `google_local` → `ads_results` | https://serpapi.com/google-local-ads | ⚠ Not served in test |
| `google_local_services` | https://serpapi.com/google-local-services-api | ✅ Live, 20 ads/search |
| Pricing | https://serpapi.com/pricing | ✅ |

---

## 11. Recommended build order

1. **Parse `immersive_products` from existing `engine=google` runs.** Zero cost, zero new scheduling. Unlocks events 1–4.
2. **Parse `local_results.places[].ad`.** Zero cost. Unlocks event 5 for service clients.
3. **Implement the `(source, title)` diff key + N≥3 debounce for presence events.** Without this, everything above emits false positives.
4. **Add `google_shopping` per keyword (+10/run)** once merchant normalisation is in place.
5. **Add `google_immersive_product` drill-down on the top 3 products/keyword (+30/run)** for landed-price undercut alerts.
6. **Add `google_local_services` per service/city** for service-vertical clients.

**Budget spent: 40 of 150 searches.** Raw JSON in `./raw/` (my calls listed in `./mine.txt`); `api_key` stripped and verified absent from every saved file.
