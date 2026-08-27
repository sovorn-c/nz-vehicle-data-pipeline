"""Confidence assessment engine deriving reproducible 0-100 evidence ratings."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictState,
    FieldConflict,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import (
    SOURCE_AUTHORITIES,
)

CONFIDENCE_RULE_VERSION = "confidence-v1"
RISK_FIELDS: set[str] = {"ppsr_result", "stolen_status", "writeoff_status"}


class ConfidenceBand(StrEnum):
    """Calibrated tier of confidence score."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfidenceAssessment(BaseModel):
    """Reproducible assessment of canonical evidence strength under ADR 0003."""

    model_config = ConfigDict(frozen=True)

    score: int = Field(description="Integer confidence score from 0 through 100")
    band: ConfidenceBand = Field(description="Confidence band rating")
    field_scores: dict[str, int] = Field(description="Per-field weighted confidence scores")
    field_components: dict[str, dict[str, int]] = Field(
        description=("Detailed authority, agreement, freshness, validation breakdowns")
    )
    rule_version: str = Field(
        default=CONFIDENCE_RULE_VERSION,
        description="Version of confidence calculation rule",
    )
    explanation: str = Field(description="Human-readable explanation of score factors")


class ConfidenceEngine:
    """Computes reproducible confidence assessments based on ADR 0003/ADR 0005 weights."""

    def assess(
        self,
        resolved_fields: dict[str, Any],
        field_provenance: dict[str, list[ProvenanceLink]],
        conflicts: list[FieldConflict],
        field_candidates: dict[str, list[CandidateValue]],
        as_of: datetime,
    ) -> ConfidenceAssessment:
        """Derive reproducible field and aggregate scores from evidence."""
        all_fields = set(resolved_fields.keys()) | set(field_candidates.keys())
        for c in conflicts:
            all_fields.add(c.field_name)

        field_scores: dict[str, int] = {}
        field_components: dict[str, dict[str, int]] = {}

        for field in sorted(all_fields):
            val = resolved_fields.get(field)
            provs = field_provenance.get(field, [])
            matching_conflict = next((c for c in conflicts if c.field_name == field), None)

            if val is None or not provs:
                # Unresolved field -> score is 0
                field_scores[field] = 0
                field_components[field] = {
                    "authority": 0,
                    "agreement": 0,
                    "freshness": 0,
                    "validation": 0,
                }
                continue

            # Authority: 40%
            auth = max(SOURCE_AUTHORITIES.get(p.source_system, 50) for p in provs)

            # Agreement: 30%
            if matching_conflict is not None:
                agree = 50 if matching_conflict.state == ConflictState.RESOLVED else 0
            else:
                agree = 100 if len(provs) >= 2 else 70

            # Freshness: 20%
            newest_retrieved = max(p.retrieved_at for p in provs)
            age_days = (as_of - newest_retrieved).total_seconds() / 86400.0

            if field in RISK_FIELDS:
                if age_days <= 30:
                    fresh = 100
                elif age_days <= 90:
                    fresh = 70
                else:
                    fresh = 40
            else:
                if age_days <= 365:
                    fresh = 100
                elif age_days <= 730:
                    fresh = 70
                else:
                    fresh = 40

            # Validation: 10%
            valid = 100

            # Weighted sum: 40% auth + 30% agree + 20% fresh + 10% valid
            raw_field_score = (
                Decimal(str(auth)) * Decimal("0.40")
                + Decimal(str(agree)) * Decimal("0.30")
                + Decimal(str(fresh)) * Decimal("0.20")
                + Decimal(str(valid)) * Decimal("0.10")
            )
            field_score = int(raw_field_score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

            field_scores[field] = field_score
            field_components[field] = {
                "authority": auth,
                "agreement": agree,
                "freshness": fresh,
                "validation": valid,
            }

        # Overall confidence is governed by the lowest field score
        overall_score = min(field_scores.values()) if field_scores else 0
        band = self._score_to_band(overall_score)
        explanation = self._build_explanation(overall_score, band, field_scores)

        return ConfidenceAssessment(
            score=overall_score,
            band=band,
            field_scores=field_scores,
            field_components=field_components,
            rule_version=CONFIDENCE_RULE_VERSION,
            explanation=explanation,
        )

    def _score_to_band(self, score: int) -> ConfidenceBand:
        if score >= 80:
            return ConfidenceBand.HIGH
        if score >= 50:
            return ConfidenceBand.MEDIUM
        return ConfidenceBand.LOW

    def _build_explanation(
        self,
        overall_score: int,
        band: ConfidenceBand,
        field_scores: dict[str, int],
    ) -> str:
        if not field_scores:
            return "No fields evaluated."
        lowest_field = min(field_scores.items(), key=lambda x: x[1])
        return (
            f"Overall confidence is {overall_score}/100 ({band.value}), governed by lowest "
            f"field score '{lowest_field[0]}' ({lowest_field[1]}/100)."
        )
