# infra

- `../docker-compose.yml` — local stack (db + api + web)
- `../services/api/Dockerfile`, `../apps/web/Dockerfile` — non-root, `$PORT`-aware images
- `../docs/DEPLOY.md` — one-command deploy to Fly / Azure Container Apps / Cloud Run
- Terraform module: post-hackathon.
