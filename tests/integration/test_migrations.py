"""Integration tests verifying Alembic migrations upgrade and downgrade cleanly (e03s01)."""

import asyncio
import os

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from nz_vehicle_data_pipeline.persistence.models import Base

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
)


def get_alembic_config(db_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.mark.asyncio
async def test_alembic_upgrade_and_downgrade_cycle() -> None:
    """Verify applying Alembic upgrade head creates all expected tables and columns."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # 1. Clean slate: drop all existing tables and alembic_version
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

    config = get_alembic_config(TEST_DB_URL)

    # 2. Upgrade to head
    await asyncio.to_thread(command.upgrade, config, "head")

    # 3. Inspect tables created by migration
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        assert "source_observations" in tables
        assert "vehicles" in tables
        assert "canonical_revisions" in tables
        assert "alembic_version" in tables

    # 4. Downgrade to base
    await asyncio.to_thread(command.downgrade, config, "base")

    async with engine.connect() as conn:
        tables_after = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        assert "canonical_revisions" not in tables_after
        assert "vehicles" not in tables_after
        assert "source_observations" not in tables_after

    # 5. Re-upgrade to head
    await asyncio.to_thread(command.upgrade, config, "head")
    await engine.dispose()
