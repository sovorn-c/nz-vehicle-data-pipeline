"""Integration tests for concurrent canonical publications under PostgreSQL row locks (e03s02)."""

import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.database import (
    get_engine,
    get_session_factory,
)
from nz_vehicle_data_pipeline.persistence.models import (
    Base,
    CanonicalRevisionRow,
    VehicleRow,
)
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
async def clean_db() -> AsyncGenerator[None, None]:
    engine = get_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.mark.usefixtures("clean_db")
async def test_concurrent_initial_publications() -> None:
    """Verify concurrent initial publications for same VIN create 1 vehicle and 1 revision."""
    engine = get_engine(TEST_DB_URL)
    factory = get_session_factory(engine)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"

    link = ProvenanceLink(
        observation_id="obs_c1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    confidence = ConfidenceAssessment(
        score=91,
        band=ConfidenceBand.HIGH,
        field_scores={"make": 91},
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
    )
    result = ReconciliationResult(
        vin=vin,
        canonical_fields={"make": "HONDA"},
        field_provenance={"make": [link]},
        conflicts=[],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )

    async def worker() -> None:
        async with factory() as session:
            store = PostgresCanonicalStore(session)
            await store.publish(result)

    # Launch 5 concurrent workers attempting initial publication simultaneously
    await asyncio.gather(*(worker() for _ in range(5)))

    # Verify invariants in database
    async with factory() as session:
        v_count = (
            await session.execute(select(func.count(VehicleRow.vin)).where(VehicleRow.vin == vin))
        ).scalar_one()
        assert v_count == 1

        r_count = (
            await session.execute(
                select(func.count(CanonicalRevisionRow.revision_id)).where(
                    CanonicalRevisionRow.vin == vin
                )
            )
        ).scalar_one()
        assert r_count == 1

    await engine.dispose()


@pytest.mark.usefixtures("clean_db")
async def test_concurrent_different_material_publications_are_serialized() -> None:
    """Verify concurrent distinct material changes are serialized without collision."""
    engine = get_engine(TEST_DB_URL)
    factory = get_session_factory(engine)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"

    link = ProvenanceLink(
        observation_id="obs_c1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    confidence = ConfidenceAssessment(
        score=91,
        band=ConfidenceBand.HIGH,
        field_scores={"make": 91},
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
    )

    async def worker(index: int) -> None:
        async with factory() as session:
            store = PostgresCanonicalStore(session)
            res = ReconciliationResult(
                vin=vin,
                canonical_fields={"make": f"HONDA_{index}"},
                field_provenance={"make": [link]},
                conflicts=[],
                confidence=confidence,
                as_of=as_of,
                rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
            )
            await store.publish(res)

    # Launch 4 concurrent distinct material updates
    await asyncio.gather(*(worker(i) for i in range(4)))

    # Verify all revisions were serialized monotonically
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(CanonicalRevisionRow.revision_number).where(
                        CanonicalRevisionRow.vin == vin
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sorted(rows) == [1, 2, 3, 4]

    await engine.dispose()
