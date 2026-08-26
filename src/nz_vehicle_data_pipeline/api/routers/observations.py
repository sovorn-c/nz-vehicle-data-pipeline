"""FastAPI router for inspecting raw immutable source observations (e03s04)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from nz_vehicle_data_pipeline.api.schemas import (
    ErrorResponse,
    ObservationDetailResponse,
)
from nz_vehicle_data_pipeline.persistence.database import get_db_session
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)

router = APIRouter(prefix="/v1/observations", tags=["observations"])


def get_observation_store(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresObservationStore:
    """Dependency injecting PostgresObservationStore."""
    return PostgresObservationStore(session)


@router.get(
    "/{observation_id}",
    response_model=ObservationDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get raw source observation detail",
)
async def get_observation_detail(
    observation_id: str,
    store: Annotated[PostgresObservationStore, Depends(get_observation_store)],
) -> ObservationDetailResponse:
    """Retrieve full raw source evidence for an observation by ID."""
    obs = await store.get_by_id(observation_id)
    if obs is None:
        raise HTTPException(
            status_code=404,
            detail=f"Observation '{observation_id}' not found",
        )
    return ObservationDetailResponse(
        observation_id=obs.observation_id,
        source_system=obs.source_system.value,
        source_record_id=obs.source_record_id,
        ingestion_run_id=obs.ingestion_run_id,
        raw_payload=obs.raw_payload,
        payload_hash_sha256=obs.payload_hash_sha256,
        retrieved_at=obs.retrieved_at,
        synthetic=obs.synthetic,
    )
