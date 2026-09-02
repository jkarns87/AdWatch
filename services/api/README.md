# services/api — AdWatch data plane

FastAPI + SQLAlchemy + Postgres. Owners: @divya2030 @semmaguptam.

```
app/
  main.py               app factory, CORS, /health
  config.py             env settings (pydantic-settings)
  db.py                 engine/session, create_all on startup
  models.py             tables (docs/ARCHITECTURE.md § Data model)
  schemas.py            response models (docs/API_CONTRACT.md)
  auth.py               workspace resolution (X-Workspace-Id | Xano JWT)
  collectors/
    serpapi_client.py   3 engines + disk cache (quota protection)
    normalize.py        raw SerpApi -> flat dicts (pure)
  engine/
    diff.py             change detection (pure, unit-tested)
    collect.py          run -> snapshots -> rows -> changes
    analyst.py          Claude: structured diff -> JSON insight (with honest fallback)
    analyze.py          pending changes -> insights -> alerts
  alerts/webhook.py     Slack/Discord webhook
  seed/
    synthetic.py        fake SerpApi client (fictitious advertisers, 2 runs)
    demo.py             synthetic / live seeding
  routers/              watchlists · runs · reads · demo
tests/test_diff.py
```

## Run locally without Docker

```bash
cd services/api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://adwatch:adwatch@localhost:5432/adwatch
uvicorn app.main:app --reload
pytest -q
```

## Where to start (backend lane)

1. `pytest` green → the diff engine is the contract; extend `tests/test_diff.py` before changing thresholds.
2. Run `POST /api/v1/demo/seed {"mode":"synthetic"}` and browse `/docs` — every read endpoint should return data.
3. Put a real domain + keyword in `seed/demo_config.json` and run `POST /demo/seed {"mode":"live"}` **once**. Inspect `snapshots.raw` and fix `normalize.py` if any field is off (re-normalizing from raw costs no quota).
4. Second live run via `POST /watchlists/{id}/collect-and-analyze` → real changes + Claude insights.

## Field notes

- SerpApi's `google_ads_transparency_center` returns `ad_creatives[]` with `id`, `format`, `first_shown`/`last_shown` (unix ts in newer responses), `image`, `details_link`, `advertiser`, `advertiser_id`. `normalize.py` handles both timestamp and ISO shapes.
- `google` engine ads live in `ads[]` with `position`, `block_position` ("top"/"bottom"), `title`, `link`, `displayed_link`, `description`.
- `google_trends` TIMESERIES → `interest_over_time.timeline_data[]` (`timestamp`, `values[0].extracted_value`); RELATED_QUERIES → `related_queries.rising[]/top[]` (`query`, `value`, `extracted_value`; "Breakout" has no numeric value).
- Never call SerpApi from a read endpoint. Only `collect` spends quota.
