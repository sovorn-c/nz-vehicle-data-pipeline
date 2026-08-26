"""Provenance lineage tracking and candidate value models (ADR 0001, ADR 0003)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.observation.models import SourceSystem


class ProvenanceLink(BaseModel):
    """Immutable trace pointing back to the exact source observation."""

    model_config = ConfigDict(frozen=True)

    observation_id: str = Field(description="Unique observation identifier")
    source_system: SourceSystem = Field(description="Originating source system")
    source_record_id: str = Field(description="Record/row ID in source")
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp observation was retrieved",
    )
    synthetic: bool = Field(
        default=False, description="Flag indicating synthetic demonstration source"
    )


class CandidateValue(BaseModel):
    """Normalized field value proposed by one source observation."""

    model_config = ConfigDict(frozen=True)

    field_name: str = Field(description="Canonical field name")
    value: Any = Field(description="Extracted attribute value")
    provenance: ProvenanceLink = Field(description="Lineage to source observation")
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp value was extracted",
    )
