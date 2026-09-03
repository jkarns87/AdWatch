# AdWatch — Competitor Discovery via SerpApi

**Research date:** 2026-09-03
**Method:** live SerpApi documentation + a real 65-search end-to-end experiment on a live key.
**Live experiment:** CRM software vertical, notional AdWatch customer = **Pipedrive**.
**Search spend:** 65 metered calls (3 returned SerpApi `error` → per docs not billed; effective ≈62).

> Internal research note: real advertiser names appear throughout. They are observational
> research on public ad placements and must **not** be pasted into public/marketing copy.

---

## 0. Executive summary

Three findings reshape the AdWatch discovery design:

1. **The documented `ads[].link` field no longer contains the advertiser's URL.** In 122/122
   live ad records it was an opaque `https://www.google.com/goto?url=<blob>` redirect.
   `domain_of(link)` returns `google.com` for **100%** of ads. The SerpApi doc example is stale.
   `displayed_link` is the only 100%-available identity field.
2. **The Ads Transparency Center cannot be searched by keyword or topic.** `text=` is a
   *domain* search only. `text="crm software"`, `text="best crm for small business"` and even
   `text="Pipedrive"` (no TLD) all returned zero. ATC is an **enrichment** tool, not a
   discovery tool. Discovery must originate on the SERP.
3. **`engine=google_ads` massively outperforms the `ads` block of `engine=google`** at the same
   1-search cost: 57 ad records vs 16 across the same 10 keywords, 10/10 keywords with ads vs
   7/10, and it is the only one of the two that reliably surfaces brand conquesting.

---

## 1. Discovery from the SERP (zero extra searches)

### 1a. Documented field set

Source: <https://serpapi.com/google-ads> (Google Ad Results API — the `ads` array inside
`engine=google`) and <https://serpapi.com/google-ads-api> (the dedicated `engine=google_ads`).

> "When a Google search contains advertisements, they are parsed and exist within the ads array
> in the JSON output. Advertisements can contain block_position (top, bottom, middle and right),
> title, phone, link, sitelinks, source and more."
> — <https://serpapi.com/google-ads>

Documented per-ad fields: `position`, `block_position`, `title`, `link`, `displayed_link`,
`tracking_link`, `description`, `source`, `extensions[]`, `thumbnail`, `sitelinks[]`
(`title`/`link`/`snippets[]`), plus vertical-specific `price`, `extracted_price`, `rating`,
`reviews`, `links[]`, and `vehicles_for_sale[]`.

The doc's headline example shows a real destination:
`"link": "https://www.viator.com/Paris-tourism/d479-r47064828883-s955139954"`.

### 1b. OBSERVED — what live data actually returns

Measured over **122 ad records from 34 SERP calls** (`engine=google` + `engine=google_ads`,
US/Austin, desktop, 2026-09-03):

| Identity field | Availability | Usable for advertiser identity? |
|---|---|---|
| `displayed_link` | **122/122 (100%)** | **Yes — primary key** |
| `source` | 122/122 (100%) | Partly — inconsistent type (see traps) |
| `tracking_link` | 122/122 (100%) | Only as an `adurl=` carrier |
| `tracking_link` → `adurl=` destination | **41/122 (34%)** | Yes, authoritative when present |
| `link` (documented as destination) | 122/122 present | **No — 122/122 (100%) are `google.com/goto` redirects** |
| `link` containing a real advertiser URL | **0/122 (0%)** | — |

**This is the single most important trap.** A naive `domain_of(ad.link)` — the exact thing the
documentation invites you to write — yields `google.com` for every advertiser in the product.

Where `adurl=` *is* present it is a goldmine and it corroborated `displayed_link` in 4/4
checkable cases. It also leaks the advertiser's own campaign telemetry, e.g. observed live:

```
adurl=https://www.zoho.com/crm/lp/zoho-crm-sales-enablement.html
        ?network=g&device=c&keyword=sales%20crm&campaignid=14560280586
adurl=http://attio.com/p/crm-1707-25
        ?utm_source=google_ads&utm_medium=ppc&utm_campaign=Search-CRM-NAMER-Desktop&utm_term=...
```

That gives you, for free: the advertiser's **Google Ads campaign ID**, their **internal campaign
name**, and the **keyword they think they matched**. INFERRED: campaign ID is a stable
advertiser-owned identifier and a far better join key than any domain heuristic — but only on
the 34% of ads that expose it.

