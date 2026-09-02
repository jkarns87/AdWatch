import os

# Pin before app.config is imported and its settings get lru_cached. The repo's .env
# sets AUTH_PROVIDER=xano for the demo, and docker-compose passes .env into the test
# container — without this every request 401s locally while CI (which has no .env)
# passes. Tests assert routing and business logic, not Xano token introspection.
# Unconditional, not setdefault: compose has already set these from .env, so a default
# would never win. Override with TEST_AUTH_PROVIDER if you genuinely want to exercise it.
os.environ["AUTH_PROVIDER"] = os.environ.get("TEST_AUTH_PROVIDER", "none")
os.environ["ALERT_DISPATCHER"] = "none"

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: F401  — registers the tables on Base.metadata
from app.db import Base


@pytest.fixture
def db():
    """A real SQLAlchemy session against in-memory SQLite. Not a mock: the ORM
    mapping, defaults and constraints all execute for real."""
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
