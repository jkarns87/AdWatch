# Devpost submission — checklist + copy

**RULE: no third-party company or brand names as competitors, incumbents, or example advertisers.** Use category language for those. **Google** (Google Ads, Ads Transparency Center, Google Trends), **hackathon sponsors** (SerpApi, Xano), our own stack, and integration destinations (Slack, Microsoft Teams, Discord) are safe to name — confirmed by Joey.

Full story copy to paste into Devpost: **`docs/devpost_story.md`** (rewritten 2026-09-03 against verified production numbers).

## Checklist (target submit 9:00 AM Thu 2026-09-03 local)

- [ ] Every team member registered on Devpost and added to the project (editing rights) — *only you can do this*
- [x] Project name: **AdWatch**
- [x] Elevator pitch (≤ 200 chars) — below, 186 chars
- [x] Full story — `docs/devpost_story.md`, real numbers, no placeholders
- [x] Built with (tags): `python`, `fastapi`, `postgresql`, `nextjs`, `typescript`, `tailwindcss`, `docker`, `github-actions`, `fly-io`, `serpapi`, `xano`, `claude`, `anthropic`
- [x] Screenshots: 8 captured from the **deployed** app, signed in as the demo account — `docs/screenshots/01..08`
- [x] Project URL: **https://adwatch.dev** (200, TLS, custom domain)
- [x] API URL: **https://api.adwatch.dev/api/v1/health** (200)
- [x] Repo URL: **https://github.com/jkarns87/AdWatch** — public
- [ ] Video 2–4 min (SerpApi: "end-to-end"; Xano: build story) — script in `DEMO_SCRIPT.md`; *only you can do this*
- [x] Sponsor challenges: **SerpApi – Best AI Use Case**, **Xano – Rebuild a SaaS Tool You Hate** (control plane shipped: 26 XanoScript files)
- [x] SerpApi line: "where SerpApi performs core work and why" — in the story, with live cost numbers
- [x] Xano build story answers — in the story
- [ ] Accept terms → **Submit to Hackathon** → confirm status shows *Submitted*
- [ ] Nobody edits after 9:30 AM

## Verified numbers (pulled from production 2026-09-03 06:47Z)

> **Post-submission note.** These are the figures as submitted and are left unedited as
> the record of what was sent. They are also **understated**, because they were collected
> while two of the three collectors silently returned nothing: the Ads Transparency
> normalizer matched a field name the engine does not send, and the keyword collector
> queried `engine=google`, whose paid block is empty on commercial queries. Both were
> found and fixed after submission — see `docs/research/README.md`. On the same demo
> watchlist afterwards: 248 creatives and 35 typed changes in a single run, against 29
> and 75 cumulative here. Do not reuse these numbers as current.

Real, SerpApi-backed workspaces only — the synthetic demo workspace is excluded so
nothing here is inflated by seeded data.

| | |
|---|---|
| Runs / SerpApi searches spent | 12 / 94 |
| Creatives tracked | 29 |
| Paid-block placements captured | 38 |
| Trend points | 1,618 |
| Typed changes detected | 75 |
| Insights written | 21 |
| Claude calls that reached the model | 10 (9,824 in / 6,658 out tokens, $0.0862) |
| SerpApi spend to date | $0.94 |
| Projected month — naive cadence | $21.60 |
| Projected month — plan cadence | $4.41 (~5x saving) |
| XanoScript files | 26 (15 api, 6 table, 2 function, 2 task) |
| Python modules / passing tests | 57 / 246 |
| Web routes / Playwright specs | 11 / 6 |
| Commits | 50 |

Re-pull before submitting if more runs happen: `GET /api/v1/usage`.

## Demo account for judges

Created off the public signup endpoint and seeded **live** from `seed/demo_config.json`:
three real US coffee advertisers, collected through SerpApi, so the creatives, paid
blocks and insights are all real rather than fabricated. The advertisers are the
*subjects* being monitored — they are not named anywhere in the story as competitors of
ours or as incumbents, which is what the rule at the top of this file governs.

Seeding this way spends quota (~15 searches a run) and the synthetic mode remains
available at zero cost via `{"mode": "synthetic"}`.

```
https://adwatch.dev
demo@adwatch.dev / AdWatchDemo2026!
```

Worth adding to the Devpost "Try it out" notes so judges can sign in rather than only
watch the video. Re-seed any time with `POST /api/v1/demo/reset` then `/api/v1/demo/seed`
using that account's token.

## Elevator pitch (186 chars)

> An always-on competitive-intelligence analyst for paid search. AdWatch tracks every ad your rivals run and every keyword they bid on, then tells you what changed and what to do about it.

## SerpApi one-liner

> SerpApi is the sensor layer: its Google Ads Transparency Center, Google Search, and Google Trends engines are the only source of every change AdWatch detects — the AI analyst reasons *exclusively* over diffs of SerpApi data.

## Screenshot shot list (what judges should see)

Capture from **https://adwatch.dev** signed in, at 1440×900, light theme unless noted:

1. **Dashboard (`/`)** — ops overview: SerpApi health card showing a valid key and remaining quota, Anthropic burn, alert cards. This is the "cost is a first-class object" shot.
2. **Watchlist detail (`/watchlists/[id]`)** — insight feed with an AI insight expanded, showing what changed → why it matters → recommended actions.
3. **Creative grid** — per-competitor creatives with first/last-shown dates, including one that has stopped.
4. **Usage & plan (`/usage`)** — the naive-vs-plan cadence projection side by side. The 5× saving is the whole cost story in one image.
5. **Alerts inbox (`/alerts`)** — severity filters and read state, proving alerts are a product object not just a webhook.
6. **Onboarding (`/onboarding`)** — the review screen after Claude reads a company site and proposes category, keywords and competitors.
7. **Integrations (`/settings/integrations`)** — destinations with per-destination severity thresholds.
8. *(optional)* Dark theme of the dashboard, to show theming.
9. *(optional)* Xano UI — tables + API group + the two scheduled tasks, for the Xano challenge.

## Talking points for the video

- **Onboarding is the hook.** Company name and website in; Claude reads the site and proposes the whole watchlist. Show this first — it's the fastest path from nothing to value.
- **The diff is the product.** Not a dashboard of charts: typed change events with severity, which is what makes AI analysis, alerting and scheduling all simple downstream.
- **Data stays in the platform.** The inbox is served by the control plane with read state, severity filters and deep links. Chat integrations extend it; they aren't the product.
- **Budgeting is built in.** Every SerpApi call is one search; every run records what it spent; the Usage page prices the month and projects it two ways. $21.60 naive vs $4.41 at plan cadence, live.
- **Bring your own keys.** Per-workspace Anthropic and SerpApi keys, encrypted at rest, validated on save — the customer's spend is theirs.
- **Multi-tenant from day one.** Workspaces, roles, per-workspace destinations and plan, all pushed from code.
- **Verified, not assumed.** The scheduler was confirmed by watching it fire in production; the cost numbers come from the live ledger.
