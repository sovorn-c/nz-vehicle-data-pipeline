"""Integration tests for atomic canonical publication in PostgreSQL (e03s02, ADR 0004)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.models import (
    Base,
    CanonicalRevisionRow,
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
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def test_publish_first_revision_creates_revision_1(
    db_session: AsyncSession,
) -> None:
    """Verify publishing a greenfield ReconciliationResult creates Revision 1 in PostgreSQL."""
    store = PostgresCanonicalStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"
    link = ProvenanceLink(
        observation_id="obs_1",
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
        canonical_fields={"make": "HONDA", "model": "ACCORD"},
        field_provenance={"make": [link], "model": [link]},
        conflicts=[],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )

    record, created = await store.publish(result)
    assert created is True
    assert record.revision_number == 1
    assert record.vin == vin
    assert record.canonical_fields["make"] == "HONDA"

    # Query current revision from DB
    current = await store.get_current_revision(vin)
    assert current is not None
    assert current.revision_number == 1
    assert current.canonical_fields["model"] == "ACCORD"


async def test_publish_identical_result_is_idempotent_no_new_revision(
    db_session: AsyncSession,
) -> None:
    """Verify publishing the exact same material hash creates no duplicate revision."""
    store = PostgresCanonicalStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"
    link = ProvenanceLink(
        observation_id="obs_1",
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

    rec1, created1 = await store.publish(result)
    assert created1 is True
    assert rec1.revision_number == 1

    rec2, created2 = await store.publish(result)
    assert created2 is False
    assert rec2.revision_number == 1
    assert rec2.revision_id == rec1.revision_id


async def test_publish_material_change_increments_revision(
    db_session: AsyncSession,
) -> None:
    """Verify publishing changed field values creates Revision 2."""
    store = PostgresCanonicalStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"
    link = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    confidence1 = ConfidenceAssessment(
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
    result1 = ReconciliationResult(
        vin=vin,
        canonical_fields={"make": "HONDA"},
        field_provenance={"make": [link]},
        conflicts=[],
        confidence=confidence1,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )
    await store.publish(result1)

    # Material change: adding model
    result2 = ReconciliationResult(
        vin=vin,
        canonical_fields={"make": "HONDA", "model": "ACCORD"},
        field_provenance={"make": [link], "model": [link]},
        conflicts=[],
        confidence=confidence1,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )
    rec2, created2 = await store.publish(result2)
    assert created2 is True
    assert rec2.revision_number == 2

    # Verify history has 2 revisions
    history = await store.get_revision_history(vin)
    assert len(history) == 2
    assert history[0].revision_number == 2  # newest first
    assert history[1].revision_number == 1


async def test_publish_failure_rolls_back_entire_transaction(
    db_session: AsyncSession,
) -> None:
    """Verify any child or commit failure rolls back all writes."""
    store = PostgresCanonicalStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"

    link = ProvenanceLink(
        observation_id="obs_1",
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

    # Simulate error by injecting a session failure
    original_commit = db_session.commit

    async def broken_commit() -> None:
        raise RuntimeError("Simulated database failure during publication")

    db_session.commit = broken_commit  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        await store.publish(result)

    db_session.commit = original_commit  # type: ignore[method-assign]
    await db_session.rollback()

    # Verify no partial revision was written
    rev_count = (
        await db_session.execute(
            select(func.count(CanonicalRevisionRow.revision_id)).where(
                CanonicalRevisionRow.vin == vin
            )
        )
    ).scalar_one()
    assert rev_count == 0
