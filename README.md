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

## Docs

- [`docs/PLAN.md`](docs/PLAN.md) — hour-by-hour timeline, lanes, checkpoints, quota budget
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components, data model, change taxonomy
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
