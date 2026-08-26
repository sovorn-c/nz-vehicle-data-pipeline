"""Integration tests for Vehicle REST API endpoints (e03s03)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.api.app import create_app
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


async def test_get_vehicle_not_found(client: httpx.AsyncClient) -> None:
    """Verify requesting an unknown VIN returns 404 with structured error."""
    resp = await client.get("/v1/vehicles/1HGCR2F85HA999999")
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data


async def test_get_current_vehicle_and_history(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verify publishing a revision and querying current vehicle and history."""
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
        canonical_fields={"make": "HONDA", "model": "ACCORD", "year": 2017},
        field_provenance={"make": [link], "model": [link], "year": [link]},
        conflicts=[],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )
    await store.publish(result)

    # Get current vehicle
    resp = await client.get(f"/v1/vehicles/{vin}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vin"] == vin
    assert data["revision_number"] == 1
    assert data["canonical_fields"]["make"] == "HONDA"
    assert data["confidence"]["score"] == 91
    assert data["confidence"]["band"] == "HIGH"

    # Get revision history
    resp_hist = await client.get(f"/v1/vehicles/{vin}/history")
    assert resp_hist.status_code == 200
    hist = resp_hist.json()
    assert len(hist) == 1
    assert hist[0]["revision_number"] == 1

    # Get revision 1 by number
    resp_rev1 = await client.get(f"/v1/vehicles/{vin}/revisions/1")
    assert resp_rev1.status_code == 200
    assert resp_rev1.json()["revision_number"] == 1
