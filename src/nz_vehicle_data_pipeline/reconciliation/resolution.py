"""Deterministic field resolution policies and authority weights (ADR 0003, ADR 0005)."""

import json
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
    SourceSystem.PPSR_SYNTHETIC: 60,
    SourceSystem.STOLEN_SYNTHETIC: 60,
    SourceSystem.WRITEOFF_SYNTHETIC: 60,
}


def _canonical_key(val: Any) -> str:
    """Produce deterministic hashable key for scalar or structured candidate values."""
    if isinstance(val, (dict, list)):
        return json.dumps(val, sort_keys=True)
    return str(val)


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
    """Applies versioned deterministic resolution policies to candidate values."""

    def resolve_field(
        self, field_name: str, candidates: list[CandidateValue]
    ) -> FieldResolutionResult:
        """Resolve a single field from candidate values with authority-based tie breaking."""
        if not candidates:
            msg = f"Cannot resolve field '{field_name}' with zero candidate values"
            raise ValueError(msg)

        # Group candidates by canonical key representation
        by_value: dict[str, tuple[Any, list[CandidateValue]]] = {}
        for c in candidates:
            k = _canonical_key(c.value)
            if k not in by_value:
                by_value[k] = (c.value, [c])
            else:
                by_value[k][1].append(c)

        # Single distinct candidate value -> No conflict
        if len(by_value) == 1:
            val, val_cands = next(iter(by_value.values()))
            sorted_provs = sorted(
                [c.provenance for c in val_cands],
                key=lambda p: (p.source_system.value, p.observation_id),
            )
            return FieldResolutionResult(
                field_name=field_name,
                resolved_value=val,
                supporting_provenance=sorted_provs,
                conflict=None,
            )

        # Multiple distinct values -> Conflict detected
        value_authorities: list[tuple[int, Any, list[CandidateValue]]] = []
        for _k, (val, val_cands) in by_value.items():
            max_auth = max(SOURCE_AUTHORITIES.get(c.provenance.source_system, 0) for c in val_cands)
            value_authorities.append((max_auth, val, val_cands))

        # Sort descending by authority
        value_authorities.sort(key=lambda item: item[0], reverse=True)
        top_auth = value_authorities[0][0]
        top_tier = [item for item in value_authorities if item[0] == top_auth]

        all_conflicting_candidates = sorted(
            candidates,
            key=lambda c: (
                c.provenance.source_system.value,
                c.provenance.observation_id,
            ),
        )

        # Tie at highest authority -> UNRESOLVED conflict, field omitted
        if len(top_tier) > 1:
            conflict = FieldConflict(
                field_name=field_name,
                conflicting_candidates=all_conflicting_candidates,
                state=ConflictState.UNRESOLVED,
                winning_value=None,
                rule_version=RESOLUTION_RULE_VERSION,
                rationale=(
                    f"Equal authority ({top_auth}) disagreement between "
                    f"{len(top_tier)} distinct values; unresolved per ADR 0003/ADR 0005"
                ),
            )
            return FieldResolutionResult(
                field_name=field_name,
                resolved_value=None,
                supporting_provenance=[],
                conflict=conflict,
            )

        # Single highest authority wins -> RESOLVED conflict
        winning_auth, winning_val, winning_cands = top_tier[0]
        winning_provs = sorted(
            [c.provenance for c in winning_cands],
            key=lambda p: (p.source_system.value, p.observation_id),
        )
        losing_auth = value_authorities[1][0]

        conflict = FieldConflict(
            field_name=field_name,
            conflicting_candidates=all_conflicting_candidates,
            state=ConflictState.RESOLVED,
            winning_value=winning_val,
            rule_version=RESOLUTION_RULE_VERSION,
            rationale=(
                f"Higher authority: winning authority {winning_auth} "
                f"exceeds competing authority {losing_auth}"
            ),
        )
        return FieldResolutionResult(
            field_name=field_name,
            resolved_value=winning_val,
            supporting_provenance=winning_provs,
            conflict=conflict,
        )
