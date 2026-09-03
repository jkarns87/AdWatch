# SerpApi for AdWatch — Keyword Discovery & Demand Expansion

Research date: 2026-09-03. Live measurement against the SerpApi production API (62 successful searches).
Every doc claim is cited. Every measured claim is labelled **OBSERVED** with the raw JSON file under `raw/`.
Inference is labelled **INFERRED**.

---

## 0. Headline numbers (read this if you read nothing else)

| Question | Answer |
|---|---|
| Onboarding cost/yield — cheap tier | **4 searches → 116 unique candidate keywords (29.0/search)** |
| Onboarding cost/yield — full tier | **38 searches → 554 unique candidate keywords (14.6/search)** |
| Does SerpApi expose search volume / CPC / competition for an arbitrary keyword? | **No. Not through any engine.** See §5. |
| Biggest single win found | **Swap `engine=google` → `engine=google_ads`.** Same 1-search cost, same free ride-alongs, but it returned **6 ads where `engine=google` returned 0** on the identical query+location. See §7.1. |
| Best free-rider | `refine_this_search` — up to **25 commercial facet chips** on shopping-intent SERPs, at zero marginal cost. See §3.2. |
| Highest raw yield per single search | `google_trends_trending_now` — **864 trends + 914 breakdown terms = ~1,778 strings for 1 search**, with bucketed absolute volume. See §5.2. |

