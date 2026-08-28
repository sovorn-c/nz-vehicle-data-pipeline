"""Integration tests for GET /v1/vehicles catalog endpoint (e05s01)."""

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


def _publish_result(vin: str, make: str = "Toyota", model: str = "Corolla") -> ReconciliationResult:
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
        canonical_fields={
            "make": make,
            "model": model,
            "year": 2021,
            "registration_status": "active",
        },
        field_provenance={"make": [prov], "model": [prov]},
        conflicts=[],
        confidence=ConfidenceAssessment(
            score=95,
            band=ConfidenceBand.HIGH,
            field_scores={"make": 95},
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


async def test_get_vehicles_empty_catalog(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["limit"] == 20
    assert data["offset"] == 0


async def test_get_vehicles_paginates_and_sorts(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    store = PostgresCanonicalStore(db_session)
    for v in ["7A8HB000000000003", "7A8HB000000000001", "7A8HB000000000002"]:
        await store.publish(_publish_result(v))

    resp = await client.get("/v1/vehicles?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["items"][0]["vin"] == "7A8HB000000000001"
    assert data["items"][0]["make"] == "Toyota"
    assert data["items"][0]["model"] == "Corolla"
    assert data["items"][0]["year"] == 2021
    assert data["items"][0]["synthetic"] is True
    assert data["items"][1]["vin"] == "7A8HB000000000002"
    assert "no real vehicle" in data["disclaimer"].lower()

    # Next page
    resp2 = await client.get("/v1/vehicles?limit=2&offset=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 3
    assert len(data2["items"]) == 1
    assert data2["items"][0]["vin"] == "7A8HB000000000003"


async def test_get_vehicles_validation_errors(client: httpx.AsyncClient) -> None:
    resp_limit = await client.get("/v1/vehicles?limit=101")
    assert resp_limit.status_code == 422

    resp_offset = await client.get("/v1/vehicles?offset=-1")
    assert resp_offset.status_code == 422
