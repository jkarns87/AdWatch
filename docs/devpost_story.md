## Inspiration

Every paid-search team does the same ritual: once a week, someone opens the Google Ads Transparency Center for a handful of competitors, searches their own keywords in an incognito window, checks Google Trends, and pastes screenshots into a deck. It's slow, it's retrospective, and it has no concept of *change* — you see a snapshot, not a signal. Incumbent competitive-intelligence suites cost hundreds of dollars a seat and still hand you a report, not an alert. We wanted the thing we actually needed: a monitor with an analyst attached.

## What it does

You give AdWatch a **watchlist** — competitor domains and the keywords you care about. On a schedule (or on demand) it collects three live signals through **SerpApi**:

- every creative each competitor is currently running in Google Ads (via the **Ads Transparency Center** engine, with first/last-shown dates),
- the live paid block on each of your keywords in **Google Search** (who's bidding, in what position, top or bottom),
- **Google Trends** interest-over-time plus rising related queries for the category.

Each run is **diffed against the last**. The diff engine emits typed change events — a creative launched or dropped, a creative surge, a new advertiser appearing on your keyword, a position shift, a demand spike, a breakout query — each with a severity. An **AI analyst (Claude)** reads only the structured diff and writes a plain-English insight: what happened, why it matters, and two or three concrete actions with effort and urgency. Insights above your severity threshold fan out to your team's chat or email.

The result is a Monday-morning brief that was written at 6 AM: *"Competitor B launched four video creatives overnight; a new advertiser took position one on 'meal kit for two'; that query is breaking out and no tracked competitor owns it yet — ship a two-person landing page this week."*

## How we built it

**Control plane on Xano** — authentication, workspaces and membership, alert preferences, alert fan-out with a delivery log, and the 6-hourly scheduler that kicks off collection. Sixteen XanoScript files, validated with the Xano Developer MCP.

**Data plane in Python** — FastAPI + Postgres: SerpApi collectors with response caching (to respect quota), pure-function normalizers, a unit-tested diff engine with nine change kinds, a Claude analyst with a strict JSON contract and an honest fallback, and a synthetic seed so the whole pipeline runs with zero quota during development. The data plane introspects Xano bearer tokens, so it never stores a password or issues a token itself.

**Dashboard in Next.js** — insight feed, change timeline, per-competitor creative grid, per-keyword paid-block table with share of voice, and a demand sparkline. One button: *Collect now*.

Everything ships as non-root containers with GitHub Actions CI on every push and a one-command deploy, so it runs on any cloud. Three people, about twenty-two hours.

## Where SerpApi does the core work — and why

SerpApi *is* the sensor. Three engines feed the product: Google Ads Transparency Center (every live creative per advertiser), Google Search (the live paid block per keyword), and Google Trends (interest over time and rising queries). Without structured, real-time access to that public data there is no diff, and without the diff there is nothing for the AI to analyze — the "AI experience" here is only as good as the freshness of the signal. The AI analyst reasons *exclusively* over diffs of SerpApi data and is not allowed to invent numbers.

## Xano build story

- **What software did we replace?** The weekly manual competitor check paid-search teams run across an incumbent competitive-intelligence suite and a spreadsheet.
- **Why?** It's retrospective, expensive per seat, and has no notion of *change* — you get a report, not an alert.
- **Which AI tools?** Claude (Cowork and Code) for planning, scaffolding, the diff engine, and the analyst model; the Xano Developer MCP for XanoScript docs and validation.
- **How long?** About twenty-two hours.
- **What would have taken significantly longer without AI + Xano?** The entire control plane — auth, tenancy, alert preferences, fan-out with delivery logging, and the scheduler — was written and validated in under an hour; the diff engine, analyst prompt, and dashboard were scaffolded in the first two.

## Challenges we ran into

Quota discipline: 250 free searches a month meant a local response cache, a synthetic seed dataset with fictitious advertisers, and live calls only for real runs. Making the AI useful rather than chatty: structured diff in, strict JSON out, no invented metrics, one insight per competitor or keyword cluster. Making the first run not look like "everything changed": baselines produce zero events by design.

## Accomplishments that we're proud of

A real change feed over real public data, with an analyst that recommends actions instead of describing charts. A clean control-plane / data-plane split where each half does what it's best at. CI green from the first commit.

## What we learned

The interesting product isn't the dashboard — it's the *diff*. Once changes are typed events with severity, everything downstream (AI analysis, alerting, scheduling) becomes simple.

## What's next for AdWatch

Own-account overlay (import your campaign reports to see spend against competitor moves), more channels, per-workspace schedules and quiet hours, a Terraform module, and per-seat pricing at a fraction of incumbent suites.
