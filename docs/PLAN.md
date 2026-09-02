# AdWatch — 24-hour build plan

**Hard deadline: Thursday, Sept 3, 2026 @ 10:00 AM PDT.** Late = rejected, no exceptions.
**Target submit time: 9:00 AM.** Nothing gets edited after 9:30.

Judging (Overall, Round 1): **Progress** (how much did you build), **Concept** (real problem?), **Feasibility** (could this be a company?). Sponsor judges (SerpApi, Xano) pick their own winners separately.

Top 5 → phone call at 1:00 PM → onsite at 2:00 PM → 3-minute main-stage demo at 2:30 PM. Everyone is onsite, so a rehearsable live demo is a first-class deliverable, not an afterthought.

## Scope — what v1 IS and ISN'T

**IS:** competitor ad intelligence for one vertical. Add competitors + keywords → AdWatch pulls their live Google ads (Ads Transparency Center), the paid results on your keywords (Google Search `ads` block), and category demand (Google Trends) → diffs each run against the last → Claude writes an insight with recommended actions → alerts.

**ISN'T:** managing your own Google Ads account (API dev-token approval takes days), bid automation, multi-channel (Meta/TikTok), billing, team roles. If it isn't in the demo script, it isn't in v1.

## Lanes

| Lane | Owner | Deliverable |
|---|---|---|
| **A — Frontend** | Joey (@jkarns87) | Dashboard: watchlist list, watchlist overview (insight feed, change timeline, competitor creative grid, keyword share-of-voice table, trend sparkline). Built against `docs/API_CONTRACT.md` from minute one. |
| **B — Backend** | @divya2030 @semmaguptam | Postgres schema, SerpApi collectors, snapshot storage, diff engine, Claude analyst, seed script, `/collect` + `/analyze` endpoints. |
| **C — Infra** | Joey (@jkarns87), background | Docker Compose, CI on push, one public deploy URL for Devpost, `.env` hygiene. |
| **D — Xano control plane** | Joey (@jkarns87), time-boxed | Auth + workspaces + watchlist CRUD + alert prefs in Xano; Next.js static hosting on Xano. **Cut-line 6:00 PM.** |
| **E — Submission** | Whoever is least blocked | Devpost story, screenshots, video, README polish. Starts by 9:00 PM regardless of feature state. |

## Timeline (PDT)

| Time | Milestone |
|---|---|
| **Wed 10:30–11:30** | Everyone: `make up` green locally. Keys in `.env`. GitHub repo public, CI running. Xano account created (coupon applied), CLI pushing enabled. Agree the API contract — any change after this is a PR with a note. |
| **11:30–14:00** | B: schema + `serpapi_client` + `/collect` writing raw snapshots and normalized creatives/serp_ads/trend_points. A: dashboard shell with mocked API responses from the contract. C: Dockerfiles, CI green. |
| **14:00–16:00** | B: diff engine (unit-tested, pure functions) + Claude analyst + `/analyze`. A: wire real API, insight feed + change timeline live. C: pick deploy target, first deploy. |
| **16:00–18:00** | D: Xano auth + watchlist CRUD; Next.js login → Xano JWT → API. **18:00 checkpoint: Xano works end-to-end or it's cut** (watchlist tables already exist in Postgres as fallback). B: alerts (webhook → Slack/Discord/email). |
| **18:00–21:00** | Polish. Trend panel, share-of-voice, creative thumbnails. Deployed URL works. Run live `collect` #1 on the demo watchlist. |
| **21:00–23:00** | E: Devpost story, screenshots from deployed app, README. Run live `collect` #2 so real diffs + insights exist. Rehearse demo once. |
| **23:00–01:00** | Bug bash only. Feature freeze at 01:00. |
| **01:00–06:00** | **Sleep.** You're demoing on a stage at 2:30 PM. |
| **06:00–07:30** | Smoke test deployed app. Record demo video (2–4 min: SerpApi wants "end-to-end", Xano wants a build story voiceover). |
| **07:30–09:00** | Devpost: video uploaded, screenshots, story, tech tags, sponsor challenges checked (Overall + SerpApi + Xano), repo link, live URL. **Submit at 9:00.** |
| **09:00–10:00** | Buffer. Verify submission shows as submitted. Don't touch it after 9:30. |
| **10:00–12:00** | Judging. Rehearse the 3-minute demo twice. |
| **13:00** | Phone call window. **14:00** be at the stage if called. |

## SerpApi quota budget (free tier: 250 searches/month, 50/hour)

Each collector call = 1 search. A watchlist with 3 competitors + 5 keywords costs:
- 3 × ads_transparency + 5 × google search + 5 × trends (TIMESERIES) + 5 × trends (RELATED_QUERIES) = **18 searches per collect run**.

Budget: 2 live runs for demo data (36) + dev testing (~60) + safety margin ≈ 100. Fine. Rules to stay under:
1. `make seed` uses **synthetic** data — zero quota. Develop against that.
2. The API caches every SerpApi response in `snapshots.raw`; the client also has a local disk cache keyed by params (`.cache/serpapi/`). Re-running the same query within an hour costs nothing on SerpApi's side either (cached searches are free) — but don't rely on it.
3. Only `make collect` hits SerpApi. Never wire the dashboard to call SerpApi directly.
4. If we blow through 250, the $25 Starter plan (1,000 searches) is the fallback — decide by 4 PM.

## Cut order if we're behind (cut from the top)

1. Xano control plane (→ Postgres tables, already there)
2. Email alerts (keep webhook)
3. Trend panel (keep creatives + SERP diff — that's the story)
4. Creative thumbnails (show text rows)
5. Deployed URL (fall back to local demo + video) — *last resort; Devpost wants a URL*

## Definition of done for the demo

- [ ] Open dashboard → watchlist "Meal Kit Delivery" (or chosen vertical) shows ≥3 competitors with live creatives
- [ ] Change timeline shows ≥1 `creative_launched`, ≥1 `new_serp_advertiser`, ≥1 `trend_spike` from real runs
- [ ] Insight feed shows Claude-written insight with 2–3 recommended actions per change cluster
- [ ] Clicking "Collect now" on stage completes in < 30s and produces at least one new change (pre-warm: run collect 5 min before demo so SerpApi's cache is hot)
- [ ] Alert fires to a Slack/Discord channel visible on the second screen
- [ ] Deployed URL loads over conference Wi-Fi; local Docker fallback ready on the laptop
