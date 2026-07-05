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


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
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
    """Create all V2 tables (for dev/testing). In production use ddl.sql + Alembic."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(V2Base.metadata.create_all)
