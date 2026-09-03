# J — Onboarding redesign

**Date:** 2026-09-03
**Status:** Draft for review
**Supersedes:** the four-step wizard at `/onboarding`
**Subsumes:** K (generalising the coffee gate)

---

## The problem

Onboarding asks for what the user is least able to supply. Today it wants a vertical from
a hardcoded list of eight, then three-plus competitor *domains* typed from memory, then
keywords. Someone who knows all of that does not need this product.

It also contradicts itself. `onboarding/page.tsx:10` offers eight verticals; Divya's
`GET /coffee/keywords` serves one and rejects the other seven with *"This endpoint covers
coffee-related searches only."*

## The shape

Three fields — **company name, website, description** — and Claude reads the site.

```
name / website / description
        │
        ▼  web_fetch, allowed_domains pinned to the submitted domain
   extract, strict schema
        │
        ├── vertical      → a Google Trends category ID (closed set of 1,133)
        ├── keywords      → kept automatically
        ├── assets        → brand, owned properties, catalogue
        └── competitors   → PROPOSED, shown for confirmation
                              │
                              ▼  each kept domain verified against Ads Transparency
                           watchlist created, user's own domain tracked as `self`
```

### Why the human confirms only competitors

A wrong keyword is cheap and self-evident: it returns an empty paid block on the first
run and gets deleted. A wrong competitor is expensive and sticky — it burns a SerpApi
search every run forever and quietly skews share-of-voice, while looking entirely
legitimate in the UI. Put the confirmation where the cost is, not everywhere.

---

## Decisions already settled

| | |
|---|---|
| Subject | The user's **own** company. Their domain is tracked as `self`, so every SERP read answers "where am I versus them" rather than only "what are they doing" |
| Vertical | A **classification** into Google's published Trends taxonomy, not a generated string |
| Verification | Every competitor domain checked against Ads Transparency **before** it is persisted |
| Assets | All four: brand assets, owned properties, their own creatives, product/catalogue |
| Keys | Platform by default, BYO to lift the quota — already built (F) |
| Trust model | **C, hybrid**: auto for vertical/keywords/assets, confirm for competitors |

### Classification, not generation

Claude picks one ID from Google's 1,133-node Trends taxonomy. That turns an unverifiable
output into a checkable one: the ID either exists in the enumeration or it does not, and
it feeds straight into `cat=` on every subsequent trends query for the watchlist.

This is what replaces `COFFEE_TERMS`. The gate — `is_coffee()`, the regex, and the
off-market rejection at `coffee/engine.py:181` — becomes dead code. The engine underneath
(ValueTrack macro extraction, advertiser counting, the local/informational/commercial
ladder) is entirely vertical-agnostic and is kept.

### Prompt injection is a first-class concern, not a footnote

The page being fetched is written by a third party and lands in the model's context.

- `allowed_domains` pinned to the submitted domain, so injected links cannot redirect the
  fetch elsewhere.
- `max_content_tokens` capped, so a hostile page cannot exhaust the budget.
- Output constrained to a strict schema — a category ID from the enumeration, a list of
  domains, a list of keywords. **Page content is data, never instructions.**
- Nothing extracted is executed, and every domain is verified against a second source
  before it is persisted.

This is the discipline `analyst.py` already states: *"the model only sees the supplied
changes. It must not invent metrics."*

---

## Schema

