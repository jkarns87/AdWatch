# Devpost submission — checklist + copy

**RULE: no third-party company or brand names anywhere in the pitch, tags, or story.** Use category language for competitors, incumbents, and example advertisers. **Google** (Google Ads, Ads Transparency Center, Google Trends) and **hackathon sponsors** (SerpApi, Xano) are safe to name — confirmed by Joey.

## Checklist (target submit 9:00 AM Thu)

- [ ] Every team member registered on Devpost and added to the project (editing rights)
- [ ] Project name: **AdWatch**
- [ ] Elevator pitch (≤ 200 chars) — below
- [ ] Full story — below, filled in with real numbers
- [ ] Built with (tags): `python`, `fastapi`, `postgresql`, `nextjs`, `typescript`, `tailwindcss`, `docker`, `github-actions`, `serpapi`, `xano`, `claude`, `anthropic`
- [ ] Screenshots: watchlist overview, insight card, change timeline, creative grid, alert in chat channel (≥ 4, taken from the *deployed* app)
- [ ] Project URL: deployed dashboard
- [ ] Repo URL: public GitHub repo, README has setup steps that work from a clean clone
- [ ] Video 2–4 min (SerpApi: "end-to-end"; Xano: build story) — script in `DEMO_SCRIPT.md`
- [ ] Sponsor challenges ticked: **SerpApi – Best AI Use Case**, **Xano – Rebuild a SaaS Tool You Hate** (only if the control plane shipped)
- [ ] SerpApi line: "where SerpApi performs core work and why"
- [ ] Xano build story answers (see `XANO.md`)
- [ ] Accept terms → **Submit to Hackathon** → confirm the status shows *Submitted*
- [ ] Nobody edits after 9:30 AM

## Elevator pitch

> AdWatch is an always-on competitive-intelligence analyst for paid-search teams: it watches every ad your competitors run, every keyword they bid on, and every shift in category demand — then tells you what changed, why it matters, and what to do next.

## Story (draft — replace bracketed bits)

**Inspiration.** Every paid-search team does the same ritual: once a week, someone opens the ad transparency pages for a handful of competitors, searches their own keywords in an incognito window, checks a trends chart, and pastes screenshots into a deck. It's slow, it's retrospective, and it has no concept of *change* — you see a snapshot, not a signal. Incumbent competitive-intelligence suites cost hundreds of dollars a seat and still hand you a report, not an alert. We wanted the thing we actually needed: a monitor with an analyst attached.

**What it does.** You give AdWatch a watchlist — competitor domains and the keywords you care about. On a schedule (or on demand) it collects three live signals through SerpApi: every creative each competitor is currently running in Google Ads (via the Ads Transparency Center), the paid results on each of your keywords in Google Search, and Google Trends interest-over-time plus rising related queries for the category. Each run is diffed against the last. The diff engine emits typed changes — a creative launched or dropped, a new advertiser appearing on your keyword, a position shift, a demand spike, a breakout query. An AI analyst (Claude) reads the structured diff and writes a plain-English insight: what happened, why it matters, and two or three concrete actions with effort and urgency. High-severity insights fire a webhook to your team's chat.

**How we built it.** Control plane on Xano — auth, workspaces, watchlist configuration, alert preferences, and dispatch. Data plane in Python (FastAPI + Postgres): SerpApi collectors with response caching, a pure-function diff engine with unit tests, a Claude analyst with a strict JSON contract, and a Next.js dashboard. Everything ships as containers with CI on every push and a one-command deploy, so it runs on any cloud. [N] people, [22] hours.

**Where SerpApi performs core work and why.** SerpApi *is* the sensor. Three engines feed the product: the Google Ads Transparency Center engine (every live creative per advertiser, with first/last-shown dates), the Google Search engine (the live paid block per keyword — who's bidding, in what position), and the Google Trends engine (interest over time + rising queries). Without structured, real-time access to that public data there is no diff, and without the diff there is nothing for the AI to analyze — the "AI experience" here is only as good as the freshness of the signal.

**Challenges.** Quota discipline (250 free searches → local response cache + synthetic seed data for development, live calls only for real runs); making the AI useful rather than chatty (structured diff in, strict JSON out, no invented numbers); making first-run baselines not look like "everything changed."

**Accomplishments.** [Real numbers: X creatives tracked across Y competitors, Z changes detected, N insights, deployed URL, CI green.]

**What we learned.** [1–2 honest sentences.]

**What's next.** Scheduled runs per workspace, own-account performance overlay (import your own campaign reports to see spend against competitor moves), more channels, Terraform module, per-seat pricing at a fraction of incumbent suites.

## SerpApi one-liner

> SerpApi is the sensor layer: its Google Ads Transparency Center, Google Search, and Google Trends engines are the only source of every change AdWatch detects — the AI analyst reasons *exclusively* over diffs of SerpApi data.
