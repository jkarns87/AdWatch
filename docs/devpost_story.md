## Inspiration

Every paid-search team does the same ritual: once a week, someone opens the Google Ads Transparency Center for a handful of competitors, searches their own keywords in an incognito window, checks Google Trends, and pastes screenshots into a deck. It's slow, it's retrospective, and it has no concept of *change* — you see a snapshot, not a signal. Incumbent competitive-intelligence suites cost hundreds of dollars a seat and still hand you a report, not an alert. We wanted the thing we actually needed: a monitor with an analyst attached.

## What it does

You tell AdWatch your company name and website. Claude reads the site and proposes your category, your keywords, your likely competitors and your own brand assets — so a **watchlist** takes about a minute to create instead of an afternoon of research.

From then on, on a schedule or on demand, AdWatch collects three live signals through **SerpApi**:

- every creative each competitor is currently running in Google Ads (via the **Ads Transparency Center** engine, with first/last-shown dates),
- the live paid block on each of your keywords in **Google Search** (who's bidding, in what position, top or bottom),
- **Google Trends** interest-over-time plus rising related queries for the category.

Each run is **diffed against the last**. The diff engine emits typed change events — a creative launched or dropped, a creative surge, a new advertiser appearing on your keyword, a position shift, a demand spike, a breakout query — each with a severity. An **AI analyst (Claude)** reads only the structured diff and writes a plain-English insight: what happened, why it matters, and two or three concrete actions with effort and urgency. Insights land in your workspace's alert inbox and fan out to Slack, Microsoft Teams, Discord, email or a plain webhook, each at its own severity threshold.

The result is a Monday-morning brief that was written at 6 AM: *"Competitor B launched four video creatives overnight; a new advertiser took position one on 'meal kit for two'; that query is breaking out and no tracked competitor owns it yet — ship a two-person landing page this week."*

Because every run is stored, the history is queryable too: how long each creative actually flew, and how positions on a keyword moved run over run. An advertiser absent from a run gets no data point rather than a zero, so a chart draws a gap instead of a false drop to position one.

## How we built it

**Control plane on Xano** — authentication, workspaces and membership, watchlist configuration, alert preferences, alert fan-out with a delivery log, password reset, and the scheduled tasks that drive collection and housekeeping. Twenty-six XanoScript files, all pushed from the repo with the Xano CLI, so the control plane is version-controlled source rather than clicks in a UI.

**Data plane in Python** — FastAPI + Postgres across 57 modules: SerpApi collectors with response caching, pure-function normalizers, a unit-tested diff engine, a Claude analyst with a strict JSON contract and an honest deterministic fallback, and a synthetic seed so the whole pipeline runs with zero quota during development. **238 tests pass on every push.** The data plane introspects Xano bearer tokens, so it never stores a password or issues a token itself.

**Dashboard in Next.js** — eleven routes: ops dashboard, watchlists, per-watchlist insight feed and change timeline, creative grid, per-keyword paid block with share of voice, demand sparkline, alerts inbox, usage and plan, integrations, and guided onboarding. Light/dark/system theming throughout, with Playwright end-to-end tests that stub both planes.

**Operational from day one.** Bring-your-own API keys per workspace, encrypted at rest with Fernet and validated on save, so a customer's Anthropic and SerpApi spend is theirs. Every Claude call is metered into a ledger with its cost frozen at write time, and models we don't have a price for are recorded unpriced rather than silently counted as free. Snapshot payloads are pruned on a retention window so the one table with unbounded growth stays bounded — while the row survives, because it's the audit trail proving a fetch happened.

Everything ships as non-root containers with GitHub Actions CI on every push and a one-command deploy, running on Fly behind a custom domain with TLS. Three people, about twenty-two hours.

## Where SerpApi does the core work — and why

SerpApi *is* the sensor. Three engines feed the product: Google Ads Transparency Center (every live creative per advertiser), Google Search (the live paid block per keyword), and Google Trends (interest over time and rising queries). Without structured, real-time access to that public data there is no diff, and without the diff there is nothing for the AI to analyze — the "AI experience" here is only as good as the freshness of the signal. The AI analyst reasons *exclusively* over diffs of SerpApi data and is not allowed to invent numbers.

Quota is treated as a product constraint, not an afterthought. Each call is one search; each run records what it spent; the Usage page prices the month to date and projects it two ways. On our live workspace that's **$21.60/month at the naive "collect everything every six hours" cadence against $4.41 at the plan cadence** — a ~5× saving with the same alerts, because creatives change daily and category demand moves weekly. A live SerpApi health check on the dashboard shows key validity and remaining quota before a run ever spends anything.

## Xano build story

- **What software did we replace?** The weekly manual competitor check paid-search teams run across an incumbent competitive-intelligence suite and a spreadsheet.
- **Why?** It's retrospective, expensive per seat, and has no notion of *change* — you get a report, not an alert.
- **Which AI tools?** Claude (Cowork and Code) for planning, the diff engine, the analyst model, and the onboarding site-analysis; Claude also drove the XanoScript itself.
- **How long?** About twenty-two hours.
- **What would have taken significantly longer without AI + Xano?** The entire control plane — auth, tenancy, alert preferences, fan-out with delivery logging, password reset and the schedulers — is twenty-six XanoScript files pushed from the repo. Writing that as a bespoke service, with migrations and a token story, would have consumed the whole budget on plumbing instead of on the diff engine that actually makes the product.

## Challenges we ran into

**Quota discipline.** 250 free searches a month meant a local response cache, a synthetic seed with fictitious advertisers, and live calls only for real runs.

**Making the AI useful rather than chatty.** Structured diff in, strict JSON out, no invented metrics, one insight per competitor or keyword cluster.

**Making the first run not look like "everything changed."** Baselines produce zero events by design.

**Generalising beyond the demo vertical.** The keyword engine's guard against drifting into an adjacent market ("espresso machine" must not drag it into "machine learning") was originally five hand-curated term lists, which covered the seeded verticals and nothing else — a watchlist created from onboarding had no guard at all. It now derives its vocabulary from the watchlist's own keywords, so a mattress company fences itself without borrowing a coffee company's words.

**Trusting the right evidence.** Several bugs were invisible to passing assertions and only showed up when we looked at production directly: a scheduled task that had never once run, a reset-link invalidation that silently matched no rows because an unset timestamp column stores `0` rather than SQL `NULL`, and a badge that read correctly in the DOM while CSS uppercased it on screen. Screenshots and live probes caught what green tests could not.

## Accomplishments that we're proud of

A real change feed over real public data, with an analyst that recommends actions instead of describing charts. Live in production on a custom domain, with **11 runs, 76 SerpApi searches spent, 29 creatives tracked, 38 paid-block placements captured, 1,153 trend points, 72 typed changes detected and 18 AI insights written** — and $0.72 of actual SerpApi spend to show the cost model is real, not theoretical.

A clean control-plane / data-plane split where each half does what it's best at. 238 tests, CI green on every push, and a scheduler we verified by watching it fire rather than by assuming it did.

## What we learned

The interesting product isn't the dashboard — it's the *diff*. Once changes are typed events with severity, everything downstream (AI analysis, alerting, scheduling) becomes simple.

The other lesson was about verification. Passing tests told us the code did what we wrote; only production told us whether what we wrote was the thing we meant. Every one of our worst bugs was silent — no error, no failing assertion, just a feature quietly doing nothing.

## What's next for AdWatch

Own-account overlay (import your campaign reports to see spend against competitor moves), cross-tenant dedupe of SerpApi calls so two workspaces watching the same competitor cost one search, hard budget enforcement in the scheduler, per-workspace schedules and quiet hours, dayparting from hourly SERP samples, a Terraform module, and per-seat pricing at a fraction of incumbent suites.
