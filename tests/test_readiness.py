"""Unit tests for /health liveness and /ready database probe (e04s04)."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nz_vehicle_data_pipeline.api.app import create_app
from nz_vehicle_data_pipeline.persistence.database import get_db_session


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_check_returns_ok(client: httpx.AsyncClient) -> None:
    """Verify /health returns 200 process liveness status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readiness_probe_success() -> None:
    """Verify /ready returns 200 when database probe succeeds."""
    app = create_app()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready", "database": "connected"}


async def test_readiness_probe_failure_returns_503() -> None:
    """Verify /ready returns 503 when database probe fails."""
    app = create_app()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=ConnectionRefusedError("Database down"))

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/ready")
        assert resp.status_code == 503
        assert resp.json() == {"status": "unavailable", "database": "unreachable"}
