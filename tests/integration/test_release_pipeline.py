"""Integration tests for ReleasePipeline orchestrator (e04s03)."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.connectors.dealer import SyntheticDealerConnector
from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.nzta_csv import NZTAFleetCSVConnector
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector
from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER
from nz_vehicle_data_pipeline.persistence.canonical_store import PostgresCanonicalStore
from nz_vehicle_data_pipeline.persistence.models import Base
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)
from nz_vehicle_data_pipeline.pipeline.release_runner import ReleasePipeline

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
)

VIN_1 = "1HGCR2F85HA000000"
VIN_2 = "1FA6P8CF8H5000000"


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


async def test_release_pipeline_runs_all_connectors_and_publishes_revisions(
    db_session: AsyncSession,
) -> None:
    """Verify ReleasePipeline executes ingestion across connectors, groups by VIN, and publishes."""
    obs_store = PostgresObservationStore(db_session)
    can_store = PostgresCanonicalStore(db_session)
    pipeline = ReleasePipeline(obs_store=obs_store, canonical_store=can_store)

    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    # 1. NHTSA connector
    nhtsa_conn = NHTSAVPICConnector(
        data=[
            {
                "VIN": VIN_1,
                "Make": "HONDA",
                "Model": "ACCORD",
                "ModelYear": 2017,
                "VehicleType": "PASSENGER CAR",
            },
            {
                "VIN": VIN_2,
                "Make": "FORD",
                "Model": "MUSTANG",
                "ModelYear": 2018,
                "VehicleType": "PASSENGER CAR",
            },
        ]
    )

    # 2. PPSR connector (clean NO_MATCH for VIN_1)
    ppsr_conn = SyntheticPPSRConnector(
        data=[
            {
                "ppsr_id": "PPSR_101",
                "vin": VIN_1,
                "search_timestamp": "2026-08-01T12:00:00Z",
                "result": "NO_MATCH",
                "interests": [],
                "metadata": {
                    "synthetic": True,
                    "dataset_id": "ds",
                    "dataset_version": "1.0",
                    "scenario_id": "clean",
                    "generated_at": "2026-08-01T10:00:00Z",
                    "disclaimer": SYNTHETIC_DISCLAIMER,
                },
            }
        ]
    )

    # 3. NZTA Fleet CSV (EVIDENCE_ONLY)
    nzta_csv = "MAKE,MODEL,YEAR,VIN11,CHASSIS7\nHONDA,ACCORD,2017,1HGCR2F85HA,1234567\n"
    nzta_conn = NZTAFleetCSVConnector(csv_content=nzta_csv)

    # 4. Dealer connector
    dealer_conn = SyntheticDealerConnector(
        data=[
            {
                "dealer_id": "D_1",
                "listing_id": "L_1",
                "vin": VIN_1,
                "price_cents": 2100000,
                "odometer_km": 45000,
                "metadata": {
                    "synthetic": True,
                    "dataset_id": "ds",
                    "dataset_version": "1.0",
                    "scenario_id": "clean",
                    "generated_at": "2026-08-01T10:00:00Z",
                    "disclaimer": SYNTHETIC_DISCLAIMER,
                },
            }
        ]
    )

    # Execute run
    summary = await pipeline.run(
        connectors=[nhtsa_conn, ppsr_conn, nzta_conn, dealer_conn],
        as_of=as_of,
        manifest_id="test_manifest_01",
    )

    assert summary.manifest_id == "test_manifest_01"
    assert summary.total_observations == 5
    assert summary.evidence_only_count == 1  # NZTA
    assert summary.vehicles_processed == 2
    assert summary.revisions_created == 2
    assert summary.revisions_reused == 0

    # Verify lexical order of VIN outcomes
    assert [v.vin for v in summary.vin_outcomes] == [VIN_2, VIN_1]

    # Verify second run produces revisions_reused == 2, revisions_created == 0
    summary_2 = await pipeline.run(
        connectors=[nhtsa_conn, ppsr_conn, nzta_conn, dealer_conn],
        as_of=as_of,
        manifest_id="test_manifest_01",
    )
    assert summary_2.revisions_created == 0
    assert summary_2.revisions_reused == 2
