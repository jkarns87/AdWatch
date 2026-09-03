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
| **Plan** — which plan a workspace is on, and who may change it | Xano | `table/workspace.xs`, `api/control/workspace/plan_post.xs` |
| **Platform administration** — changing *another* workspace's plan | Xano | `table/user.xs` (`is_platform_admin`), `api/control/admin/workspace_plan_post.xs`, `table/plan_change.xs` |
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
  table/        user · workspace · workspace_member · alert_pref · alert_log ·
                password_reset · plan_change
  function/     issue_token · send_email
  api/control/  api_group (canonical adwatch-control) · health_get
    auth/       signup_post · login_post · me_get · forgot_password_post · reset_password_post
    workspace/  plan_post
    admin/      workspace_plan_post
    alert_prefs_get · alert_prefs_post · alert_prefs/by_id_delete
    alerts_get · alerts/read_post · alerts/read_all_post
    internal/   dispatch_post
  task/         collect_all_watchlists (21600s) · prune_snapshots (daily 09:00Z)
```

## Plans and platform administration

`workspace.plan` is owned here and read by the data plane through `/auth/me`
introspection, which caches for five minutes — a plan change is not visible to the data
plane until the token is re-introspected or the user logs in again. That cache is worth
remembering before concluding a plan change "did not work".

Two doors change a plan:

- `POST /workspace/plan` — the owner changing their **own** workspace. Gated on
  `$auth.extras.role == "owner"`.
- `POST /admin/workspace/{workspace_id}/plan` — platform staff changing **anyone's**.
  Gated on `$auth.extras.is_platform_admin`.

`is_platform_admin` is deliberately not a `workspace_member.role`. A role only ever means
something inside one workspace; this is the one action a caller takes against a workspace
they are not a member of, so conflating them would have made every workspace owner a
platform admin. The claim rides in the token, so **a user granted the flag must log in
again** before it takes effect — and a token issued before the claim existed reads null
and is denied, which is the correct way to fail.

Both doors write to `plan_change` (actor, workspace, from, to, reason), before the patch
and even when the plan does not move, so "who changed this plan" has one answer
regardless of which door it came through.

Granting the flag is a manual database edit — there is no endpoint that grants platform
administration, on purpose:

```bash
TOK=$(python3 -c "import yaml,pathlib;print(yaml.safe_load(pathlib.Path.home().joinpath('.xano/credentials.yaml').read_text())['profiles']['default']['access_token'])")
curl -X PUT "https://<instance>/api:meta/workspace/1/table/3/content/<user_id>" \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"id":<user_id>,"is_platform_admin":true}'
```

That metadata endpoint merges rather than replaces — verified — but `PUT` semantics vary,
so test against a throwaway row before scripting it against a real user.

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


## Password reset

`POST /auth/forgot_password` `{email}` → always `{ok:true, message}`, whether or not the
address has an account. A different answer for a known email turns the form into an
account-enumeration oracle.

`POST /auth/reset_password` `{token, password}` → `{ok:true, message}`.

The emailed token is a **split token**, `selector.verifier`:

- `selector` is stored in clear and uniquely indexed, so the row is found by lookup
  rather than by comparing secrets.
- `verifier` is stored in a Xano `password` field, so it is hashed. A leak of
  `password_reset` yields no usable reset link.

Tokens expire after an hour, are single-use (`used_at`), and issuing a new one spends
any outstanding tokens for that user, so only the newest link works. Every failure —
unknown, spent, expired, wrong verifier — returns the same message, so the endpoint
cannot be used to probe which links exist.

> An unset `timestamp?` column stores the sentinel **0, not SQL NULL**. This matters
> because the two comparisons are evaluated in different places: a `db.query` `where`
> runs in the database, where `IS NULL` never matches 0, while a `precondition` runs
> in-script, where `0 == null` is loosely true. `where used_at == null` therefore matched
> nothing and silently invalidated nothing, while redemption kept working — so every link
> issued within the hour stayed live at once. Compare against `0` in a `where` clause.

`DASHBOARD_URL` builds the link, so it must be set on the Xano side too or the email
points nowhere.

### Rate limiting

Three issues per account per hour, counted from `password_reset` rows — no extra table.
Enough for someone who lost the first email, not enough to mail-bomb an address.

A throttled request returns the **same** response as a delivered one. Anything else
re-opens the enumeration hole the neutral message exists to close.

The throttle gates the whole issue-and-send block, including the step that spends
outstanding tokens — so being throttled never invalidates a link the user is still
holding.

This is per-account, not per-IP. Someone spraying many different addresses is not
limited by it; that would need a separate counter keyed on the caller.

### Known gap: the response body is neutral, the response *time* is not

Measured against production on 2026-09-03: an address with no account returns in
0.19–0.24s (n=8, tight cluster), because the whole issue-and-send block is skipped. An
address **with** an account that is not yet throttled returns in 0.39–0.65s (n=3) — it
generates a token and calls Resend on the response path. The ranges do not overlap, so a
single request distinguishes a registered address from an unregistered one despite the
identical body.

Self-limiting but not closed: after three probes the account is throttled and returns
fast like an unknown address, so an attacker gets three clean probes per address per
hour — and one is enough. Closing it means taking the send off the response path so
every answer costs the same, which is a design change, not a tweak.


## Health

`GET /health` → `{status, dataplane_configured, dashboard_url_configured,
dataplane_secret_configured, dataplane_probe_status}`

The three `*_configured` flags are presence checks on env vars, reported separately
because they fail differently:

| | Symptom when missing |
|---|---|
| `DATAPLANE_URL` | the collect task builds a relative path that never resolves |
| `DATAPLANE_SHARED_SECRET` | the data plane answers 401 |
| `DASHBOARD_URL` | reset emails send with a link pointing nowhere |

`GET /health?deep=true` additionally calls `GET {DATAPLANE_URL}/api/v1/watchlists` with
the shared secret — the same authenticated endpoint `task/collect_all_watchlists` uses —
and reports the status in `dataplane_probe_status`. **200 means the scheduler can
actually do its job.**

Both variables being set proves nothing about whether the secret *matches* the one the
data plane holds. That mismatch otherwise surfaces only as a 401 on an unattended
nightly run, which looks identical to "nothing changed overnight".

Deep is opt-in because it makes an outbound request; the default stays a cheap liveness
check and returns `dataplane_probe_status: null`.
