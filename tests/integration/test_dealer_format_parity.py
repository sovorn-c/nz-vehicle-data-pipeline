"""Integration test proving semantic parity between dealer JSON and XML representations (e04s02)."""

import json
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.api.app import create_app
from nz_vehicle_data_pipeline.normalization.engine import (
    NormalizationEngine,
    NormalizedObservation,
)
from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.database import get_db_session
from nz_vehicle_data_pipeline.persistence.models import Base
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)
from nz_vehicle_data_pipeline.reconciliation.engine import ReconciliationEngine

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
)

VIN = "1HGCR2F85HA000000"

JSON_PAYLOAD = json.dumps(
    {
        "dealer_id": "DLR_99",
        "listing_id": "LST_PARITY_1",
        "vin": VIN,
        "make": "HONDA",
        "model": "ACCORD",
        "model_year": 2017,
        "trim": "EX-L",
        "condition": "EXCELLENT",
        "price_cents": 2350000,
        "currency": "NZD",
        "odometer_km": 42000,
        "availability": "AVAILABLE",
        "image_urls": ["https://example.com/a.jpg"],
        "metadata": {
            "synthetic": True,
            "dataset_id": "dealer-parity",
            "dataset_version": "1.0",
            "scenario_id": "parity_check",
            "generated_at": "2026-08-01T10:00:00Z",
            "disclaimer": SYNTHETIC_DISCLAIMER,
        },
    }
)

XML_PAYLOAD = f"""<?xml version="1.0" encoding="UTF-8"?>
<dealer-listing>
    <dealer_id>DLR_99</dealer_id>
    <listing_id>LST_PARITY_1</listing_id>
    <vin>{VIN}</vin>
    <make>HONDA</make>
    <model>ACCORD</model>
    <model_year>2017</model_year>
    <trim>EX-L</trim>
    <condition>EXCELLENT</condition>
    <price_cents>2350000</price_cents>
    <currency>NZD</currency>
    <odometer_km>42000</odometer_km>
    <availability>AVAILABLE</availability>
    <image_urls>
        <image_url>https://example.com/a.jpg</image_url>
    </image_urls>
    <metadata>
        <synthetic>true</synthetic>
        <dataset_id>dealer-parity</dataset_id>
        <dataset_version>1.0</dataset_version>
        <scenario_id>parity_check</scenario_id>
        <generated_at>2026-08-01T10:00:00Z</generated_at>
        <disclaimer>{SYNTHETIC_DISCLAIMER}</disclaimer>
    </metadata>
</dealer-listing>
"""


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


async def test_dealer_json_and_xml_semantic_parity(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Prove JSON and XML dealer representations produce identical semantic outcomes."""
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    norm_engine = NormalizationEngine()
    reconciler = ReconciliationEngine()
    obs_store = PostgresObservationStore(db_session)
    can_store = PostgresCanonicalStore(db_session)

    # 1. Capture JSON observation
    obs_json = SourceObservation(
        observation_id="obs_json_1",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_json",
        source_record_id="dealer_json_LST_PARITY_1",
        raw_payload=JSON_PAYLOAD,
        retrieved_at=as_of,
        synthetic=True,
    )
    await obs_store.save(obs_json)

    # 2. Capture XML observation
    obs_xml = SourceObservation(
        observation_id="obs_xml_1",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_xml",
        source_record_id="dealer_xml_LST_PARITY_1",
        raw_payload=XML_PAYLOAD,
        retrieved_at=as_of,
        synthetic=True,
    )
    await obs_store.save(obs_xml)

    # Payloads and hashes must remain distinct
    assert obs_json.raw_payload != obs_xml.raw_payload
    assert obs_json.payload_hash_sha256 != obs_xml.payload_hash_sha256

    # 3. Normalization semantic equivalence
    norm_json = norm_engine.normalize(obs_json)
    norm_xml = norm_engine.normalize(obs_xml)
    assert isinstance(norm_json, NormalizedObservation)
    assert isinstance(norm_xml, NormalizedObservation)
    assert norm_json.staged_data == norm_xml.staged_data

    # 4. Reconciliation semantic equivalence
    res_json = await reconciler.reconcile(
        vin=VIN, eligible_pairs=[(obs_json, norm_json)], as_of=as_of
    )
    res_xml = await reconciler.reconcile(vin=VIN, eligible_pairs=[(obs_xml, norm_xml)], as_of=as_of)

    assert res_json.canonical_fields == res_xml.canonical_fields
    assert res_json.conflicts == res_xml.conflicts
    assert res_json.confidence.score == res_xml.confidence.score

    # 5. Publication and API check for XML representation
    rev_xml, created = await can_store.publish(res_xml)
    assert created is True

    resp = await client.get(f"/v1/vehicles/{VIN}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_fields"]["make"] == "HONDA"
    assert data["canonical_fields"]["model"] == "ACCORD"
    assert data["canonical_fields"]["asking_price_cents"] == 2350000
    assert data["synthetic_notice"] == SYNTHETIC_DISCLAIMER
    assert "raw_payload" not in data

    # 6. Retrieve exact raw XML via observation detail
    obs_resp = await client.get("/v1/observations/obs_xml_1")
    assert obs_resp.status_code == 200
    obs_data = obs_resp.json()
    assert obs_data["raw_payload"] == XML_PAYLOAD
    assert obs_data["synthetic"] is True