### 1c. The traps, with measured failure modes

| # | Trap | Live evidence | Effect |
|---|---|---|---|
| 1 | **Redirect hides advertiser** | `link` = `google.com/goto?url=…` in 122/122 | `domain_of(link)` → `google.com`. Total identity loss. |
| 2 | **Scheme instability splits one advertiser** | `attio.com` appeared as both `http://www.attio.com` and `https://www.attio.com` | Naive string key creates **two** advertisers from one. |
| 3 | **`source` is not a domain** | `Zoho CRM`→zoho.com, `Salesloft, Inc.`→salesloft.com, `Seamless®`→seamless.ai, `Best CRM Systems`→best-crm-system.com | Legal suffixes, ® glyphs, product-vs-company names. |
| 4 | **`source` is *sometimes* a bare domain** | `tryopine.com`, `scoreapp.com`, `top10.com` used as `source` | The field is untyped — cannot parse uniformly. |
| 5 | **Affiliates / comparison sites bid on category terms** | capterra.com, top10.com, softwareadvice.com, 10bestcrmsoftware.com, best-crm-system.com, projectools.io | 6 of 24 discovered domains are lead-gen arbitrage, **not competitors**. |
| 6 | **Adjacent-category advertiser** | asana.com on "lead management software" | Work-management tool logged as a CRM rival. |
| 7 | **One advertiser, many slots on one SERP** | **19/29 SERPs (66%)** had ≥1 advertiser holding 2+ slots | Share-of-voice computed on slots is inflated. Must dedupe. |
| 8 | **Multi-product domain merges business units** | zoho.com (CRM + ~40 products), hubspot.com (CRM + CMS + marketing) | Domain-level identity is coarser than the competitive unit. |
| 9 | **Sitelink URLs are also redirects** | `sitelinks[].link` observed as `aclk`/`goto` in the mobile doc example and live | Cannot mine sitelinks for extra domains. |

### 1d. Resolution strategy that survives the observed data

```
advertiser_key(ad):
  1. host = first path segment of displayed_link, split on "›", strip scheme + "www."
  2. domain = registrable domain (eTLD+1, real PSL — not a naive last-two-labels split)
  3. if adurl= present in tracking_link: prefer registrable domain of adurl (authoritative);
     assert agreement with (2) and log disagreement as a redirect/affiliate signal
  4. NEVER derive identity from ad.link  (100% failure rate)
  5. normalise: lowercase, drop scheme, drop www., drop trailing dot
  6. classify domain against a maintained ROLE list:
       vendor | affiliate_aggregator | reseller_partner | adjacent_category
     seeded from the ATC dominance test (§3) + a comparison-site blocklist
  7. dedupe per (keyword, poll) before computing share of voice
```

Keep `source`, `title`, and the campaign ID from `adurl` as **attributes**, never as the key.

---

## 2. Discovery from the Ads Transparency Center

Engine: `google_ads_transparency_center` — <https://serpapi.com/google-ads-transparency-center-api>

### 2a. Documented parameters (verbatim)

| Param | Req | Doc text |
|---|---|---|
| `engine` | Required | "Set parameter to `google_ads_transparency_center`…" |
| `advertiser_id` | Optional | "Parameter defines the Google Advertiser ID… found in the Ads Transparency Center advertiser URL." Accepts single or comma-separated IDs. |
| `text` | Optional | "Parameter defines the text you want to search, **typically related to a domain search** within the context of Google Ads… can be used as an alternative to `advertiser_id`." |
| `platform` | Optional | `PLAY`, `MAPS`, `SEARCH`, `SHOPPING`, `YOUTUBE`. "When not set, it will return results from all platforms (default)." |
| `political_ads` | Optional | Only political ads when `true`. "This parameter can only be used alongside with the `region` parameter." |
| `get_advertiser` | Optional | "…fetch the advertiser details (legal name and country of registration). When set to true, **an additional request is made**… can only be used with a single `advertiser_id`." |
| `region` | Optional | Numeric code; default "anywhere". US = `2840`. <https://serpapi.com/google-ads-transparency-center-regions> |
| `start_date` / `end_date` | Optional | `YYYYMMDD`. "To set the date for Today / Single Day, set `end_date` as `start_date` + 1 day." |
| `creative_format` | Optional | `text`, `image`, `video`. |
| `num` | Optional | "40 (default) returns 40 results and 100 returns 100 results." |
| `next_page_token` | Optional | Next page. |

