"""Canonical vehicle revision models and material change detection (ADR 0001, ADR 0003)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.reconciliation.confidence import ConfidenceAssessment
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink


class CanonicalRevision(BaseModel):
    """Immutable published state of a canonical vehicle record (ADR 0001)."""

    model_config = ConfigDict(frozen=True)

    revision_id: str = Field(description="Unique identifier for this canonical revision")
    vin: str = Field(description="Canonical 17-character VIN")
    revision_number: int = Field(description="Monotonically increasing revision sequence")
    canonical_fields: dict[str, Any] = Field(
        description="Resolved canonical attribute key-value pairs"
    )
    field_provenance: dict[str, ProvenanceLink] = Field(
        description="Trace from every canonical field to winning source observation"
    )
    conflicts: list[FieldConflict] = Field(
        default_factory=list, description="Recorded field conflicts in this revision"
    )
    confidence: ConfidenceAssessment = Field(
        description="Reproducible confidence score for this revision"
    )
    reconciled_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when revision was created",
    )


class MaterialChangeDetector:
    """Detects whether proposed reconciliation result differs materially from previous revision."""

    def has_material_change(
        self,
        previous: CanonicalRevision | None,
        candidate_fields: dict[str, Any],
        candidate_provenance: dict[str, ProvenanceLink],
        candidate_conflicts: list[FieldConflict],
        candidate_confidence: ConfidenceAssessment,
    ) -> bool:
        """Return True if material changes exist, False if reprocessing is identical."""
        if previous is None:
            return True

        if previous.canonical_fields != candidate_fields:
            return True

        if previous.confidence.score != candidate_confidence.score:
            return True

        if previous.confidence.band != candidate_confidence.band:
            return True

        if len(previous.conflicts) != len(candidate_conflicts):
            return True

        prev_conflict_states = {
            (
                c.field_name,
                c.state.value,
                c.winning_candidate.value if c.winning_candidate else None,
            )
            for c in previous.conflicts
        }
        cand_conflict_states = {
            (
                c.field_name,
                c.state.value,
                c.winning_candidate.value if c.winning_candidate else None,
            )
            for c in candidate_conflicts
        }
        if prev_conflict_states != cand_conflict_states:
            return True

        prev_prov = {k: v.observation_id for k, v in previous.field_provenance.items()}
        cand_prov = {k: v.observation_id for k, v in candidate_provenance.items()}
        return prev_prov != cand_prov
