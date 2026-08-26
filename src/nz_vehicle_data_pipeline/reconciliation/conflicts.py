"""Field conflict models and conflict detection logic (ADR 0003)."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.reconciliation.provenance import CandidateValue


class ConflictState(StrEnum):
    """Lifecycle state of a detected field conflict."""

    DETECTED = "DETECTED"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class FieldConflict(BaseModel):
    """Recorded disagreement between credible incompatible candidate values."""

    model_config = ConfigDict(frozen=True)

    field_name: str = Field(description="Target canonical field")
    conflicting_candidates: list[CandidateValue] = Field(
        description="All competing candidate values"
    )
    state: ConflictState = Field(
        default=ConflictState.DETECTED, description="Current conflict resolution state"
    )
    winning_value: Any | None = Field(
        default=None, description="Winning candidate value if resolved"
    )
    rule_version: str = Field(default="", description="Version of resolution rule applied")
    rationale: str = Field(default="", description="Explanation of resolution decision")


class ConflictDetector:
    """Detects disagreements across candidate values for the same canonical field."""

    def detect_conflicts(self, candidates: list[CandidateValue]) -> list[FieldConflict]:
        """Group candidates by field name and detect distinct conflicting values."""
        by_field: dict[str, list[CandidateValue]] = {}
        for candidate in candidates:
            by_field.setdefault(candidate.field_name, []).append(candidate)

        conflicts: list[FieldConflict] = []
        for field_name, field_candidates in by_field.items():
            if len(field_candidates) < 2:
                continue

            first_val = field_candidates[0].value
            has_disagreement = any(c.value != first_val for c in field_candidates[1:])

            if has_disagreement:
                conflicts.append(
                    FieldConflict(
                        field_name=field_name,
                        conflicting_candidates=field_candidates,
                        state=ConflictState.DETECTED,
                    )
                )

        return conflicts