Response: `search_information.total_results`, optional `advertiser{id,name,legal_name,country_code,country}`,
`ad_creatives[]{advertiser_id, advertiser, ad_creative_id, format, link, target_domain, image,
width, height, total_days_shown, first_shown, last_shown, details_link, serpapi_details_link}`,
plus political-only `minimum/maximum_views_count` and `minimum/maximum_budget_spent`, and
`serpapi_pagination{next_page_token, next}`.

### 2b. OBSERVED — **can you enumerate advertisers by keyword or topic? No.**

| Query | Result |
|---|---|
| `text="crm software"` | `error: "Google Ads Transparency Center hasn't returned any results for this search."` |
| `text="best crm for small business"` | same error, 0 creatives |
| `text="Pipedrive"` (brand, no TLD) | same error, 0 creatives |
| `text="pipedrive.com"` | **40 creatives, advertiser resolved** |

SerpApi maps `text` onto the ATC `domain=` URL parameter — visible in the doc's own
`google_ads_transparency_center_url`: `https://adstransparency.google.com?region=US&domain=apple.com`.
**A resolvable domain is required.** There is no keyword, topic, or category enumeration.

**Consequence for AdWatch:** ATC is *not* a first-class discovery mechanism. It cannot answer
"who advertises on this term". It answers "tell me everything about this domain's advertising",
which is enrichment on a domain you already discovered from the SERP.

### 2c. OBSERVED — filters that do not behave as advertised

- **`platform` does not isolate Search ads.** `text=pipedrive.com&platform=SEARCH` and
  `platform=YOUTUBE` returned overlapping sets (37/40 identical creatives, identical format mix).
  `platform=SEARCH` was byte-identical to no-platform (40/40). Worse, **the response carries no
  `platform` field**, so a creative's channel is unknowable. ATC gives creative inventory but
  **not channel attribution** — a real limitation for a paid-*search* product.
- **`start_date`/`end_date` filter on "active during the window", not `first_shown`.**
  `attio.com` with `start_date=20260801` still returned creatives with `first_shown` = 2023-04-14.
  Usable for "is it running now", not for "when did it launch". INFERRED from the observation
  that every query returned `last_shown` max = today.
- **`num=40` is a truncating default.** 20/23 domain lookups returned exactly 40 creatives, so
  advertiser counts on busy domains are **lower bounds** without pagination.

### 2d. Cost

Per <https://serpapi.com/pricing>: "Only successful searches are counted toward your monthly
searches. Cached, errored, and failed searches are not," and "responses with 100 results or empty
result sets will both count as 1 search." Per the engine docs: "Cached searches are free… Cache
expires after 1h."

- 1 ATC call = 1 search. **Each `next_page_token` page = another search** (INFERRED: it is a
  separate metered API call).
- `get_advertiser=true` "an additional request is made" — INFERRED this is internal to SerpApi
  and still bills as 1 search; not isolable on a shared key.
- The 3 zero-result ATC calls returned an `error` field, so per the pricing statement they should
  not be billed. UNVERIFIED (shared key prevented isolation).

---

## 3. Linking a SERP advertiser to an ATC `advertiser_id`

**There is no ID lookup endpoint.** The only route is `text=<registrable domain>` and then reading
`ad_creatives[].advertiser_id`. Tested on all 23 domains discovered in the live experiment.

### 3a. Measured hit rate

| Metric | Result |
|---|---|
| Domains resolving to ≥1 `advertiser_id` | **23/23 (100%)** |
| Domains resolving to exactly **one** advertiser | **16/23 (70%)** |
| Domains returning **multiple** advertisers (ambiguous) | **7/23 (30%)** |
| Correct owner via dominance rule (see below) | **22/23 (96%)** |

`target_domain` on every returned creative equalled the queried domain exactly — so the query is
"all advertisers whose creatives point at this domain". That is why ambiguity appears: the brand
owner **plus its resellers, partners, affiliates and individual media buyers**.

### 3b. The ambiguity structure (real data)

