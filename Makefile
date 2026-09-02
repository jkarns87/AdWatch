.PHONY: up down logs seed reset collect analyze test lint web-dev api-dev build

WATCHLIST ?= 1
API ?= http://localhost:8000/api/v1

up:            ## start postgres + api + web
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api web

seed:          ## synthetic demo data (no SerpApi quota)
	curl -s -X POST $(API)/demo/seed -H 'content-type: application/json' -d '{"mode":"synthetic"}'; echo

seed-live:     ## real data from services/api/seed/demo_config.json (spends quota)
	curl -s -X POST $(API)/demo/seed -H 'content-type: application/json' -d '{"mode":"live"}'; echo

reset:
	curl -s -X POST $(API)/demo/reset -o /dev/null -w "%{http_code}\n"

collect:       ## live collect for WATCHLIST=n (spends quota)
	curl -s -X POST $(API)/watchlists/$(WATCHLIST)/collect | python3 -m json.tool | head -40

analyze:
	curl -s -X POST $(API)/watchlists/$(WATCHLIST)/analyze | python3 -m json.tool | head -60

test:
	cd services/api && python -m pytest -q

lint:
	cd services/api && ruff check app tests
	cd apps/web && npx tsc --noEmit

api-dev:       ## run the API without docker (needs local postgres)
	cd services/api && uvicorn app.main:app --reload

web-dev:
	cd apps/web && npm run dev

build:         ## build both images
	docker build -t adwatch-api ./services/api
	docker build -t adwatch-web ./apps/web

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
