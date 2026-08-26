"""Deterministic field resolution policies (ADR 0003)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictState,
    FieldConflict,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)

RESOLUTION_RULE_VERSION = "1.0.0"

SPEC_FIELDS: set[str] = {
    "make",
    "model",
    "year",
    "body_type",
    "vehicle_type",
    "engine_cylinders",
    "displacement_l",
    "manufacturer",
}

RISK_FIELDS: set[str] = {
    "ppsr_interests",
    "stolen_status",
    "stolen_report_date",
    "police_district",
    "writeoff_status",
    "writeoff_damage_date",
}


class FieldResolutionResult(BaseModel):
    """Outcome of applying deterministic resolution rule to one field."""

    model_config = ConfigDict(frozen=True)

    field_name: str = Field(description="Canonical field name")
    resolved_value: Any = Field(description="Selected canonical value")
    winning_provenance: ProvenanceLink = Field(description="Lineage of winning candidate")
    conflict: FieldConflict | None = Field(
        default=None, description="Resolved or detected conflict if present"
    )


class FieldResolver:
    """Applies versioned deterministic resolution policies to candidate values."""

    def resolve_field(
        self, field_name: str, candidates: list[CandidateValue]
    ) -> FieldResolutionResult:
        """Resolve a single field from candidate values with conflict detection."""
        if not candidates:
            msg = f"Cannot resolve field '{field_name}' with zero candidate values"
            raise ValueError(msg)

        # Check for conflicts
        first_val = candidates[0].value
        has_disagreement = any(c.value != first_val for c in candidates[1:])

        winner: CandidateValue
        conflict_obj: FieldConflict | None = None

        if not has_disagreement:
            # All candidates agree or single candidate exists
            winner = self._pick_authoritative(field_name, candidates)
        else:
            # Conflict detected - apply deterministic resolution policy
            winner = self._pick_authoritative(field_name, candidates)
            rationale = self._get_rationale(field_name, winner)

            conflict_obj = FieldConflict(
                field_name=field_name,
                conflicting_candidates=candidates,
                state=ConflictState.RESOLVED,
                winning_candidate=winner,
                rule_version=RESOLUTION_RULE_VERSION,
                rationale=rationale,
                resolved_at=datetime.now(UTC),
            )

        return FieldResolutionResult(
            field_name=field_name,
            resolved_value=winner.value,
            winning_provenance=winner.provenance,
            conflict=conflict_obj,
        )

    def _pick_authoritative(
        self, field_name: str, candidates: list[CandidateValue]
    ) -> CandidateValue:
        """Select the authoritative candidate according to field domain policy."""
        if field_name in SPEC_FIELDS:
            # NHTSA vPIC is authoritative for vehicle factory specifications
            nhtsa_match = next(
                (c for c in candidates if c.provenance.source_system == SourceSystem.NHTSA_VPIC),
                None,
            )
            if nhtsa_match:
                return nhtsa_match

        if field_name == "ppsr_interests":
            ppsr_match = next(
                (
                    c
                    for c in candidates
                    if c.provenance.source_system == SourceSystem.PPSR_SYNTHETIC
                ),
                None,
            )
            if ppsr_match:
                return ppsr_match

        if field_name in {"stolen_status", "stolen_report_date", "police_district"}:
            stolen_match = next(
                (
                    c
                    for c in candidates
                    if c.provenance.source_system == SourceSystem.STOLEN_SYNTHETIC
                ),
                None,
            )
            if stolen_match:
                return stolen_match

        if field_name in {"writeoff_status", "writeoff_damage_date"}:
            wo_match = next(
                (
                    c
                    for c in candidates
                    if c.provenance.source_system == SourceSystem.WRITEOFF_SYNTHETIC
                ),
                None,
            )
            if wo_match:
                return wo_match

        # Default / fallback: return first candidate
        return candidates[0]

    def _get_rationale(self, field_name: str, winner: CandidateValue) -> str:
        """Return rationale string explaining resolution outcome."""
        src = winner.provenance.source_system.value
        if field_name in SPEC_FIELDS:
            return (
                f"NHTSA manufacturer VIN decode is authoritative "
                f"for specification field '{field_name}' (winner: {src})"
            )
        if field_name in RISK_FIELDS:
            return (
                f"Dedicated incident/risk register is authoritative "
                f"for '{field_name}' (winner: {src})"
            )
        return f"Deterministic policy selected candidate from {src} for '{field_name}'"