| Domain | Advertisers | Top advertiser (creative share) | Reading |
|---|---|---|---|
| scoreapp.com | **15** | Hyper Targeted Marketing Ltd (12/40 = 30%) | **No dominant owner — resolution fails** |
| hubspot.com | 11 | Hubspot, Inc. (28/40 = 70%) | owner + 10 partners/affiliates |
| keap.com | 9 | Infusion Software, Inc. (18/26 = 69%) | owner under a **former legal name** |
| honeybook.com | 3 | Honeybook Inc (38/40 = 95%) | owner + 2 affiliates |
| salesloft.com | 2 | Salesloft, Inc. (38/40 = 95%) | owner + 1 individual |
| asana.com | 2 | Asana, Inc. (38/40 = 95%) | owner + 1 agency (MightyHive) |
| capterra.com | 2 | Capterra Inc. (39/40 = 98%) | owner + 1 |

**Dominance rule:** attribute the domain to the advertiser holding **≥50% of returned creatives**;
otherwise flag for review. That yields 22/23 = **96%** correct owner attribution. The single
failure, scoreapp.com, is correctly *flagged* rather than silently mis-attributed — and its flat
distribution is itself a signal (an affiliate-saturated product).

### 3c. Ambiguity risks to design around

- **Legal name ≠ brand name.** keap.com → "Infusion Software, Inc."; a name-similarity join would
  score ~0 and reject the true owner. Never gate on name similarity; use creative dominance.
- **Individuals as advertisers.** "NATHANIEL DALE MEADOWS" (tryopine.com), "Shawn Van Dyke",
  "Jill Samycia". `advertiser` is not always a company.
- **Comparison-site operators mask the brand.** top10.com → "Natural Intelligence Ltd";
  best-crm-system.com → "FMK Compare GmbH"; projectools.io → "Scaleup Media Ltd". These are
  arbitrage operators; treat as `affiliate_aggregator`, not competitors.
- **Truncation inflates confidence.** With `num=40` capping 20/23 lookups, minority advertisers
  are undercounted. Paginate before trusting a dominance ratio near the 50% line.
- **Verdict:** SERP → ATC is a **viable** product flow (100% resolve, 96% correctly attributed),
  provided you use the dominance rule and treat one lookup per domain as a **one-time enrichment**,
  cached indefinitely — not a per-poll cost.

---

## 4. Cross-keyword advertiser overlap — real numbers

10 keywords × `engine=google_ads` = **10 searches, zero extra**. All figures below are derived
from that one dataset with no additional calls.

### 4a. Engine comparison (same 10 keywords, same 10-search cost)

| | `engine=google` ads block | `engine=google_ads` |
|---|---|---|
| Ad records | 16 | **57** |
| Keywords with ≥1 ad | 7/10 | **10/10** |
| Unique advertiser domains | 9 | **11** |
| Advertisers on 2+ keywords | 1 | **8** |

The two sets are **almost disjoint — only 2 of 18 advertisers appeared in both**
(attio.com, zoho.com). `google_ads` found the incumbents (Pipedrive, HubSpot, monday.com);
the `google` ads block found a different long tail (Asana, Capterra, LeanData, Seamless, ScoreApp).
Running both doubles recall for 2× cost.

### 4b. Share of voice, coverage breadth (engine=google_ads, 57 slots)

| Advertiser | Keywords | Breadth | Slots | SoV |
|---|---|---|---|---|
| monday.com | 9 | 90% | 12 | 21.1% |
| pipedrive.com | 7 | 70% | 13 | **22.8%** |
| zoho.com | 7 | 70% | 10 | 17.5% |
| hubspot.com | 6 | 60% | 6 | 10.5% |
| attio.com | 4 | 40% | 5 | 8.8% |
| top10.com | 2 | 20% | 3 | 5.3% |
| reevo.ai | 2 | 20% | 3 | 5.3% |
| gong.io | 2 | 20% | 2 | 3.5% |
| 10bestcrmsoftware.com / salesloft.com / clozd.com | 1 each | 10% | 1 each | 1.8% each |

Note monday.com leads on *breadth* (90%) while pipedrive.com leads on *SoV* (22.8%) — a
concentrated-vs-broad strategy contrast that falls straight out of the same 10 calls.

### 4c. Head-to-head overlap (Jaccard on keyword sets)

