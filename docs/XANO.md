# Xano control plane

**Cut-line: Wednesday 6:00 PM PDT.** If signup → login → dashboard isn't working end-to-end by then, set `AUTH_PROVIDER=none` / `NEXT_PUBLIC_AUTH_PROVIDER=none` / `ALERT_DISPATCHER=webhook` and ship without it. Nothing else changes.

## What Xano owns (and why it's "meaningful")

| Concern | Where | XanoScript |
|---|---|---|
| **Authentication** — signup, login, token issuance with a `workspace_id` claim | Xano | `api/control/auth/*`, `function/issue_token.xs`, `table/user.xs` |
| **Tenancy** — workspaces, membership, roles | Xano | `table/workspace.xs`, `table/workspace_member.xs` |
| **Token introspection for the data plane** | Xano `/auth/me` ← FastAPI | `api/control/auth/me_get.xs`, `services/api/app/auth.py` |
| **Alert preferences** — per-workspace webhook/email destinations + min severity | Xano | `table/alert_pref.xs`, `api/control/alert_prefs*` |
| **Alert dispatch** — fan-out to every destination, delivery log | Xano ← FastAPI | `api/control/internal/dispatch_post.xs`, `table/alert_log.xs` |
| **Scheduling** — every 6h, collect + analyze every watchlist in every workspace | Xano → FastAPI | `task/collect_all_watchlists.xs` |
| Watchlists, competitors, keywords, snapshots, creatives, diffs, insights | **Postgres / FastAPI** | `services/api/*` |

The data plane never stores a password, never issues a token, never decides who gets notified, and never schedules itself. That's the build-story sentence.

## Request flow

```
Browser ──login──▶ Xano /auth/login ──▶ authToken (claims: workspace_id, role)
Browser ──Bearer──▶ FastAPI /api/v1/* ──introspect──▶ Xano /auth/me ──▶ workspace_id  (cached 5 min)
Xano task (6h) ──X-Dataplane-Secret + X-Workspace-Id──▶ FastAPI /watchlists … /collect-and-analyze
FastAPI /analyze ──X-Dataplane-Secret──▶ Xano /internal/dispatch ──▶ webhook / email per alert_pref ──▶ alert_log
```

## Files (all validated with `xano_validate_xanoscript`)

```
xano/
  table/        user · workspace · workspace_member · alert_pref · alert_log
  function/     issue_token
  api/control/  api_group (canonical adwatch-control) · health_get
    auth/       signup_post · login_post · me_get
    alert_prefs_get · alert_prefs_post · alert_prefs/by_id_delete
    internal/   dispatch_post
  task/         collect_all_watchlists  (freq 21600s)
```

## Push it (Joey, from a terminal in `AdWatch/`)

```bash
npm i -g @xano/cli && xano auth            # browser login, pick instance, name the profile
xano workspace list                        # note the id
xano workspace push -d ./xano -w <id> --dry-run   # REVIEW THE DIFF
xano workspace push -d ./xano -w <id>             # apply (direct push is enabled on this workspace)
```

Then in the Xano dashboard (`app.xano.com` → your instance → workspace → Settings → Environment variables) set:

| Env var | Value |
|---|---|
| `DATAPLANE_URL` | public URL of the FastAPI service, no trailing slash (e.g. `https://adwatch-api.fly.dev`) |
| `DATAPLANE_SHARED_SECRET` | any long random string — same value goes in the API's `.env` |

Grab the control-plane base URL: it's `https://<instance-host>/api:adwatch-control` (instance host from `xano profile me`). Do **not** guess a dashboard URL; use `app.xano.com`.

## Wire the data plane + web

`.env` (API):
```
AUTH_PROVIDER=xano
XANO_BASE_URL=https://<instance-host>/api:adwatch-control
DATAPLANE_SHARED_SECRET=<same as Xano>
ALERT_DISPATCHER=xano
DASHBOARD_URL=https://<web-url>
```
`apps/web/.env.local`:
```
NEXT_PUBLIC_AUTH_PROVIDER=xano
NEXT_PUBLIC_XANO_BASE_URL=https://<instance-host>/api:adwatch-control
```

## Smoke test (≈ 5 min)

```bash
X=https://<instance-host>/api:adwatch-control
curl -s $X/health
curl -s -X POST $X/auth/signup -H 'content-type: application/json' -d '{"name":"Joey","email":"you@example.com","password":"correct-horse-9"}'
TOKEN=<authToken from above>
curl -s $X/auth/me -H "Authorization: Bearer $TOKEN"                       # -> workspace_id
curl -s -X POST $X/alert_prefs -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
     -d '{"channel":"webhook","target":"https://hooks.slack.com/services/…","min_severity":"medium"}'
curl -s http://localhost:8000/api/v1/watchlists -H "Authorization: Bearer $TOKEN"   # data plane accepts the Xano token
curl -s -X POST http://localhost:8000/api/v1/watchlists/1/analyze -H "Authorization: Bearer $TOKEN"  # alerts_sent > 0 → Slack message
```

Then in the dashboard: `/login` → sign in → watchlists load with the token.

## Static hosting (optional, paid feature — skip if it fights you)

```bash
cd apps/web && npm run build            # standalone output; static hosting wants plain files, so prefer the container deploy
xano static_host create adwatch
xano static_host build push adwatch -d ./apps/web/.next -n "v1"   # only if the plan allows it
```
`docs/DEPLOY.md` is the primary path for the web app; static hosting is a bonus line in the build story, not a dependency.

## Build story answers (Devpost Xano section — no third-party brand names)

- **What did you replace?** The weekly manual competitor check paid-search teams do across an incumbent competitive-intelligence suite and a spreadsheet.
- **Why?** It's retrospective, expensive per seat, and has no notion of *change* — you get a report, not an alert.
- **AI tools used:** Claude (Cowork + Code) for planning, scaffolding, the diff engine and the analyst model; Xano Developer MCP for XanoScript docs + validation.
- **Time:** ~22 hours, team of 3.
- **What would have taken longer without AI + Xano:** the entire control plane — auth, tenancy, alert preferences, fan-out with delivery logging, and the scheduler — is 16 XanoScript files written and validated in under an hour; the diff engine, analyst prompt, and dashboard were scaffolded by Claude in the first two hours.