Budget accounting: baseline `total_searches_left` **14,323** → final **14,020**. The account-wide delta (303) is
**contaminated by concurrent sibling agents on the same key** — I re-checked the balance twice with zero calls
issued from this agent and it still dropped (13,774 → 13,770). My own ledger: **68 calls attempted, 6 returned
`error` (not billed, per [pricing](https://serpapi.com/pricing): "Only successful searches are counted toward
your monthly searches. Cached, errored, and failed searches are not."), so **62 searches spent**, against a
budget of 150.

---

# PART A — DOCUMENTED

## 1. `google_autocomplete`

Doc: <https://serpapi.com/google-autocomplete-api>

### 1.1 Full parameter set (verbatim from the docs page)

| Group | Param | Req | Description |
|---|---|---|---|
| Search Query | `q` | **Required** | "Parameter defines the search query. A query that would be used to provide completion options." |
| Localization | `gl` | Optional | Two-letter country code (`us`, `uk`, `fr`). Full list: <https://serpapi.com/google-countries> |
| Localization | `hl` | Optional | Two-letter language code (`en`, `es`, `fr`). Full list: <https://serpapi.com/google-languages> |
| Advanced | `cp` | Optional | "Cursor pointer defines the position of cursor for the query provided, position starts from 0 which is a case where cursor is placed before the query `\|query`. If not provided acts as cursor is placed in the end of query `query\|`." |
| Advanced | `client` | Optional | "Parameter used to define client for autocomplete." List: <https://serpapi.com/google-autocomplete-clients> |
| SerpApi | `engine` | **Required** | `google_autocomplete` |
| SerpApi | `api_key` | **Required** | Private key |
| SerpApi | `no_cache` | Optional | Bypass cache. "Cache expires after 1h. Cached searches are free, and are not counted towards your searches per month." |
| SerpApi | `async` | Optional | Submit and retrieve later via Searches Archive API. Must not be combined with `no_cache`. |
| SerpApi | `zero_trace` | Optional | Enterprise only. |
| SerpApi | `output` | Optional | `json` (default), `html`, `md`. |
| SerpApi | `json_restrictor` | Optional | Field allowlist to shrink payload. <https://serpapi.com/json-restrictor> |

There is **no** `location`, `uule`, `device`, or `num` parameter on this engine — geo targeting is `gl` only.

### 1.2 Response shape (documented)

```
search_information.autocomplete_results_state   // e.g. "Showing completion results."
suggestions[].value            // the suggested query string
suggestions[].relevance        // integer, chrome / chrome-omni only
suggestions[].type             // e.g. "QUERY", chrome / chrome-omni only
suggestions[].serpapi_link     // pre-built google_autocomplete call for that suggestion
verbatim_relevance             // integer, chrome / chrome-omni only
```

Docs state: "`chrome` and `chrome-omni` clients also have omnibox related metadata — `suggesttype`,
`verbatim_relevance`, `clientdata`." (<https://serpapi.com/google-autocomplete-api>)

### 1.3 The `client` parameter — documented values

Doc: <https://serpapi.com/google-autocomplete-clients>

| `client` | Documented description |
|---|---|
| `chrome` | "Is used in when google is opened in google chrome" |
| `chrome-omni` | "Comes from chrome omnibox - address bar in chrome" |
| `gws-wiz` | "Is used in Google home page" |
| `gws-wiz-local` | "Is used for Google Local" |
| `safari` | "Is used in when Google is opened in safari" |
| `firefox` | "Is used in when Google is opened in firefox" |
| `psy-ab` | "Is used in when Google is opened in Google Chrome" |
| `toolbar` | "Origin unknown. Returns XML" |
| `youtube` | "Origin unknown. Returns JSONP" |

### 1.4 Cost

1 search per call. Nothing on the pricing page marks autocomplete as cheaper or more expensive
(<https://serpapi.com/pricing>). Cached repeats within 1h are free.

---

## 2. `related_questions` / People Also Ask — **both**

- **As a field on the `google` engine response:** <https://serpapi.com/related-questions>
- **As a standalone engine:** `engine=google_related_questions`, <https://serpapi.com/google-related-questions-api>

The standalone engine takes exactly one meaningful input:

> `next_page_token` — "token needed to show additional related questions that Google generates when a specific
> question gets clicked" (<https://serpapi.com/google-related-questions-api>)

Documented `related_questions[]` item fields (<https://serpapi.com/related-questions>):
`question`, `type` (`featured_snippet` | `ai_overview`), `next_page_token`, `serpapi_link`; for
`featured_snippet`: `snippet`, `title`, `link`, `displayed_link`, `source_logo`, `table`, `date`, `info`;
for `ai_overview`: `text_blocks`, `references`, `thumbnail`.

**Tree expansion cost:** the initial 4 questions are free on the parent `google` call. Every node you expand
costs **1 additional search** (one `google_related_questions` call per `next_page_token`). A 2-level expansion
of 4 seed questions each yielding ~4 children = 4 searches for level 2, 16 for level 3. This grows badly; see
the OBSERVED section for why it is worse than it looks in 2026.

---

## 3. `related_searches` on the `google` engine — free rider

Doc: <https://serpapi.com/related-searches>

Exact key: `related_searches`. Item shape:

```json
{
  "block_position": 1,
  "query": "coffee near me",
  "link": "https://www.google.com/search?...",
  "serpapi_link": "https://serpapi.com/search.json?..."
}
```

Optional variants carry `image` and a nested `items[]` array (`name`, `image`, `link`, `serpapi_link`,
`reviews`, `rating`, `duration`, `extensions`) for entity-carousel style related searches.

**Cost: zero marginal.** It is part of the JSON body of a `google` search AdWatch already pays 1 search for.
Not requesting it does not refund anything.

Sibling free riders documented on the same response
(<https://serpapi.com/search-api> nav + individual pages):
`refine_this_search` (<https://serpapi.com/refine-this-search>), `things_to_know`
(<https://serpapi.com/things-to-know>), `related_questions`, `perspectives`, `discussions_and_forums`,
`related_brands`, `related_categories`, `broaden_searches`, `refine_search_filters`.

---

## 4. Google News

Two distinct products:

**(a) `engine=google_news`** — news.google.com. Doc: <https://serpapi.com/google-news-api>

| Param | Notes |
|---|---|
| `q` | "You can use anything that you would use in a regular Google News search. e.g. `site:`, `when:`". Docs: `q` "can't be used together with any of the Advanced Parameters." |
| `gl` / `hl` | country / language, default `us` / `en` |
| `topic_token` | topic feed (World, Business, …) |
| `publication_token` | single-publisher feed |
| `section_token` | sub-section of a topic |
| `story_token` | full coverage of one story |
| `so` | `0` relevance (default), `1` date |
| SerpApi | `no_cache`, `async`, `zero_trace`, `output`, `json_restrictor`, `api_key` |

Response: `news_results[]` with `position`, `title`, `link`, `date`, `iso_date`, `source{name,icon,authors[]}`,
`thumbnail`, `thumbnail_small`; plus `menu_links`, `related_topics`, `related_publications`.

**(b) `engine=google&tbm=nws`** — the News *tab* of Google Search. Doc: <https://serpapi.com/news-results>.
Returns `news_results[]` with `position`, `title`, `link`, `source`, `date`, `published_at`, `snippet`,
`favicon`, `thumbnail`, plus `people_also_search_for`. This variant carries a `snippet`, which
`google_news` does not.

Cost: 1 search either way.

---

## 5. Search volume, CPC, competition — **SerpApi does not provide this**

This is flat, not hedged.

SerpApi has **no keyword-volume endpoint, no CPC estimate, and no keyword-competition score** for an arbitrary
keyword, on any engine. SerpApi says so itself in its own competitor comparison
(<https://serpapi.com/blog/dataforseo-vs-serpapi/>):

> "SerpApi doesn't support these features because its main focus is on the web search API rather than an SEO
> data suite."
>
> "If you need backlink graphs or a keyword-volume database alongside SERPs, DataForSEO consolidates that in
> one account."

and describes itself as "SERP-focused (no backlinks/keyword DB)". If AdWatch needs true volume/CPC it must
buy it elsewhere — Google Ads Keyword Planner API (free with an Ads account, but volume is bucketed unless
you spend), DataForSEO Labs, or a Semrush/Ahrefs feed. **Do not build a volume number out of SerpApi data and
present it to a customer as volume.**

### 5.1 The three legitimate proxies, and exactly where each breaks

| Proxy | Source | What it actually is | Where it breaks |
|---|---|---|---|
| **Relative interest index** | `google_trends&data_type=TIMESERIES` (<https://serpapi.com/google-trends-api>) | `interest_over_time.timeline_data[].values[].extracted_value`, 0–100, **normalised to the max point across the queries in that one call** | Not absolute. Not comparable across calls. Max 5 queries per call, so cross-keyword ranking beyond 5 requires chained calls with a shared pivot keyword and manual re-normalisation. Zero-suppressed for low-volume terms unless `include_low_search_volume=true`. |
| **Autocomplete rank order** | `suggestions[].relevance` on `client=chrome` | Google's own ordering signal for completions of that prefix | Only ordinal, only *within one prefix*. Values I observed run 601 → 550 in a monotone descending ladder — it is a rank, not a magnitude. Cross-prefix comparison is meaningless. |
| **Ad density on the SERP** | `(.ads \| length)` on a `google_ads` / `google` call | How many advertisers are willing to buy the top slot right now | A commercial-competition proxy, **not** a CPC. Saturated at Google's slot cap (I never saw >6). Zero ads ≠ zero competition (see §7.1 OBSERVED — `engine=google` under-reports ads badly). |

### 5.2 The one place SerpApi does surface an absolute-looking volume — and its hard limit

`engine=google_trends_trending_now` (<https://serpapi.com/google-trends-trending-now>) returns
`trending_searches[].search_volume` as an **integer**, alongside `increase_percentage`.

**This is real, and it is the only absolute number in the whole API.** But it only exists for queries Google
has classified as *currently trending*. You cannot ask it "what is the volume of `espresso machine`". It is a
firehose you filter, not a lookup you query. See the OBSERVED section for the measured bucket ladder.

---

## 6. Google Images / Lens / Videos — creative intelligence

Short answer: **Images is worth one call for keyword facets; Lens is worth it only if AdWatch stores competitor
creative assets; Videos is skippable.**

- **`engine=google_images`** (<https://serpapi.com/google-images-api>) — carries `suggested_searches[]` and
  `related_searches[]` free on the response. This is a *keyword* play, not a creative play. See OBSERVED §B4.
- **`engine=google_lens`** (<https://serpapi.com/google-lens-api>) — accepts an image `url` and returns
  `visual_matches`, `exact_matches`, `products`, `about_this_image`. The genuinely useful AdWatch shape: feed
  it a competitor's hero/ad image and get back every other domain running that same asset. That is real
  creative-reuse intelligence. Cost 1 search per image, so it only scales if AdWatch is deliberate about which
  images it tracks.
- **`engine=google_videos`** (<https://serpapi.com/google-videos-api>) — no paid-search signal that
  `google_news` or the SERP's own `inline_videos` block doesn't already give you for free. Skip.

Also relevant and better than all three for pure ad-creative work:
**`engine=google_ads_transparency_center`** (<https://serpapi.com/google-ads-transparency-center-api>) —
params `advertiser_id`, `text`, `region`, `start_date`, `end_date`, `platform` (PLAY/MAPS/SEARCH/SHOPPING/
YOUTUBE), `creative_format` (text/image/video), `political_ads`, `get_advertiser`, `num` (default 40, max 100),
`next_page_token`. Returns ad creatives with `first_shown` / `last_shown` timestamps — i.e. a competitor's
campaign start and stop dates. **Caveat measured in §B6: `text=` search did not resolve.**

---

# PART B — OBSERVED (live API, 62 searches)

All raw responses under `raw/`. `search_parameters.api_key` stripped from every file; verified 0 files contain
the key (64-char secret, `grep -rlF` returned nothing).

## B1. `google_autocomplete` field inventory — OBSERVED

`jq -r 'paths(scalars)|join(".")' | sed 's/[0-9]\+/[]/g' | sort -u` on `raw/ac_client_chrome.json`:

```
search_information.autocomplete_results_state
search_metadata.{id,status,created_at,processed_at,total_time_taken,
                 google_autocomplete_url,json_endpoint,markdown_endpoint,
                 raw_html_file,prettify_html_file}
search_parameters.{engine,q,gl,hl,client}
suggestions.[].{value,relevance,type,serpapi_link}
verbatim_relevance
```

`gws-wiz` returns a **different** set: `suggestions[].{value, value_highlight, serpapi_link}` and, for entity
suggestions, `suggestions[].{title, subtitle}` — **no `relevance`, no `type`, no `verbatim_relevance`**.

## B2. The `client` parameter measured — the docs undersell how much it matters

Seed `espresso machine`, `gl=us&hl=en`, 10 calls (`raw/ac_client_*.json`):

| `client` | n suggestions | has `relevance` | unique to this client |
|---|---|---|---|
| *(omitted)* | **15** | yes | 1 |
| `chrome` | **15** | yes | 1 |
| `youtube` | 14 | no | 0 |
| `firefox` | 10 | no | 0 |
| `safari` | 10 | no | 0 |
| `psy-ab` | 10 | no | 0 |
| `toolbar` | 10 | no | 1 |
| `gws-wiz` | 10 | no | 1 |
| `gws-wiz-local` | 10 | no | 2 |
| `chrome-omni` | **8** | yes | 2 |

Three findings AdWatch should act on:

1. **Omitting `client` is identical in shape to `client=chrome`** — 15 results, `relevance`, `type`,
   `verbatim_relevance`. SerpApi's own `google_autocomplete_url` in `search_metadata` confirms it appends
   `&client=chrome` when you don't. So the default is already the best client. **INFERRED:** no reason to send
   `client` at all unless you specifically want gws-wiz's entity `title`/`subtitle`.
2. **`chrome` returns 50% more suggestions than every non-Chrome client** (15 vs 10). Use it.
3. **Rotating clients is a bad trade.** 10 searches across all 10 clients produced a union of only **24**
   unique suggestions, versus **15 from `chrome` alone in 1 search**. That is +9 keywords for +9 searches
   (1.0/search). The same 9 searches spent on alphabet-soup letters yield ~135. **Do not rotate clients.**

One caveat worth logging: `gws-wiz` returned `espresso machine repair tampa`. That is IP-geo personalisation
leaking through SerpApi's egress, not a US-national signal. `gl=us` does not fully suppress it.

## B3. Expansion yield — the deliverable number

Seed `espresso machine`, `client=chrome`, `gl=us&hl=en`. 26 alphabet-soup calls
(`q=espresso machine {a..z}`, `raw/ac_soup_*.json`) + 8 modifier stems (`best…`, `cheap…`, `buy…`,
`…for`, `…vs`, `…under`, `…reviews`, `commercial…`, `raw/ac_mod_*.json`).

```
seed call (1 search):          15 unique
alphabet soup (26 searches):  389 unique   (390 raw — near-zero intra-soup overlap)
modifiers (8 searches):       120 unique;  90 new
------------------------------------------------------------
TOTAL 35 searches ->          479 unique   = 13.7 unique/search
```

Composition of the 479 (regex classifier, `expansion_buckets.json`):

| bucket | n | % |
|---|---|---|
| explicit commercial intent (`best/cheap/buy/under $X/sale/near me/reviews/for sale/commercial`) | 138 | 29% |
| competitor brand named (Breville, De'Longhi, Jura, La Marzocco, Ninja, Nespresso, Profitec…) | 26 | 5% |
| retailer named (Amazon, Walmart, Costco, Target…) | 11 | 2% |
| purely informational (`how to clean`, `parts diagram`, `descale`) | 22 | 5% |
| unclassified long-tail (specs, colours, models, geos) | 282 | 59% |

95% are non-informational. Spot-checking the 282 unclassified: mostly genuinely biddable
(`espresso machine dual boiler`, `espresso machine that uses pods`, `espresso machine with milk frother`),
with a visible noise tail (`espresso machine zs`, `espresso machine qatar`, a 20-word Amazon SKU title).
**INFERRED:** budget for an LLM filter pass that discards ~20–30%, giving **~340–380 usable candidates from
35 searches**.

### The cost curve — this is what should drive the onboarding design

Cumulative dedup across all sources for the same seed:

| step | cost | new keywords | new/search |
|---|---:|---:|---:|
| `google_ads(seed)` → `related_searches` + PAA + `refine_this_search` + `things_to_know` | 1 | **41** | **41.0** |
| `google_trends&data_type=RELATED_QUERIES` | 1 | 39 | 39.0 |
| `google_images(seed)` → `suggested_searches` + `related_searches` | 1 | 29 | 29.0 |
| `google_autocomplete(seed)` | 1 | 7 | 7.0 |
| 26× alphabet soup | 26 | 348 | 13.4 |
| 8× modifier stems | 8 | 90 | 11.2 |

- **Cheap tier: 4 searches → 116 unique (29.0/search).**
- **Full tier: 38 searches → 554 unique (14.6/search).**
- The 34 autocomplete calls are the *low-yield* tail at 12.9 new/search. They are worth buying — nothing else
  produces 438 keywords — but they should be the **last** thing bought, not the first.

**Recommended onboarding ladder:** run the 4-search cheap tier for every customer. Run the 34-search soup only
for seeds the customer confirms as core, and only for one or two seeds, not for every category term.

## B4. Free ride-alongs — confirmed on real responses

Every `google` / `google_ads` call in this study, without exception (8 SERPs across 6 verticals):

| block | count per call | cost |
|---|---|---|
| `related_searches` | **exactly 8, every time** | free |
| `related_questions` | **exactly 4, every time** | free (question text only) |
| `refine_this_search` | **25** on shopping-intent seeds (`espresso machine`); **0** on the others | free |
| `things_to_know.buttons` | 4–5 when present | free |
| `organic_results` | 8–9 | free |
| `ads` | 0–6 (see B5) | free |
| `ai_overview` | present on 8/8 | free |

`refine_this_search` on `espresso machine` returned these 25 chips verbatim — this is Google's own commercial
facet taxonomy for the category, delivered at zero marginal cost:

> With Grinder · On sale · Under $200 · Home · Nearby · For Commercial Use · With Steam Wand · Automatic ·
> Get it today · Semi Automatic · Manual · Reviews · Pump · Super Automatic · Pod Compatible · Small · New ·
> Used · Keurig · Price · Barista · Nespresso Compatible · Black · For Sale · Brand

Cross-producted with the seed these become 25 high-intent long-tails (`espresso machine under $200`,
`espresso machine for commercial use`, `espresso machine used`). **This is the single best free keyword source
in the API and AdWatch is not using it.** Note it fires on product/shopping verticals only — it was empty for
`crm software`, `meal kit delivery`, `car insurance quotes`, `best web hosting`, `mesothelioma lawyer`.

Real `related_searches` payload (`raw/g_crm.json`), showing the exact shape:

```json
{
  "block_position": 1,
  "query": "Crm software examples",
  "link": "https://www.google.com/search?sca_esv=…&q=Crm+software+examples&sa=X&ved=…",
  "serpapi_link": "https://serpapi.com/search.json?device=desktop&engine=google&gl=us&google_domain=google.com&hl=en&location=Austin%2CTexas%2CUnited+States&q=Crm+software+examples"
}
```

## B5. PAA in 2026 — the tree is effectively gone

**All 32 `related_questions` items across all 8 SERPs came back `"type": "ai_overview"`.** Zero
`featured_snippet`. The item carries only:

```
question, type, next_page_token, page_token, serpapi_link, serpapi_ai_overview_link
```

— **no `snippet`, no `link`, no `title`.** The answer body is not in the parent response any more.

I then spent 1 search calling `engine=google_related_questions` with a real `next_page_token` from
`raw/g_crm.json`. Result (`raw/rq_expand1.json`):

```json
{ "error": "Google Related Questions hasn't returned any results for this query." }
```

**Verdict: `google_related_questions` is dead weight for AI-Overview-backed PAA.** When `type` is
`ai_overview`, expansion has moved to `engine=google_ai_overview` via the separate `serpapi_ai_overview_link` /
`page_token`. AdWatch should:

- **Harvest the 4 question strings free** on every SERP call it already makes — they are perfectly good
  long-tail keyword candidates as-is.
- **Not build a PAA tree.** Level-2 expansion costs 1 search per node and, on today's SERPs, returns an error
  for the `google_related_questions` path.

(Errors are not billed — those 6 error calls cost me nothing, per <https://serpapi.com/pricing>.)

## B6. Ads — the finding that matters most for a paid-search product

Same query, same `location=Austin,Texas,United States`, same hour:

| query | `engine=google` → `ads` | `engine=google_ads` → `ads` |
|---|---:|---:|
| `crm software` | **0** | **6** (Pipedrive ×2, Zoho ×2, monday.com, Salesforce) |
| `espresso machine` | 0 | 1 (Nespresso) + 34 `shopping_results` |
| `car insurance quotes` | 0 | not tested |
| `best web hosting` | 0 | not tested |
| `mesothelioma lawyer` | 5 | not tested |

I pulled the raw scraped HTML for `car insurance quotes` (`search_metadata.raw_html_file`, free to fetch) and
grepped for `aclk|Sponsored|googleadservices|data-text-ad`: **zero hits**. Google genuinely served an ad-free
SERP to that scrape. For `mesothelioma lawyer` the same grep found 59 `aclk` + 5 `data-text-ad`. So
`engine=google` is not silently dropping ads it received — it simply receives them inconsistently.

`engine=google_ads` exists precisely for this. Doc (<https://serpapi.com/google-ads-api>):

> "Scrape sponsored results from Google search pages at a higher rate than the standard Google Search API."

Measured: `engine=google_ads` returned **`ads`, `ai_overview`, `discussions_and_forums`, `inline_videos`,
`organic_results`, `related_questions` (4), `related_searches` (8), `things_to_know`** — and on
`espresso machine` also `refine_this_search` (25), `shopping_results` (34), `immersive_products`,
`local_results`. It is a **strict superset** of what `engine=google` gave me, at the same 1-search price.
Its params: `q`, `location` (required), `hl`, `safe`, `nfpr`, `device`.

**Action: AdWatch should use `engine=google_ads` as its primary monitoring call, not `engine=google`.** Same
cost, better ad recall, all the same free keyword ride-alongs.

## B7. Google Trends measured

`data_type=RELATED_QUERIES`, `q=espresso machine`, `geo=US` (`raw/tr_espresso.json`) — **25 rising + 25 top =
50 strings for 1 search** (41 after normalising dupes across the two lists).

Rising list is genuinely a demand-emergence signal, and it is timely:

```
ninja luxe café premier series 3-in-1 espresso coffee & cold brew machine   Breakout   (+33,200)
alton brown espresso machine eggs                                          Breakout   (+7,300)
espresso machine arc raiders                                               +4,150%
breville oracle dual boiler espresso machine                               +750%
philips baristina automatic espresso machine                               +750%
fellow series 1 espresso machine                                           +700%
how to descale espresso machine                                            +450%
```

Note the shape: `value` is a **string** (`"Breakout"`, `"+4,150%"`, `"100"`) and `extracted_value` is the
integer. For `rising` the integer is a **percentage delta**; for `top` it is a **0–100 relative index**. These
are different units in the same field name — parse by list, not by field.

`data_type=TIMESERIES` with 3 comma-separated queries (`raw/tr_ts_crm.json`): 53 weekly points,
`interest_over_time.timeline_data[].values[].extracted_value` 0–100, plus `interest_over_time.averages[]`
(`crm software` 7, `espresso machine` 50, `meal kit delivery` 1). **Max 5 queries per call** for TIMESERIES
and GEO_MAP, 1 for the others (<https://serpapi.com/google-trends-api>) — so relative sizing costs
1 search per 5 keywords, and comparisons across calls require a shared pivot keyword.

`google_trends_trending_now`, `geo=US&hours=48` (`raw/tnow_us.json`), **1 search**:

- **864 trending queries**
- **276 of them carry `trend_breakdown[]`, totalling 914 additional query strings**
- ≈ **1,778 keyword strings for one search** — by far the highest raw yield in the API
- `search_volume` is bucketed, not continuous. Observed ladder across the 864:
  `500000×3, 200000×4, 100000×7, 50000×21, 20000×56, 10000×69, 5000×96, 2000×163, 1000×153, 500×133, 200×114, 100×45`
- `category_id=18` (Technology), `hours=168` narrowed it to **56 trends** — e.g. `chatgpt` vol 500,000 +100%,
  `gopro stock` vol 50,000 +100%, `sony ps5 tariff refund lawsuit` vol 5,000 +400%.

**This is the closest thing to volume in SerpApi and it is still not keyword volume** — it only covers queries
Google flagged as trending in the last N hours. For AdWatch it is an *emerging-query radar*, not a planner.

## B8. Google News measured — brand yes, category no

| call | results | verdict |
|---|---:|---|
| `q=Breville espresso machine` (`raw/news_breville.json`) | **100** | mixed; dates span 5 months despite relevance sort |
| `q="espresso machine" when:7d` (`raw/news_when7d.json`) | 37 | **noise** — top story was a baseball trade ("Tarik Skubal took espresso machine from Tigers locker room"), plus SEO-spam domains (`Krepšinio žinios`, `fuelcarmagazine.com`) |
| `q=Pipedrive when:30d` (`raw/news_pipedrive2.json`) | **7** | **high signal** |

The Pipedrive feed, verbatim:

```
08/26  PCMag                 Pipedrive CRM Review: Competent Contact Management, Pricey Automations
08/18  nny360.com            Pipedrive MCP Connector is Now Available in Claude's Official Marketplace
08/05  eagletribune.com      Pipedrive Acquires Outfunnel, Bringing Its Top-Rated Marketplace App Home
09/02  Small Business Trends  Best CRMs for Startups to Consider
08/29  Hostinger             11 powerful Mailchimp alternatives for your email marketing
```

An acquisition, a product launch, a review, and two comparison round-ups the competitor now ranks in. Every
one of those is a plausible precursor to a bidding-behaviour change. **That is a real paid-search signal.**

Field inventory (`raw/news_breville.json`, `jq paths(scalars)`):
`news_results[].{position,title,link,date,iso_date,thumbnail,thumbnail_small,source.name,source.icon,source.authors[]}`
plus `menu_links[]`. **No `snippet`** on `google_news` — if AdWatch wants snippet text for LLM classification
it must use `engine=google&tbm=nws` (<https://serpapi.com/news-results>) instead.

**Two hard gotchas, both measured:**

1. `q` + `so` together → `{"error":"`q` and `so` parameters can't be used together."}` (2 calls,
   `raw/news_pipedrive.json`, `raw/news_crm.json`). **You cannot date-sort a keyword news feed.** The only
   recency control for a `q` search is the `when:7d` / `when:30d` operator inside `q` itself. Confirmed
   working.
2. Relevance sort with no `when:` returns months-old articles interleaved with today's. Always pin `when:`.

**Verdict on item 4:** *category-level* news is noise and AdWatch should not spend searches on it.
*Competitor-brand-level* news is a genuine, cheap signal at 1 search per competitor per run.

## B9. Google Images measured

`engine=google_images&q=espresso machine` (`raw/img_espresso.json`), 1 search:

- `suggested_searches` — **33** items (`Commercial`, `Home`, `Delonghi`, `Professional`, `Barista`,
  `Coffee shop`, `Nespresso`, `Cafe`, `La marzocco`, `Automatic`, `Manual`, `Portable`, …). These are facet
  *fragments*, so cross-product them with the seed.
- `related_searches` — **12** full queries (`automatic espresso machine`, `commercial espresso machine`,
  `professional espresso machine`, `home espresso machine`, `manual espresso machine`, …)
- `images_results` — 100

**45 keyword strings for 1 search, of which 29 were new** after the ads/trends calls. Solid, and it works on
verticals where `refine_this_search` is empty. **INFERRED:** the facet vocabulary here overlaps heavily with
`refine_this_search`, so on shopping verticals it is partly redundant — sequence it after.

## B10. Ads Transparency Center — could not make `text` work

Three attempts, all errored (and therefore free):

```
text=pipedrive&region=2840  -> "Google Ads Transparency Center hasn't returned any results for this search."
text=pipedrive              -> same
text=nike                   -> same
```

**INFERRED:** the engine in practice needs an `advertiser_id`, and free-text advertiser resolution is either
broken or requires an exact legal-entity string. AdWatch would have to resolve and store `advertiser_id` per
competitor out-of-band before this engine is usable. Treat as **unvalidated** until an `advertiser_id` path is
tested.

---

# PART C — Proposed AdWatch features, ranked by value per search

## Tier 0 — FREE. Rides along on calls AdWatch already pays for.

These cost **zero additional searches**. They are parse-only changes.

| # | Feature | Engine + params | Change-event emitted | Marginal cost |
|---|---|---|---|---|
| **0.1** | **Switch monitoring to `engine=google_ads`** | `engine=google_ads&q=<kw>&location=<loc>&hl=en&device=desktop` | `advertiser.entered` / `advertiser.exited` / `ad.copy_changed` — with **measurably better recall** (6 ads vs 0 on `crm software`) | 0 (replaces the existing `google` call 1:1) |
| **0.2** | **Refinement-chip harvester** | parse `refine_this_search[]` off 0.1 | `category.facet_added` / `facet_removed` — Google changing its commercial taxonomy for the category is a leading indicator | 0 |
| **0.3** | **Related-searches drift monitor** | parse `related_searches[]` (always exactly 8) off 0.1 | `demand.related_query_added` / `dropped` — an 8-slot list that turns over run-over-run is exactly the diff AdWatch already computes | 0 |
| **0.4** | **PAA question harvester** | parse `related_questions[].question` (always exactly 4) off 0.1 | `demand.question_emerged` — feeds informational/top-funnel keyword sets | 0 |
| **0.5** | **Ad-density competition index** | `(.ads \| length)` + distinct advertiser domains, off 0.1 | `competition.density_changed` — the only competition proxy SerpApi can honestly support | 0 |
| **0.6** | **Shopping-price watch** (retail verticals) | parse `shopping_results[]` (34 items observed) off 0.1 | `competitor.price_changed` | 0 |

Tier 0 alone turns one existing paid call into **8 related searches + 4 questions + up to 25 facets + ad roster
+ price roster**, i.e. ~37–41 keyword strings and a competition reading, per keyword per run, for nothing.

## Tier 1 — 1 search each, high yield

| # | Feature | Engine + params | Change-event | Cost / watchlist / run |
|---|---|---|---|---|
| **1.1** | **Category emerging-query radar** | `engine=google_trends&data_type=RELATED_QUERIES&q=<seed>&geo=US` | `demand.rising_query` (Breakout / +N%) — 25 rising + 25 top per call | **1 per seed** |
| **1.2** | **Competitor news watch** | `engine=google_news&q=<BrandName> when:7d&gl=us&hl=en` (never `so`) | `competitor.launch` / `.funding` / `.acquisition` / `.promo` | **1 per competitor** |
| **1.3** | **Trending-now radar, category-scoped** | `engine=google_trends_trending_now&geo=US&hours=168&category_id=<n>` | `market.trend_spike` with bucketed `search_volume` + `increase_percentage` | **1 total per run**, shared across all customers in that category |
| **1.4** | **Relative-size ranking** | `engine=google_trends&data_type=TIMESERIES&q=<k1,…,k5>&geo=US&date=today 12-m` | `keyword.interest_shift`; use a fixed pivot keyword in slot 1 to make calls comparable | **1 per 5 keywords** |
| **1.5** | **Image-facet harvest** (verticals where `refine_this_search` is empty) | `engine=google_images&q=<seed>` | `demand.facet_discovered` — 45 strings measured | **1 per seed, onboarding only** |

## Tier 2 — buy last

| # | Feature | Cost | Why last |
|---|---|---|---|
| **2.1** | Alphabet-soup autocomplete expansion | 26/seed | 13.4 new/search — real volume, worst efficiency. Onboarding only, core seeds only. |
| **2.2** | Modifier-stem autocomplete | 8/seed | 11.2 new/search. Same. |
| **2.3** | Lens creative-reuse check | 1/image | Only if AdWatch stores competitor creative assets. |
| **2.4** | Ads Transparency Center | 1+/competitor | Blocked — `text=` search does not resolve (§B10). Needs an `advertiser_id` pipeline first. |

## Explicitly NOT recommended

| Anti-feature | Why |
|---|---|
| Rotating `client` across autocomplete values | Measured 1.0 new keyword/search. Nine times worse than alphabet soup. |
| Building a PAA tree via `google_related_questions` | All PAA is now `type: ai_overview`; the engine returned "hasn't returned any results". |
| Category-level news monitoring | Measured noise (baseball trades, SEO spam) at 1 search each. |
| Any "search volume" or "CPC" column sourced from SerpApi | **It does not exist.** SerpApi says so itself. |
| `engine=google_videos` for creative intel | Nothing the SERP's free `inline_videos` block doesn't give. |

---

## Source list

- <https://serpapi.com/google-autocomplete-api>
- <https://serpapi.com/google-autocomplete-clients>
- <https://serpapi.com/related-questions>
- <https://serpapi.com/google-related-questions-api>
- <https://serpapi.com/related-searches>
- <https://serpapi.com/refine-this-search>
- <https://serpapi.com/things-to-know>
- <https://serpapi.com/search-api>
- <https://serpapi.com/news-results>
- <https://serpapi.com/google-news-api>
- <https://serpapi.com/google-trends-api>
- <https://serpapi.com/google-trends-trending-now>
- <https://serpapi.com/google-ads-api>
- <https://serpapi.com/google-ads-transparency-center-api>
- <https://serpapi.com/google-images-api>
- <https://serpapi.com/google-lens-api>
- <https://serpapi.com/google-videos-api>
- <https://serpapi.com/pricing>
- <https://serpapi.com/blog/dataforseo-vs-serpapi/>

Raw evidence: `raw/*.json` (630 files in the shared session scratchpad; mine are prefixed
`ac_`, `g_`, `gads_`, `tr_`, `tnow_`, `news_`, `img_`, `adtc_`, `rq_`). Derived:
`expansion_all.txt` (479 keywords), `expansion_buckets.json`.