| Pair | Shared | Jaccard |
|---|---|---|
| zoho.com vs hubspot.com | 5/8 | **0.62** |
| monday.com vs zoho.com | 6/10 | 0.60 |
| monday.com vs pipedrive.com | 6/10 | 0.60 |
| zoho.com vs pipedrive.com | 5/9 | 0.56 |
| monday.com vs hubspot.com | 5/10 | 0.50 |
| pipedrive.com vs hubspot.com | 3/10 | 0.30 |
| zoho.com vs attio.com | 2/9 | 0.22 |

### 4d. Signal-by-signal cost

| Derived signal | Extra searches | Notes |
|---|---|---|
| Share of voice per advertiser | **0** | Dedupe slots per SERP first (66% of SERPs had a repeat advertiser) |
| Keyword coverage breadth | **0** | |
| Head-to-head Jaccard overlap | **0** | Any pair, any time, from stored history |
| New entrant | **0** | Requires persistence gating — see 4e |
| Advertiser going dark | **0** | Requires absence gating — see 4e |
| Position/rank trend per advertiser | **0** | `position` + `block_position` already stored |
| Ad copy change (headline/description/sitelinks) | **0** | SERP returns these as text; ATC does **not** (§6) |
| Campaign ID / advertiser's own keyword | **0** | Only on the 34% of ads exposing `adurl=` |
| Advertiser legal identity, creative history, region list | 1 per domain, **one-time** | ATC enrichment, cacheable forever |

### 4e. OBSERVED — volatility makes naive new-entrant alerts unusable

Same query (`sales crm`, `engine=google_ads`), 4 samples within minutes, `no_cache=true`:

| Sample | Advertisers |
|---|---|
| t0 | attio, monday, pipedrive, reevo |
| t1 | attio, monday, pipedrive, reevo, **gong** |
| t2 | attio, monday, pipedrive, **gong** |
| t3 | attio, monday, pipedrive, reevo, **gong** |

- Union across 4 samples: **5**; stable in all 4: **3**. **40% of the advertiser set is volatile
  within minutes.** Single-call recall vs the 4-call union: 80–100%.
- **Design rule:** never emit `new_advertiser` on first sighting. Require presence in **≥2 of the
  last 3 polls**; require absence across **≥3 consecutive polls** before emitting
  `advertiser_went_dark`. Without this, both alerts are mostly noise.

---

## 5. Brand-bidding detection — tested live

**Query shape:** one search per brand term. `engine=google_ads`, `q=<brand>`, `location`, `gl`,
`hl`, `device`. **Cost: exactly 1 search per brand term per run.**

Any advertiser in the paid block whose resolved domain ≠ the brand owner's domain is a conqueror.

### 5a. Results (8 CRM brand terms)

| Brand query | Ads | Owner present? | Conquerors observed |
|---|---|---|---|
| pipedrive | 4 | YES | attio.com, monday.com |
| hubspot crm | 4 | YES | monday.com |
| zoho crm | 2 | **NO** | monday.com, pipedrive.com |
| monday.com crm | 6 | **NO** | attio, honeybook, pipedrive, + 3 affiliates |
| salesforce crm | 2 | **NO** | attio.com, pipedrive.com |
| attio crm | 0 | — | (no ads served) |
| keap crm | 6 | YES | attio.com, honeybook.com, monday.com |
| freshsales crm | 4 | **NO** | attio.com, pipedrive.com |

- Brand SERPs with ≥1 ad: **7/8**
- Of those, **≥1 competitor bidding on the brand: 7/7 = 100%**
- Of those, **brand owner absent from its own brand SERP: 4/7 = 57%**
- Most aggressive conquerors: attio.com (5 rival brands), monday.com (4), pipedrive.com (4)

**Brand conquesting is not an edge case in this vertical — it is universal.** And the
"owner absent" case is arguably the more valuable alert: the customer is being outbid on their own
name and is not even in the auction.

### 5b. Engine choice is decisive for this alert

| Brand query | `engine=google` found | `engine=google_ads` found |
|---|---|---|
| pipedrive | pipedrive ×2 — **0 conquerors** | pipedrive, **attio, monday** |
| monday.com crm | **0 ads** | 6 ads, 6 conquerors |
| salesforce crm | **lessannoyingcrm.com** (1 conqueror google_ads missed) | pipedrive, attio |

