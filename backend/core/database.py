"""
BuyerHunter V2 — Core Database Layer

Async SQLAlchemy engine for PostgreSQL with connection pooling.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings


class V2Base(DeclarativeBase):
    """Declarative base for V2 models. Separate from V1 Base to avoid collisions."""
    pass


_engine = None
_session_factory = None


def _is_sqlite(url) -> bool:
    return str(url).startswith("sqlite") or str(url).startswith("sqlite+aiosqlite")


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    kwargs = {"echo": settings.debug}
    if not _is_sqlite(settings.database_url):
        kwargs["pool_size"] = 20
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True

    _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_v2_db():
    """FastAPI dependency — yields an async session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_v2_db():
    """Create all V2 tables (for dev/testing). In production use ddl.sql + Alembic.

    A legacy V1 ``Company`` model also maps to the ``companies`` table with a
    different schema. When that legacy table already exists, ``create_all`` skips
    it and the V2 ORM queries fail with "no such column: companies.canonical_name".
    Reset any colliding legacy tables (detected by the absence of V2 columns) so the
    V2 schema is authoritative.
    """
    import backend.core.models  # Register models with V2Base.metadata
    from sqlalchemy import text

    engine = get_engine()
    async with engine.begin() as conn:
        if _is_sqlite(engine.url):
            def _reset_legacy_tables(sync_conn):
                rows = sync_conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'")
                ).fetchall()
                if not rows:
                    return
                existing_cols = [
                    r[0] for r in sync_conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                ]
                if "canonical_name" not in existing_cols:
                    for t in ("companies", "contacts", "search_jobs", "evidence_ledger"):
                        sync_conn.execute(text(f"DROP TABLE IF EXISTS {t}"))

            await conn.run_sync(_reset_legacy_tables)

        await conn.run_sync(V2Base.metadata.create_all)
