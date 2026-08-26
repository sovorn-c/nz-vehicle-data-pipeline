"""FastAPI router for vehicle entities, revision history, conflicts, and provenance."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from nz_vehicle_data_pipeline.api.schemas import (
    ErrorResponse,
    VehicleRevisionResponse,
)
from nz_vehicle_data_pipeline.identity.vin import validate_vin
from nz_vehicle_data_pipeline.persistence.canonical_store import (
    PostgresCanonicalStore,
)
from nz_vehicle_data_pipeline.persistence.database import get_db_session
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink

router = APIRouter(prefix="/v1/vehicles", tags=["vehicles"])


def get_canonical_store(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresCanonicalStore:
    """Dependency injecting PostgresCanonicalStore."""
    return PostgresCanonicalStore(session)


def get_normalized_vin(vin: str) -> str:
    """Validate and normalize path VIN parameter using 17-character ISO 3779 checksum validator."""
    res = validate_vin(vin)
    if not res.is_valid or not res.normalized_vin:
        raise HTTPException(
            status_code=422,
            detail=(f"Invalid 17-character VIN: '{vin}'. Reason: {res.error_reason}"),
        )
    return res.normalized_vin


@router.get(
    "/{vin}",
    response_model=VehicleRevisionResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get current canonical vehicle record",
)
async def get_current_vehicle(
    vin: Annotated[str, Depends(get_normalized_vin)],
    store: Annotated[PostgresCanonicalStore, Depends(get_canonical_store)],
) -> VehicleRevisionResponse:
    """Retrieve the latest canonical revision for a vehicle by VIN."""
    revision = await store.get_current_revision(vin)
    if revision is None:
        raise HTTPException(status_code=404, detail=f"Vehicle with VIN '{vin}' not found")
    return VehicleRevisionResponse.model_validate(revision.model_dump())


@router.get(
    "/{vin}/history",
    response_model=list[VehicleRevisionResponse],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get revision history for a vehicle",
)
@router.get(
    "/{vin}/revisions",
    response_model=list[VehicleRevisionResponse],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get revision history for a vehicle (alias)",
)
async def get_vehicle_history(
    vin: Annotated[str, Depends(get_normalized_vin)],
    store: Annotated[PostgresCanonicalStore, Depends(get_canonical_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    before_revision: Annotated[int | None, Query(ge=1)] = None,
    cursor: Annotated[int | None, Query(ge=1)] = None,
) -> list[VehicleRevisionResponse]:
    """Retrieve all published historical revisions for a vehicle in newest-first order."""
    eff_cursor = before_revision if before_revision is not None else cursor
    history = await store.get_revision_history(vin, limit=limit, cursor=eff_cursor)
    return [VehicleRevisionResponse.model_validate(r.model_dump()) for r in history]


@router.get(
    "/{vin}/revisions/{revision_number}",
    response_model=VehicleRevisionResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get specific canonical revision by number",
)
async def get_vehicle_revision(
    vin: Annotated[str, Depends(get_normalized_vin)],
    revision_number: int,
    store: Annotated[PostgresCanonicalStore, Depends(get_canonical_store)],
) -> VehicleRevisionResponse:
    """Retrieve a specific historical revision by its monotonic number."""
    revision = await store.get_revision_by_number(vin, revision_number)
    if revision is None:
        raise HTTPException(
            status_code=404,
            detail=(f"Revision {revision_number} for vehicle with VIN '{vin}' not found"),
        )
    return VehicleRevisionResponse.model_validate(revision.model_dump())


@router.get(
    "/{vin}/conflicts",
    response_model=list[FieldConflict],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get conflicts recorded on the current vehicle revision",
)
async def get_vehicle_conflicts(
    vin: Annotated[str, Depends(get_normalized_vin)],
    store: Annotated[PostgresCanonicalStore, Depends(get_canonical_store)],
) -> list[FieldConflict]:
    """Retrieve all field conflicts recorded on the current revision."""
    revision = await store.get_current_revision(vin)
    if revision is None:
        raise HTTPException(status_code=404, detail=f"Vehicle with VIN '{vin}' not found")
    return revision.conflicts


@router.get(
    "/{vin}/provenance",
    response_model=dict[str, list[ProvenanceLink]],
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get field-level provenance traces for the current revision",
)
async def get_vehicle_provenance(
    vin: Annotated[str, Depends(get_normalized_vin)],
    store: Annotated[PostgresCanonicalStore, Depends(get_canonical_store)],
) -> dict[str, list[ProvenanceLink]]:
    """Retrieve winning and supporting provenance links for every canonical field."""
    revision = await store.get_current_revision(vin)
    if revision is None:
        raise HTTPException(status_code=404, detail=f"Vehicle with VIN '{vin}' not found")
    return revision.field_provenance
