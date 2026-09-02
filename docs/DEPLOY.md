# Deploy

Devpost wants a public URL. Pick **one** target by 4 PM Wednesday; all three are one command from the same Docker images. Keep `docker compose up` working locally as the stage fallback regardless.

## Images

```bash
docker build -t adwatch-api ./services/api
docker build -t adwatch-web --build-arg NEXT_PUBLIC_API_BASE_URL=https://<api-url>/api/v1 ./apps/web
```

Both images run as non-root, listen on `$PORT` (api 8000, web 3000), and read config from env. Secrets are never baked into images.

## Option A — Fly.io (fastest; Postgres included)

```bash
fly launch --no-deploy --name adwatch-api --path services/api
fly postgres create --name adwatch-db && fly postgres attach adwatch-db -a adwatch-api
fly secrets set SERPAPI_API_KEY=… ANTHROPIC_API_KEY=… -a adwatch-api
fly deploy -a adwatch-api
fly launch --name adwatch-web --path apps/web --build-arg NEXT_PUBLIC_API_BASE_URL=https://adwatch-api.fly.dev/api/v1
```

## Option B — Azure Container Apps

```bash
az group create -n adwatch -l westus2
az postgres flexible-server create -g adwatch -n adwatch-pg --tier Burstable --sku-name Standard_B1ms --public-access 0.0.0.0
az containerapp up -g adwatch -n adwatch-api --source services/api --ingress external --target-port 8000 \
  --env-vars DATABASE_URL=… SERPAPI_API_KEY=… ANTHROPIC_API_KEY=… ENV=prod
az containerapp up -g adwatch -n adwatch-web --source apps/web --ingress external --target-port 3000
```

## Option C — Google Cloud Run

```bash
gcloud run deploy adwatch-api --source services/api --region us-west1 --allow-unauthenticated \
  --set-env-vars ENV=prod --set-secrets SERPAPI_API_KEY=serpapi:latest,ANTHROPIC_API_KEY=anthropic:latest,DATABASE_URL=dburl:latest
gcloud run deploy adwatch-web --source apps/web --region us-west1 --allow-unauthenticated
```
(Cloud SQL or Neon for Postgres.)

## After deploy

- `GET https://<api>/api/v1/health` shows both keys `true` and `db: ok`
- `ENV=prod` disables `/demo/*` unless `DEMO_ENDPOINTS=true` — set it `true` for the hackathon so seed works on the deployed instance
- Set `WEBHOOK_URL` to a Slack/Discord incoming webhook for the visible alert on stage
- Put the URL in Devpost **and** README

## Terraform

Not for this build. A `infra/terraform/` module would be the first post-hackathon task — mention it in the "what's next" slide, don't spend Wednesday on it.

## Continuous deploy (`.github/workflows/deploy.yml`) — added 2026-09-02

After the first manual deploy above, every push to `main` redeploys **only what changed**: `services/api/**` → `fly deploy`
(after ruff + pytest), `apps/web/**` → `fly deploy` (after `tsc`), `xano/**` → `xano workspace push --force` (after a
logged `--dry-run`). Force-pushes and the first push deploy everything. Manual runs: Actions → deploy → *Run workflow* → pick a target.

One-time setup:

```bash
fly tokens create deploy -x 720h                       # → FLY_API_TOKEN
xano profile token                                     # → XANO_ACCESS_TOKEN (or Xano → Settings → Metadata API)
gh secret set FLY_API_TOKEN
gh secret set XANO_ACCESS_TOKEN
# optional overrides: gh variable set XANO_INSTANCE_ORIGIN --body https://…xano.io ; gh variable set XANO_WORKSPACE_ID --body 1
```

Fly rolls out with health checks, so a bad image never replaces the running one; the Xano push is blocked server-side on
syntax errors. Neither step runs on pull requests — CI (`ci.yml`) does the checking there.
