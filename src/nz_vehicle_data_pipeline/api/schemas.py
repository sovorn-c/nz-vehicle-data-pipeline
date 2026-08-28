"""OpenAPI schemas for external REST API boundaries (ADR 0004, ADR 0005)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.reconciliation.confidence import ConfidenceAssessment
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink


class VehicleRevisionResponse(BaseModel):
    """Canonical vehicle revision representation."""

    model_config = ConfigDict(frozen=True)

    vin: str = Field(description="Canonical 17-character VIN")
    revision_id: str = Field(description="Unique revision identifier")
    revision_number: int = Field(description="Monotonic revision number")
    material_hash: str = Field(description="SHA-256 fingerprint of canonical material")
    canonical_fields: dict[str, Any] = Field(description="Resolved canonical fields")
    field_provenance: dict[str, list[ProvenanceLink]] = Field(
        description="Lineage to all supporting source observations"
    )
    conflicts: list[FieldConflict] = Field(
        default_factory=list, description="Recorded field conflicts"
    )
    confidence: ConfidenceAssessment = Field(description="Confidence assessment")
    as_of: datetime = Field(description="Evaluation timestamp")
    published_at: datetime = Field(description="Database publication timestamp")
    synthetic_notice: str | None = Field(
        default=None,
        description="Disclaimer notice when record contains synthetic demonstration data",
    )


class ObservationDetailResponse(BaseModel):
    """Full detail of an immutable source observation including raw payload."""

    model_config = ConfigDict(frozen=True)

    observation_id: str = Field(description="Unique observation identifier")
    source_system: str = Field(description="Originating source system")
    source_record_id: str = Field(description="Record ID in source")
    ingestion_run_id: str = Field(description="Ingestion batch run ID")
    raw_payload: str = Field(description="Exact raw payload string")
    payload_hash_sha256: str = Field(description="SHA-256 hash of payload")
    retrieved_at: datetime = Field(description="Timestamp retrieved from source")
    synthetic: bool = Field(description="Synthetic data indicator flag")


class ErrorResponse(BaseModel):
    """Structured error message."""

    detail: str = Field(description="Human-readable error explanation")


class VehicleSummary(BaseModel):
    """High-level summary of a canonical vehicle for catalog discovery."""

    model_config = ConfigDict(frozen=True)

    vin: str = Field(description="Canonical 17-character VIN")
    make: str | None = Field(default=None, description="Reconciled vehicle make")
    model: str | None = Field(default=None, description="Reconciled vehicle model")
    year: int | None = Field(default=None, description="Reconciled model year")
    registration_status: str | None = Field(default=None, description="Current registration status")
    confidence_score: float | None = Field(
        default=None, description="Overall confidence score (0.0 - 1.0)"
    )
    has_conflicts: bool = Field(
        default=False, description="True if any unresolved field conflicts exist"
    )
    revision_number: int = Field(default=1, description="Latest revision number")
    synthetic: bool = Field(default=False, description="True if record incorporates synthetic data")


class VehicleCatalogPage(BaseModel):
    """Paginated collection of canonical vehicle summaries."""

    model_config = ConfigDict(frozen=True)

    items: list[VehicleSummary] = Field(description="List of vehicle summaries")
    total: int = Field(ge=0, description="Total canonical vehicles matching query")
    limit: int = Field(ge=1, description="Page size limit")
    offset: int = Field(ge=0, description="Page offset")
    disclaimer: str | None = Field(default=None, description="Synthetic data limitation notice")
