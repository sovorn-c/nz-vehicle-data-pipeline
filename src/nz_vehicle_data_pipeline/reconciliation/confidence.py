"""Confidence assessment engine deriving reproducible 0-100 evidence ratings (ADR 0003)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictState,
    FieldConflict,
)

CONFIDENCE_RULE_VERSION = "1.0.0"


class ConfidenceBand(StrEnum):
    """Calibrated tier of confidence score."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfidenceAssessment(BaseModel):
    """Reproducible assessment of canonical evidence strength."""

    model_config = ConfigDict(frozen=True)

    score: int = Field(description="Integer confidence score from 0 through 100")
    band: ConfidenceBand = Field(description="Confidence band rating")
    contributions: dict[str, int] = Field(description="Component score contributions and penalties")
    rule_version: str = Field(
        default=CONFIDENCE_RULE_VERSION,
        description="Version of confidence calculation rule",
    )
    explanation: str = Field(description="Human-readable explanation of score factors")
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp assessment was computed",
    )


class ConfidenceEngine:
    """Computes reproducible confidence assessments based on evidence strength."""

    def assess(
        self,
        fields: dict[str, Any],
        conflicts: list[FieldConflict],
        sources_seen: set[SourceSystem],
    ) -> ConfidenceAssessment:
        """Derive 0-100 score, band, and explanation from observed evidence."""
        contributions: dict[str, int] = {}

        if SourceSystem.NHTSA_VPIC in sources_seen:
            contributions["authoritative_vin_decode"] = 40

        if len(sources_seen) >= 2:
            contributions["multi_source_agreement"] = 20

        if SourceSystem.PPSR_SYNTHETIC in sources_seen:
            contributions["finance_check_verified"] = 15

        if SourceSystem.STOLEN_SYNTHETIC in sources_seen:
            contributions["stolen_check_verified"] = 10

        if SourceSystem.WRITEOFF_SYNTHETIC in sources_seen:
            contributions["writeoff_check_verified"] = 10

        if {"make", "model", "year"}.issubset(fields.keys()):
            contributions["core_spec_complete"] = 5

        for conflict in conflicts:
            if conflict.state == ConflictState.RESOLVED:
                key = f"resolved_conflict_penalty_{conflict.field_name}"
                contributions[key] = -15
            else:
                key = f"unresolved_conflict_penalty_{conflict.field_name}"
                contributions[key] = -30

        raw_score = sum(contributions.values())
        score = max(0, min(100, raw_score))

        if score >= 80:
            band = ConfidenceBand.HIGH
        elif score >= 50:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        explanation = self._build_explanation(score, band, contributions)

        return ConfidenceAssessment(
            score=score,
            band=band,
            contributions=contributions,
            rule_version=CONFIDENCE_RULE_VERSION,
            explanation=explanation,
        )

    def _build_explanation(
        self, score: int, band: ConfidenceBand, contributions: dict[str, int]
    ) -> str:
        """Build human-readable summary of score factors."""
        positives = [f"{k} (+{v})" for k, v in contributions.items() if v > 0]
        penalties = [f"{k} ({v})" for k, v in contributions.items() if v < 0]

        summary_parts = [f"Confidence rating is {score}/100 ({band.value})."]
        if positives:
            summary_parts.append(f"Positive evidence: {', '.join(positives)}.")
        if penalties:
            summary_parts.append(f"Penalties applied: {', '.join(penalties)}.")

        return " ".join(summary_parts)
