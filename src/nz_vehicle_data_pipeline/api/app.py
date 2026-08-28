"""FastAPI application factory and lifespan configuration (ADR 0004, e04s04)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nz_vehicle_data_pipeline.api.docs import DOCS_HTML
from nz_vehicle_data_pipeline.api.routers import observations, vehicles
from nz_vehicle_data_pipeline.persistence.database import (
    get_db_session,
    get_engine,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and clean resource shutdown."""
    engine = get_engine()
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
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    application.include_router(vehicles.router)
    application.include_router(observations.router)

    @application.get("/docs", include_in_schema=False, response_class=HTMLResponse)
    async def documentation_page() -> HTMLResponse:
        """Serve the branded API documentation explorer."""
        return HTMLResponse(content=DOCS_HTML)

    @application.get("/health", tags=["system"], summary="Process liveness check")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(
        "/ready",
        tags=["system"],
        summary="Database readiness probe",
        response_model=dict[str, str],
    )
    async def readiness_probe(
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> Response:
        try:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
            return JSONResponse(
                status_code=200,
                content={"status": "ready", "database": "connected"},
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "database": "unreachable"},
            )

    return application


app = create_app()
