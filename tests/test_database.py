"""Unit tests for database URL compatibility."""

import pytest
from alembic.config import Config
from sqlalchemy.exc import OperationalError

from alembic import command
from nz_vehicle_data_pipeline.persistence.database import get_engine


async def test_get_engine_accepts_standard_postgresql_uri() -> None:
    """Use the installed async Psycopg driver for a standard PostgreSQL URI."""
    engine = get_engine("postgresql://user:password@localhost:5432/vehicle")
    try:
        assert engine.sync_engine.dialect.driver == "psycopg"
        assert engine.sync_engine.dialect.is_async
    finally:
        await engine.dispose()


def test_alembic_accepts_standard_postgresql_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run migration setup with a standard URI instead of importing Psycopg 2."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@127.0.0.1:1/vehicle")
    config = Config("alembic.ini")

    with pytest.raises(OperationalError) as error:
        command.upgrade(config, "head")

    message = str(error.value).lower()
    assert "psycopg2" not in message
    assert "connection" in message
