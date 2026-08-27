"""Integration tests for synthetic risk API scenarios and synthetic disclaimer (e04s01)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.api.app import create_app
from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.database import get_db_session
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


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_api_displays_synthetic_notice_when_synthetic_provenance_present(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verify revision response includes synthetic disclaimer when synthetic evidence is present."""
    store = PostgresCanonicalStore(db_session)
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    vin = "1HGCR2F85HA000000"

    link = ProvenanceLink(
        observation_id="obs_synth_1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        source_record_id="PPSR001",
        retrieved_at=as_of,
        synthetic=True,
    )
    confidence = ConfidenceAssessment(
        score=75,
        band=ConfidenceBand.MEDIUM,
        field_scores={"ppsr_result": 75},
        field_components={
            "ppsr_result": {
                "authority": 60,
                "agreement": 70,
                "freshness": 100,
                "validation": 100,
            }
        },
        rule_version="confidence-v1",
        explanation="Synthetic risk evidence",
    )
    result = ReconciliationResult(
        vin=vin,
        canonical_fields={"ppsr_result": "NO_MATCH"},
        field_provenance={"ppsr_result": [link]},
        conflicts=[],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )
    await store.publish(result)

    resp = await client.get(f"/v1/vehicles/{vin}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_fields"]["ppsr_result"] == "NO_MATCH"
    assert data["synthetic_notice"] == SYNTHETIC_DISCLAIMER
    assert "raw_payload" not in data
