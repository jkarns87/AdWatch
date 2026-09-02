import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .coffee.router import router as coffee_router
from .config import get_settings
from .db import get_engine, init_db
from .routers import demo, reads, reports, runs, usage, watchlists

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AdWatch API", version="0.1.0", lifespan=lifespan, docs_url="/docs", openapi_url="/openapi.json")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
app.include_router(watchlists.router, prefix=API)
app.include_router(runs.router, prefix=API)
app.include_router(reads.router, prefix=API)
app.include_router(demo.router, prefix=API)
app.include_router(usage.router, prefix=API)
app.include_router(reports.router, prefix=API)
app.include_router(coffee_router, prefix=API)


@app.get(f"{API}/health", tags=["health"])
def health():
    db_ok = "ok"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1"))
    except Exception as e:  # noqa: BLE001
        db_ok = f"error: {e.__class__.__name__}"
    return {
        "status": "ok" if db_ok == "ok" else "degraded",
        "db": db_ok,
        "serpapi_key": bool(settings.serpapi_api_key),
        "anthropic_key": bool(settings.anthropic_api_key),
        "model": settings.anthropic_model,
        "env": settings.env,
        "auth_provider": settings.auth_provider,
        "alert_dispatcher": settings.alert_dispatcher,
        "xano_configured": bool(settings.xano_base_url),
    }
