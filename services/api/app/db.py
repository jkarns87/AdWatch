from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def session_factory() -> sessionmaker:
    get_engine()
    return _SessionLocal  # type: ignore[return-value]


def get_db() -> Generator[Session, None, None]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Hackathon-grade migrations: create what's missing. Swap for Alembic post-event."""
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(get_engine())
    # additive column migrations for DBs created before these fields existed (hackathon-grade; Alembic later)
    from sqlalchemy import text

    with get_engine().begin() as conn:
        conn.execute(text("ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS location VARCHAR(120)"))
        conn.execute(text("ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS trends_category_id INTEGER"))
        conn.execute(text("ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS company_domain VARCHAR(255)"))
        conn.execute(text("ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS company_description TEXT"))
        conn.execute(text("ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS market_terms JSON"))
        conn.execute(text("ALTER TABLE competitors ADD COLUMN IF NOT EXISTS is_self BOOLEAN NOT NULL DEFAULT FALSE"))
