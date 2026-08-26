"""Deterministic field resolution policies and authority weights (ADR 0003)."""

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

RESOLUTION_RULE_VERSION = "resolution-v1"

SOURCE_AUTHORITIES: dict[SourceSystem, int] = {
    SourceSystem.NHTSA_VPIC: 100,
    SourceSystem.DEALER_FEED: 60,
}


class FieldResolutionResult(BaseModel):
    """Outcome of applying deterministic resolution rule to one field."""

    model_config = ConfigDict(frozen=True)

    field_name: str = Field(description="Canonical field name")
    resolved_value: Any | None = Field(
        default=None, description="Selected canonical value or None if unresolved"
    )
    supporting_provenance: list[ProvenanceLink] = Field(
        default_factory=list,
        description="All source observations supporting the selected value",
    )
    conflict: FieldConflict | None = Field(
        default=None, description="Resolved or unresolved conflict if present"
    )


class FieldResolver:
    """Applies versioned deterministic resolution policies to candidate values (ADR 0003)."""

    def resolve_field(
        self, field_name: str, candidates: list[CandidateValue]
    ) -> FieldResolutionResult:
        """Resolve a single field from candidate values with authority-based tie breaking."""
        if not candidates:
            msg = f"Cannot resolve field '{field_name}' with zero candidate values"
            raise ValueError(msg)

        # Group candidates by exact value
        by_value: dict[Any, list[CandidateValue]] = {}
        for c in candidates:
            by_value.setdefault(c.value, []).append(c)

        # Single distinct candidate value -> No conflict
        if len(by_value) == 1:
            val = list(by_value.keys())[0]
            provs = [c.provenance for c in by_value[val]]
            # Sort provenance for determinism
            provs.sort(key=lambda p: p.observation_id)
            return FieldResolutionResult(
                field_name=field_name,
                resolved_value=val,
                supporting_provenance=provs,
                conflict=None,
            )

        # Multiple distinct values -> Conflict exists
        value_authorities: dict[Any, int] = {}
        for val, val_cands in by_value.items():
            max_auth = max(
                SOURCE_AUTHORITIES.get(c.provenance.source_system, 50) for c in val_cands
            )
            value_authorities[val] = max_auth

        highest_auth = max(value_authorities.values())
        top_values = [val for val, auth in value_authorities.items() if auth == highest_auth]

        if len(top_values) == 1:
            # Single highest-authority winner
            winning_val = top_values[0]
            winning_cands = by_value[winning_val]
            winning_provs = [c.provenance for c in winning_cands]
            winning_provs.sort(key=lambda p: p.observation_id)

            winning_src = winning_cands[0].provenance.source_system.value
            conflict = FieldConflict(
                field_name=field_name,
                conflicting_candidates=candidates,
                state=ConflictState.RESOLVED,
                winning_value=winning_val,
                rule_version=RESOLUTION_RULE_VERSION,
                rationale=(
                    f"Higher authority {winning_src} ({highest_auth}) "
                    f"wins over competing candidate values"
                ),
            )

            return FieldResolutionResult(
                field_name=field_name,
                resolved_value=winning_val,
                supporting_provenance=winning_provs,
                conflict=conflict,
            )

        # Tied at highest authority -> UNRESOLVED conflict, no canonical value
        conflict = FieldConflict(
            field_name=field_name,
            conflicting_candidates=candidates,
            state=ConflictState.UNRESOLVED,
            winning_value=None,
            rule_version=RESOLUTION_RULE_VERSION,
            rationale=(
                f"Equal authority disagreement ({highest_auth}) "
                f"cannot be resolved without human intervention"
            ),
        )

        return FieldResolutionResult(
            field_name=field_name,
            resolved_value=None,
            supporting_provenance=[],
            conflict=conflict,
        )
