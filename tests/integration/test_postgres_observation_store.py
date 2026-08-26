"""Integration tests for PostgresObservationStore (e03s01)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.observation.store import DuplicateObservationError
from nz_vehicle_data_pipeline.persistence.models import Base
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def test_postgres_store_save_and_retrieve(db_session: AsyncSession) -> None:
    """Verify saving a new observation and retrieving it from PostgreSQL."""
    store = PostgresObservationStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    obs = SourceObservation(
        observation_id="obs_pg_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1HGCR2F85HA000000",
        raw_payload='{"Make": "HONDA"}',
        retrieved_at=as_of,
        synthetic=False,
    )

    await store.save(obs)
    retrieved = await store.get("obs_pg_1")
    assert retrieved is not None
    assert retrieved.observation_id == "obs_pg_1"
    assert retrieved.source_system == SourceSystem.NHTSA_VPIC
    assert retrieved.source_record_id == "1HGCR2F85HA000000"
    assert retrieved.raw_payload == '{"Make": "HONDA"}'
    assert retrieved.synthetic is False


async def test_postgres_store_idempotent_save(db_session: AsyncSession) -> None:
    """Verify saving the exact same observation twice is a no-op."""
    store = PostgresObservationStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    obs = SourceObservation(
        observation_id="obs_pg_2",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload='{"Make": "HONDA"}',
        retrieved_at=as_of,
    )

    await store.save(obs)
    await store.save(obs)  # should not raise
    assert await store.count() == 1


async def test_postgres_store_rejects_payload_mutation(
    db_session: AsyncSession,
) -> None:
    """Verify saving a modified payload with the same ID raises DuplicateObservationError."""
    store = PostgresObservationStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    obs1 = SourceObservation(
        observation_id="obs_pg_3",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload='{"Make": "HONDA"}',
        retrieved_at=as_of,
    )
    obs2 = SourceObservation(
        observation_id="obs_pg_3",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload='{"Make": "TOYOTA"}',
        retrieved_at=as_of,
    )

    await store.save(obs1)
    with pytest.raises(DuplicateObservationError):
        await store.save(obs2)
