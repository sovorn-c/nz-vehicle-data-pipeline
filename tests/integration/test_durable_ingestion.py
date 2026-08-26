"""Integration tests proving IngestionPipeline persists durable evidence (e03s01)."""

import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.normalization.engine import NormalizationEngine
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.persistence.models import Base
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)
from nz_vehicle_data_pipeline.pipeline.orchestrator import IngestionPipeline

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


async def test_durable_ingestion_persists_observations_in_postgres(
    db_session: AsyncSession,
) -> None:
    """Verify IngestionPipeline writes real source observations to PostgreSQL."""
    store = PostgresObservationStore(db_session)
    normalization_engine = NormalizationEngine()
    pipeline = IngestionPipeline(store=store, engine=normalization_engine)

    connector = NHTSAVPICConnector(
        data=[
            {
                "VIN": "1HGCR2F85HA000000",
                "Make": "HONDA",
                "Model": "ACCORD",
                "ModelYear": 2017,
                "VehicleType": "PASSENGER CAR",
            }
        ]
    )

    batch_result = await pipeline.ingest(connector, run_id="run_pg_01")
    assert batch_result.total_ingested == 1
    assert batch_result.normalized_count == 1

    # Verify persisted in PostgreSQL
    persisted = await store.get_by_run_id("run_pg_01")
    assert len(persisted) == 1
    assert persisted[0].source_system == SourceSystem.NHTSA_VPIC
    assert persisted[0].source_record_id == "1HGCR2F85HA000000"
    assert "ACCORD" in persisted[0].raw_payload