Three gaps, all additive — `init_db()`'s `create_all` plus the existing `ADD COLUMN IF
NOT EXISTS` block covers them.

**`competitors`** gains:

```python
is_self: Mapped[bool] = mapped_column(Boolean, default=False)  # the user's own domain
```

Read models must exclude `is_self` rows from "competitor" counts but include them in
share-of-voice, or the user appears as their own competitor.

**`watchlists`** gains:

```python
trends_category_id: Mapped[int | None]   # Google Trends taxonomy node; `vertical` stays the human label
company_domain:     Mapped[str | None]
company_description: Mapped[str | None]  # what Claude was given, kept so a re-run is reproducible
```

**New `company_assets`** — one row per extracted fact, rather than a wide table, because
the four kinds have nothing in common and more will follow:

```python
watchlist_id · kind · key · value · source_url · created_at
# kind: brand | property | catalogue        (creatives reuse the Creative table)
# e.g. brand/primary_color/#B5121B · property/landing_page//subscriptions
```

Their own creatives need **no new table** — they are `Creative` rows against the `is_self`
competitor, which means `creative_launched` fires on the user's own ads for free.

---

## API

```
POST /onboarding/analyze   {name, domain, description}
  → {vertical: {id, name}, keywords: [...], assets: [...],
     competitors: [{domain, name, reason}]}          ← proposed, nothing persisted

POST /onboarding/create    {name, domain, description, vertical_id,
                            keywords: [...], competitors: [domain, ...], assets: [...]}
  → {watchlist_id, competitors: [{domain, verified}], skipped: [...]}
```

Two calls, deliberately. `analyze` spends Anthropic tokens and no SerpApi quota; `create`
spends one Ads Transparency search per kept competitor. Splitting them means the user
sees the proposal before any quota is spent, and a slow verification pass does not hold
the analysis screen.

`create` returns which domains were **skipped** and why. Silently dropping a domain the
user explicitly kept would be worse than telling them.

### Cost

| | SerpApi | Anthropic |
|---|---|---|
| `analyze` | 0 | one call, one page fetched |
| `create` | 1 per kept competitor | 0 |

Both are metered through the `llm_calls` ledger (B) with `feature="onboarding"`, so the
dashboard shows what onboarding costs — likely the highest-volume Claude path once this
ships.

---

## Frontend

`/onboarding` becomes two screens.

1. **One form** — name, website, description. Submit runs `analyze`.
2. **Review** — vertical and keywords shown as accepted with an edit affordance; the
   competitor list as checkboxes with Claude's one-line reason each. The user's own domain
   is pinned at the top, labelled *you*, and cannot be unchecked. Confirm runs `create`,
   then redirects to the watchlist.

The vertical is a **typeahead over the 1,133-node taxonomy**, shipped as a static JSON
asset — no API call. Pre-filled with Claude's pick, one click to change. The correction is
logged, because that log is the eval set for the classifier and it is ground truth nobody
had to invent.

CSV import (`POST /watchlists/import.csv`) stays as the power-user path.

---

## Testing the classifier

Four layers, cheapest first:

1. **Structural, in code** — the returned ID exists in the taxonomy. Deterministic, no
   model judgment, catches a hallucinated ID outright.
2. **Hierarchical tolerance, in tests** — assert the node is in the right *subtree*, not an
   exact match. A coffee roaster landing on Food & Drink (71) or Grocery & Food Retailers
   (121) are both defensible; asserting equality gives a test that fails on a correct answer.
3. **Golden set in CI** — 15–20 description→subtree pairs against recorded fixtures, not
   live Claude. Catches regressions when the prompt or model changes.
4. **Empirical, in production** — a wrong vertical produces a flat or empty Trends series.
   That is a real signal, and it is alertable.

---

## Non-goals

- Replacing the CSV import.
- Reading anything behind a login on the company's site.
- Inferring competitors from anywhere but the page and the model's own knowledge —
  no crawling beyond the submitted domain.
- Migrating existing watchlists. `trends_category_id` stays null for them and the
  keyword engine falls back to today's behaviour.

---

## Open questions

1. **Where does the Trends taxonomy live?** A committed JSON asset is simplest and needs
   no network, but goes stale silently. A build-time fetch stays current and adds a
   failure mode. Assumed: committed, with the fetch date recorded in the file.
2. **Does `analyze` cache per domain?** Re-running onboarding for the same site currently
   costs another Claude call and another page fetch. A short TTL cache would make the
   review screen's "re-analyse" free. Assumed: no cache in v1.
3. **What happens when the site is unreachable?** Fall back to classifying from the
   description alone, with the UI saying the site could not be read — or refuse? Assumed:
   fall back, and say so.
