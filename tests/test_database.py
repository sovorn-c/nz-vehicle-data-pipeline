"""Unit tests for database URL compatibility."""

from nz_vehicle_data_pipeline.persistence.database import get_engine


async def test_get_engine_accepts_standard_postgresql_uri() -> None:
    """Use the installed async Psycopg driver for a standard PostgreSQL URI."""
    engine = get_engine("postgresql://user:password@localhost:5432/vehicle")
    try:
        assert engine.sync_engine.dialect.driver == "psycopg"
        assert engine.sync_engine.dialect.is_async
    finally:
        await engine.dispose()
