"""Integration tests for multi-revision vehicle history scenario (e05s02)."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.api.app import create_app
from nz_vehicle_data_pipeline.cli.seed import run_seed
from nz_vehicle_data_pipeline.persistence.database import get_db_session
from nz_vehicle_data_pipeline.persistence.models import (
    Base,
    CanonicalRevisionRow,
)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
)
VIN_MULTI = "1HGCR2F85HA000000"


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


async def test_multi_revision_history_end_to_end(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verify multi-revision creates Rev 1 and 2, queries history, and checks idempotency."""
    manifest_path = Path(__file__).parent.parent.parent / "fixtures" / "manifest.json"

    # Seed with Phase 1 and Phase 2 enabled
    summary = await run_seed(manifest_path=manifest_path, db_url=TEST_DB_URL, enable_phase2=True)
    assert summary.vehicles_processed >= 1

    # Check total revisions in DB for VIN_MULTI
    rev_count = (
        await db_session.execute(
            select(func.count())
            .select_from(CanonicalRevisionRow)
            .where(CanonicalRevisionRow.vin == VIN_MULTI)
        )
    ).scalar_one()
    assert rev_count == 2, f"Expected 2 revisions for {VIN_MULTI}, found {rev_count}"

    # 1. GET current vehicle (should be Revision 2)
    resp_curr = await client.get(f"/v1/vehicles/{VIN_MULTI}")
    assert resp_curr.status_code == 200
    curr_data = resp_curr.json()
    assert curr_data["revision_number"] == 2
    assert curr_data["canonical_fields"]["asking_price_cents"] == 1995000
    assert curr_data["canonical_fields"]["odometer_km"] == 52300

    # 2. GET history (should return [Rev 2, Rev 1] in descending order)
    resp_hist = await client.get(f"/v1/vehicles/{VIN_MULTI}/history")
    assert resp_hist.status_code == 200
    history = resp_hist.json()
    assert len(history) == 2
    assert history[0]["revision_number"] == 2
    assert history[1]["revision_number"] == 1
    assert history[0]["canonical_fields"]["asking_price_cents"] == 1995000
    assert history[1]["canonical_fields"]["asking_price_cents"] == 2150000

    # Verify provenance points to different observations
    rev2_prov = history[0]["field_provenance"]["asking_price_cents"]
    rev1_prov = history[1]["field_provenance"]["asking_price_cents"]
    assert rev2_prov != rev1_prov
    assert any("UPDATE" in p["source_record_id"] for p in rev2_prov)

    # 3. GET specific revision 1
    resp_r1 = await client.get(f"/v1/vehicles/{VIN_MULTI}/revisions/1")
    assert resp_r1.status_code == 200
    r1_data = resp_r1.json()
    assert r1_data["revision_number"] == 1
    assert r1_data["canonical_fields"]["asking_price_cents"] == 2150000

    # 4. GET specific revision 2
    resp_r2 = await client.get(f"/v1/vehicles/{VIN_MULTI}/revisions/2")
    assert resp_r2.status_code == 200
    r2_data = resp_r2.json()
    assert r2_data["revision_number"] == 2
    assert r2_data["canonical_fields"]["asking_price_cents"] == 1995000

    # 5. Idempotent replay: running seed again creates no new revisions
    summary_replay = await run_seed(
        manifest_path=manifest_path, db_url=TEST_DB_URL, enable_phase2=True
    )
    assert summary_replay.revisions_created == 0
    assert summary_replay.revisions_reused == 1

    rev_count_after = (
        await db_session.execute(
            select(func.count())
            .select_from(CanonicalRevisionRow)
            .where(CanonicalRevisionRow.vin == VIN_MULTI)
        )
    ).scalar_one()
    assert rev_count_after == 2
