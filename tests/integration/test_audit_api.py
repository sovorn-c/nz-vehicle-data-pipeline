"""Integration tests for Audit & Observation inspection REST API (e03s04)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.api.app import create_app
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.database import get_db_session
from nz_vehicle_data_pipeline.persistence.models import Base
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceAssessment,
    ConfidenceBand,
)
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictState,
    FieldConflict,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
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


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_get_observation_detail(client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Verify querying /v1/observations/{id} returns raw payload and metadata."""
    obs_store = PostgresObservationStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    obs = SourceObservation(
        observation_id="obs_audit_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1HGCR2F85HA000000",
        raw_payload='{"Make": "HONDA", "Model": "ACCORD"}',
        retrieved_at=as_of,
        synthetic=False,
    )
    await obs_store.save(obs)

    resp = await client.get("/v1/observations/obs_audit_1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["observation_id"] == "obs_audit_1"
    assert data["source_system"] == "NHTSA_VPIC"
    assert data["raw_payload"] == '{"Make": "HONDA", "Model": "ACCORD"}'
    assert data["synthetic"] is False

    # 404 for unknown observation
    resp_404 = await client.get("/v1/observations/nonexistent")
    assert resp_404.status_code == 404


async def test_get_vehicle_conflicts_and_provenance(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verify querying /v1/vehicles/{vin}/conflicts and /v1/vehicles/{vin}/provenance."""
    store = PostgresCanonicalStore(db_session)
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"

    link1 = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    link2 = ProvenanceLink(
        observation_id="obs_2",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )

    c1 = CandidateValue(field_name="year", value=2017, provenance=link1)
    c2 = CandidateValue(field_name="year", value=2018, provenance=link2)

    conflict = FieldConflict(
        field_name="year",
        conflicting_candidates=[c1, c2],
        state=ConflictState.RESOLVED,
        winning_value=2017,
        rule_version="resolution-v1",
        rationale="NHTSA wins",
    )

    confidence = ConfidenceAssessment(
        score=85,
        band=ConfidenceBand.HIGH,
        field_scores={"year": 85},
        field_components={
            "year": {
                "authority": 100,
                "agreement": 50,
                "freshness": 100,
                "validation": 100,
            }
        },
        rule_version="confidence-v1",
        explanation="Resolved conflict",
    )

    result = ReconciliationResult(
        vin=vin,
        canonical_fields={"year": 2017},
        field_provenance={"year": [link1]},
        conflicts=[conflict],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )
    await store.publish(result)

    # Get conflicts
    resp_conf = await client.get(f"/v1/vehicles/{vin}/conflicts")
    assert resp_conf.status_code == 200
    conf_data = resp_conf.json()
    assert len(conf_data) == 1
    assert conf_data[0]["field_name"] == "year"
    assert conf_data[0]["state"] == "RESOLVED"
    assert conf_data[0]["winning_value"] == 2017

    # Get provenance
    resp_prov = await client.get(f"/v1/vehicles/{vin}/provenance")
    assert resp_prov.status_code == 200
    prov_data = resp_prov.json()
    assert "year" in prov_data
    assert len(prov_data["year"]) == 1
    assert prov_data["year"][0]["observation_id"] == "obs_1"