A brand-bidding alert built on `engine=google` would have told Pipedrive "no threats detected"
while Attio and monday.com were actively bidding on its name. **Use `engine=google_ads`**; add
`engine=google` as a second call only where recall matters more than cost (neither is complete).

### 5c. Change events

```
brand_conquest_started   {brand_term, conqueror_domain, first_seen_poll, position, ad_title}
brand_conquest_ended     {brand_term, conqueror_domain, last_seen_poll}
brand_undefended         {brand_term}                 # owner absent from own brand paid block
brand_defense_resumed    {brand_term}
```
Gate all four on the ≥2-of-3 persistence rule from §4e.

---

## 6. Untapped opportunities, ranked by value per search

### Tier 0 — zero extra searches (pure post-processing of calls AdWatch already makes)

| # | Feature | Engine / params | Change event | Cost |
|---|---|---|---|---|
| 1 | **Unknown-advertiser discovery** | existing keyword polls | `advertiser_discovered{domain, keyword, position}` | **0** |
| 2 | **Share of voice + breadth leaderboard** | existing polls, dedupe per SERP | `sov_shifted{domain, delta_pp}` | **0** |
| 3 | **Advertiser went dark / returned** | existing polls, 3-poll absence gate | `advertiser_went_dark` / `advertiser_returned` | **0** |
| 4 | **Ad copy change tracking** | `title`, `description`, `sitelinks[]` are text on the SERP | `ad_copy_changed{domain, keyword, old, new}` | **0** |
| 5 | **Sitelink/offer change** | `sitelinks[].title` set diff | `offer_changed{domain, added[], removed[]}` | **0** |
| 6 | **Campaign-ID + rival keyword leak** | parse `adurl=` (34% of ads) for `campaignid`, `utm_campaign`, `keyword`/`utm_term` | `campaign_launched{domain, campaign_id, campaign_name}` | **0** |
| 7 | **Head-to-head contested-keyword map** | Jaccard over stored history | `head_to_head_shifted{a, b, delta}` | **0** |
| 8 | **Affiliate-pressure index** | share of paid block held by `affiliate_aggregator` role | `affiliate_pressure_rising{keyword}` | **0** |

Tier 0 items 4, 5 and 6 are the standouts: **ad copy, offers and campaign IDs are only available
from the SERP** — ATC returns creatives as rendered images with no text and no landing URL (§6b).
AdWatch already pays for these calls; today it throws the payload away.

### Tier 1 — one extra search per unit, high value

| # | Feature | Engine / params | Change event | Cost |
|---|---|---|---|---|
| 9 | **Brand-bidding / conquesting alert** | `engine=google_ads&q=<customer brand>` | `brand_conquest_started`, `brand_undefended` | **1 / brand term / run** |
| 10 | **Rival-brand conquesting (offensive)** | same, on each competitor's brand | `rival_brand_undefended{rival}` — a buying opportunity | 1 / rival brand / run |
| 11 | **Dual-engine recall boost** | add `engine=google` beside `google_ads` on top keywords | `advertiser_discovered` (long tail) | +1 / keyword / run |

### Tier 2 — one-time or low-frequency enrichment (cache forever)

| # | Feature | Engine / params | Change event | Cost |
|---|---|---|---|---|
| 12 | **Advertiser identity resolution** | `google_ads_transparency_center&text=<domain>&region=2840` + dominance rule | `advertiser_identified{domain, advertiser_id, legal_name, country}` | **1 / domain, one-time** |
| 13 | **Competitor creative-volume trend** | same, re-polled weekly; count creatives + `first_shown` | `creative_volume_spiked{domain}` (budget-ramp proxy) | 1 / domain / week |
| 14 | **Geographic expansion** | `google_ads_transparency_center_ad_details` → `regions[]` with per-region `last_shown` | `entered_region{domain, region}` | 1 / creative |
| 15 | **Advertiser roster growth** | ATC domain lookup, count distinct `advertiser_id` | `new_reseller_or_affiliate{domain, advertiser}` | 1 / domain / week |

### 6b. Explicitly NOT worth building

