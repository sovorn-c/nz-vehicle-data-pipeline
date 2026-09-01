"""Database engine and session configuration for async SQLAlchemy (ADR 0004)."""

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
)


def normalize_database_url(db_url: str) -> str:
    """Select the installed Psycopg 3 driver for standard PostgreSQL URLs."""
    if db_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + db_url.removeprefix("postgresql://")
    return db_url


def get_engine(url: str | None = None) -> AsyncEngine:
    """Create and return an async SQLAlchemy engine."""
    db_url = url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_async_engine(normalize_database_url(db_url), echo=False)


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create and return an async sessionmaker."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Initialize all tables in metadata."""
    from nz_vehicle_data_pipeline.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async session."""
    engine = get_engine()
    factory = get_session_factory(engine)
    async with factory() as session:
        yield session
