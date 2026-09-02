# AdWatch

**Competitive ad intelligence that watches the market for you.**

AdWatch continuously monitors what your competitors are running in paid search — every live creative, every keyword they're bidding on, every trend shift in your category — and uses AI to explain *what changed, why it matters, and what to do about it*. It's an always-on analyst for paid-search teams, replacing the weekly "open six tabs and eyeball it" ritual with a change feed and actionable recommendations.

Built in 24 hours at the DevNetwork [API + Cloud + AI] Hackathon 2026 (API World, Santa Clara).

## How it works

```
 Watchlist ──▶ Collectors ──▶ Snapshots ──▶ Diff Engine ──▶ AI Analyst ──▶ Insights + Alerts
 (competitors,  (SerpApi:      (Postgres,    (creative       (Claude reads   (dashboard feed,
  keywords)      Ads Transp.,   raw JSON +    launched/       the structured   webhook / email)
                 Search ads,    normalized    dropped, new    diff, writes
                 Trends)        tables)       SERP rival,     summary + next
                                              trend spike)    actions)
```

| Layer | Tech | Owner |
|---|---|---|
| Web dashboard | Next.js 15, TypeScript, Tailwind | @jkarns87 |
| Control plane (auth, workspaces, watchlist CRUD, alert prefs) | Xano *(time-boxed — see `docs/XANO.md`)* | @jkarns87 |
| Data plane API + collectors + diff + AI analyst | Python 3.11, FastAPI, SQLAlchemy, httpx, Anthropic SDK | @divya2030 @semmaguptam |
| Storage | Postgres 16 | @divya2030 @semmaguptam |
| Infra | Docker Compose, GitHub Actions, container deploy (any cloud) | @jkarns87 |

## Quick start

```bash
cp .env.example .env            # add SERPAPI_API_KEY and ANTHROPIC_API_KEY
make up                          # postgres + api + web
make seed                        # synthetic demo data (no SerpApi quota used)
open http://localhost:3000       # dashboard
open http://localhost:8000/docs  # API (OpenAPI)
```

Live data pull for one watchlist (uses SerpApi quota — see `docs/PLAN.md` for budget):

```bash
make collect WATCHLIST=1
make analyze WATCHLIST=1
```

## App routes

| Route | What |
|---|---|
| `/welcome` | Marketing landing (hero, how it works, features, pricing from `plans.py`) |
| `/login` | Sign in / sign up on the Xano control plane (`NEXT_PUBLIC_AUTH_PROVIDER=xano`); local mode skips it |
| `/` | Watchlists with unreviewed-change badges · **New watchlist** |
| `/onboarding` | 4-step wizard: watchlist (vertical, geo, search location) → competitors → keywords → review + baseline run |
| `/watchlists/[id]` | Insights · Changes · Competitors (creative grid, add) · Keywords (paid block, share of voice, demand, add) · **Collect now** · **Export report** |
| `/alerts` | In-app alert inbox (served by the Xano control plane) |
| `/usage` | Usage & plan: searches spent vs budget, month-end projection, plan switch |
| `/settings/integrations` | Alert destinations: in-app, Slack, Teams, Discord, email, webhook |

## Reports

`Export report ▾` (or `GET /api/v1/watchlists/{id}/report?audience=cfo|marketing&format=pdf|docx|md`) generates an audience-tailored brief: AI executive summary with decisions for that reader, KPIs, recommended actions, what changed, competitor activity, keyword share of voice and demand chart. Renderers: reportlab (PDF), python-docx, Markdown.

## Docs

- [`docs/PLAN.md`](docs/PLAN.md) — hour-by-hour timeline, lanes, checkpoints, quota budget
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components, data model, change taxonomy
- [`docs/SERPAPI.md`](docs/SERPAPI.md) — the four SerpApi calls, fields we consume, quota rules, backend definition of done
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — the REST contract between web ↔ api (frontend and backend can build in parallel against it)
- [`docs/XANO.md`](docs/XANO.md) — control-plane setup and the cut-line if it slips
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — one-command deploy options
- [`docs/DEVPOST.md`](docs/DEVPOST.md) — submission checklist + pitch copy (brand-name-free)
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — the 3-minute stage demo

## Repo layout

```
apps/web/          Next.js dashboard
services/api/      FastAPI service: routers, collectors, diff engine, AI analyst, seed
infra/             docker-compose, Dockerfiles, deploy notes
docs/              plan, architecture, contracts, submission
.github/workflows  CI: lint + tests + builds
```
