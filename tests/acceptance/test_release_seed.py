"""Acceptance tests proving deterministic release seed execution and API scenarios (e04s03)."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.api.app import create_app
from nz_vehicle_data_pipeline.cli.seed import run_seed
from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER
from nz_vehicle_data_pipeline.persistence.database import get_db_session
from nz_vehicle_data_pipeline.persistence.models import (
    Base,
    CanonicalRevisionRow,
    SourceObservationRow,
)

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


async def test_release_seed_end_to_end_and_idempotency(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Prove release seed populates all scenarios and repeated runs produce zero duplicate rows."""
    manifest_path = Path(__file__).parent.parent.parent / "fixtures" / "manifest.json"

    # --- RUN 1 ---
    summary_1 = await run_seed(manifest_path=manifest_path, db_url=TEST_DB_URL)
    assert summary_1.manifest_id == "release-manifest-2026.08"
    assert summary_1.total_observations == 22
    assert summary_1.eligible_count == 19
    assert summary_1.rejected_count == 1  # Malformed PPSR
    assert summary_1.evidence_only_count == 2  # NZTA VIN11 records
    assert summary_1.vehicles_processed == 5
    assert summary_1.revisions_created == 5
    assert summary_1.revisions_reused == 0

    # Verify counts in PostgreSQL
    obs_count_1 = (
        await db_session.execute(select(func.count()).select_from(SourceObservationRow))
    ).scalar_one()
    rev_count_1 = (
        await db_session.execute(select(func.count()).select_from(CanonicalRevisionRow))
    ).scalar_one()

    assert obs_count_1 == 22
    assert rev_count_1 == 5

    # --- VERIFY SCENARIOS VIA API ---
    # Scenario 1: Clean Vehicle
    resp_clean = await client.get("/v1/vehicles/1HGCR2F85HA000000")
    assert resp_clean.status_code == 200
    clean_data = resp_clean.json()
    assert clean_data["canonical_fields"]["make"] == "HONDA"
    assert clean_data["canonical_fields"]["model"] == "ACCORD"
    assert clean_data["canonical_fields"]["stolen_status"] == "NOT_LISTED"
    assert clean_data["canonical_fields"]["writeoff_status"] == "NONE"
    assert clean_data["canonical_fields"]["ppsr_result"] == "NO_MATCH"
    assert clean_data["confidence"]["band"] == "MEDIUM"
    assert clean_data["confidence"]["score"] == 75
    assert clean_data["synthetic_notice"] == SYNTHETIC_DISCLAIMER

    # Scenario 2: Risky Vehicle
    resp_risky = await client.get("/v1/vehicles/1FA6P8CF8H5000000")
    assert resp_risky.status_code == 200
    risky_data = resp_risky.json()
    assert risky_data["canonical_fields"]["stolen_status"] == "LISTED"
    assert risky_data["canonical_fields"]["writeoff_status"] == "STATUTORY"
    assert risky_data["canonical_fields"]["ppsr_result"] == "MATCH"
    assert risky_data["confidence"]["band"] == "MEDIUM"

    # Scenario 3: Unknown Vehicle
    resp_unk = await client.get("/v1/vehicles/JM0BL10F000000000")
    assert resp_unk.status_code == 200
    unk_data = resp_unk.json()
    assert unk_data["canonical_fields"]["stolen_status"] == "UNKNOWN"
    assert unk_data["canonical_fields"]["writeoff_status"] == "UNKNOWN"
    assert unk_data["canonical_fields"]["ppsr_result"] == "UNKNOWN"

    # Scenario 4: Conflict Vehicle
    resp_conf = await client.get("/v1/vehicles/WAUZZZ8K7BA000000")
    assert resp_conf.status_code == 200
    conf_data = resp_conf.json()
    assert "ppsr_result" not in conf_data["canonical_fields"]
    assert any(c["field_name"] == "ppsr_result" for c in conf_data["conflicts"])
    assert conf_data["synthetic_notice"] == SYNTHETIC_DISCLAIMER

    # Scenario 5: Evidence-Only NZTA cannot be queried as canonical VIN
    resp_nzta = await client.get("/v1/vehicles/1HGCR2F85HA")
    assert resp_nzta.status_code == 422  # Fails 17-char VIN ISO 3779 validation

    # --- RUN 2 (IDEMPOTENCY) ---
    summary_2 = await run_seed(manifest_path=manifest_path, db_url=TEST_DB_URL)
    assert summary_2.revisions_created == 0
    assert summary_2.revisions_reused == 5

    # Check row counts in PostgreSQL remain exactly identical
    obs_count_2 = (
        await db_session.execute(select(func.count()).select_from(SourceObservationRow))
    ).scalar_one()
    rev_count_2 = (
        await db_session.execute(select(func.count()).select_from(CanonicalRevisionRow))
    ).scalar_one()

    assert obs_count_2 == obs_count_1
    assert rev_count_2 == rev_count_1
