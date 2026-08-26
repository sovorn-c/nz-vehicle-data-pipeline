"""FastAPI application factory and lifespan configuration (ADR 0004)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nz_vehicle_data_pipeline.api.routers import observations, vehicles
from nz_vehicle_data_pipeline.persistence.database import get_engine, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and clean resource shutdown."""
    engine = get_engine()
    await init_db(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    application = FastAPI(
        title="NZ Vehicle Data Pipeline API",
        version="0.1.0",
        description=(
            "Canonical NZ vehicle records with immutable provenance and conflict tracking"
        ),
        lifespan=lifespan,
    )

    application.include_router(vehicles.router)
    application.include_router(observations.router)

    @application.get("/health", tags=["system"], summary="Health check")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