- **Ad-copy history from ATC.** The `..._ad_details` engine returned only
  `ad_creatives[0].image` (a `tpc.googlesyndication.com` render) plus `search_information`
  with `ad_funded_by`, `format`, `last_shown` and `regions[]`. **No headline, no description, no
  landing URL** — even for `format: "text"`. Copy monitoring must come from the SERP (Tier 0 #4).
  The one genuinely useful field is `ad_funded_by` ("Pipedrive Inc."), a clean legal-identity
  cross-check.
- **Keyword discovery via ATC.** Impossible — `text` is domain-only (§2b).
- **Channel split via ATC `platform`.** Non-functional on domain searches, and the response has no
  platform field (§2c).

### 6c. Recommended default plan for a 10-keyword customer

| Component | Searches/run |
|---|---|
| 10 category keywords on `engine=google_ads` | 10 |
| Customer's own brand term | 1 |
| 3 top rival brand terms | 3 |
| **Per run** | **14** |
| One-time ATC identity enrichment | 1 per newly discovered domain (~20 at onboarding, then rare) |

Daily at 14 searches ≈ 420/month/customer, and it delivers every Tier 0 signal plus the flagship
brand-conquesting alert.

---

## 7. DOCUMENTED vs OBSERVED

| Claim | Documented | Observed live (2026-09-03) |
|---|---|---|
| `ads[].link` is the destination URL | Example shows `https://www.viator.com/...` — <https://serpapi.com/google-ads> | **False.** 122/122 were `google.com/goto?url=` redirects. 0% usable. |
| `ads[].source` names the advertiser | "…title, phone, link, sitelinks, source and more" | Present 100%, but untyped: brand name, legal name w/ suffix, ® glyph, or bare domain. |
| ATC `text` is a free-text search | "text you want to search, **typically related to a domain search**… anything you would normally use in a standard ATC search" | **Domain-only.** Topics and bare brand names return zero results. |
| ATC `platform` filters by surface | `PLAY/MAPS/SEARCH/SHOPPING/YOUTUBE` | **Ineffective on domain searches** (SEARCH ≡ no-filter, 37/40 overlap with YOUTUBE); no platform field in response. |
| ATC `start_date`/`end_date` | "start date for which you want the search results to begin" | Filters "active during window", **not** `first_shown`. Creatives from 2023 returned for an Aug-2026 window. |
| `num` default 40 | "40 (default)… 100 returns 100" | Confirmed; **20/23 lookups truncated at exactly 40** → advertiser counts are lower bounds. |
| `engine=google_ads` is a higher-rate ads scraper | "scrape sponsored results… at a higher rate than the standard Google Search API" — <https://serpapi.com/google-ads-api> | **Confirmed and then some:** 57 vs 16 ad records, 10/10 vs 7/10 keyword coverage, and the only engine that surfaced brand conquesting. |
| Only successful searches billed | "Cached, errored, and failed searches are not" — <https://serpapi.com/pricing> | 3 zero-result ATC calls returned `error`; billing not isolable on a shared key. UNVERIFIED. |
| ATC ad details returns the creative | `ad_creatives[]` | Returns **only an image URL**; no ad text, no landing page. `ad_funded_by` is the useful field. |

---

## 8. Sources

- <https://serpapi.com/google-ads> — Google Ad Results API (`ads` array in `engine=google`)
- <https://serpapi.com/google-ads-api> — dedicated `engine=google_ads`
- <https://serpapi.com/google-ads-transparency-center-api> — ATC engine, params + response schema
- <https://serpapi.com/google-ads-transparency-center-regions> — numeric region codes (US = 2840)
- <https://serpapi.com/pricing> — search metering, cached/errored searches
- <https://serpapi.com/search-api> — Google Search API

## 9. Experiment provenance

- 65 metered calls: 21 `google_ads`, 13 `google`, 30 `google_ads_transparency_center`,
  1 `google_ads_transparency_center_ad_details`. 3 returned `error` (zero-result ATC probes).
- Account before: `total_searches_left: 14303`. After: `13945`. The 358 delta includes
  concurrent agents on the same shared key; **my own spend is 65**, tracked in `ledger.jsonl`.
- All raw responses saved under `scratchpad/raw/` with `api_key` and `search_metadata` stripped.
  Verified: 0 files contain the key; 0 of my files contain an `api_key` field.
- Locale held constant: `location="Austin, Texas, United States"`, `gl=us`, `hl=en`,
  `device=desktop`. Results are locale- and time-specific; volatility measured at 40% (§4e).
