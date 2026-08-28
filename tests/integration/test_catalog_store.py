"""Integration tests for PostgresCanonicalStore list_current_vehicles catalog query (e05s01)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.models import Base
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceAssessment,
    ConfidenceBand,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink
from nz_vehicle_data_pipeline.reconciliation.result import ReconciliationResult

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


def _make_reconciliation_result(
    vin: str, make: str = "Toyota", model: str = "Corolla"
) -> ReconciliationResult:
    now = datetime.now(UTC)
    prov = ProvenanceLink(
        observation_id=f"obs_{vin}_1",
        source_system=SourceSystem.NZTA_MVR,
        source_record_id=f"rec_{vin}",
        retrieved_at=now,
        synthetic=True,
    )
    return ReconciliationResult(
        vin=vin,
        canonical_fields={"make": make, "model": model, "year": 2020},
        field_provenance={"make": [prov], "model": [prov]},
        conflicts=[],
        confidence=ConfidenceAssessment(
            score=90,
            band=ConfidenceBand.HIGH,
            field_scores={"make": 90},
            field_components={
                "make": {
                    "authority": 100,
                    "agreement": 70,
                    "freshness": 100,
                    "validation": 100,
                }
            },
            rule_version="confidence-v1",
            explanation="High confidence",
        ),
        as_of=now,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )


async def test_list_current_vehicles_empty(db_session: AsyncSession) -> None:
    store = PostgresCanonicalStore(db_session)
    items, total = await store.list_current_vehicles(limit=10, offset=0)
    assert items == []
    assert total == 0


async def test_list_current_vehicles_paginates_and_sorts(db_session: AsyncSession) -> None:
    store = PostgresCanonicalStore(db_session)

    # Publish 3 vehicles
    vins = ["7A8HB000000000003", "7A8HB000000000001", "7A8HB000000000002"]
    for v in vins:
        res = _make_reconciliation_result(v)
        await store.publish(res)

    # Fetch page 1 (limit 2, offset 0) -> should be sorted by VIN ascending
    page1, total = await store.list_current_vehicles(limit=2, offset=0)
    assert total == 3
    assert len(page1) == 2
    assert page1[0].vin == "7A8HB000000000001"
    assert page1[1].vin == "7A8HB000000000002"

    # Fetch page 2 (limit 2, offset 2)
    page2, total2 = await store.list_current_vehicles(limit=2, offset=2)
    assert total2 == 3
    assert len(page2) == 1
    assert page2[0].vin == "7A8HB000000000003"
