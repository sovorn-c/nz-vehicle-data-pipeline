"""Tests for ConfidenceAssessment and ConfidenceEngine (e02s03 task t01)."""

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceBand,
    ConfidenceEngine,
)
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictState,
    FieldConflict,
)


def test_confidence_assessment_high_when_full_sources_agree() -> None:
    """Verify high confidence score when multiple sources agree with no conflicts."""
    engine = ConfidenceEngine()
    sources = {
        SourceSystem.NHTSA_VPIC,
        SourceSystem.DEALER_FEED,
        SourceSystem.PPSR_SYNTHETIC,
        SourceSystem.STOLEN_SYNTHETIC,
        SourceSystem.WRITEOFF_SYNTHETIC,
    }
    fields = {
        "make": "HONDA",
        "model": "ACCORD",
        "year": 2017,
        "body_type": "Sedan",
    }
    conflicts: list[FieldConflict] = []

    assessment = engine.assess(fields, conflicts, sources)

    assert assessment.score >= 80
    assert assessment.band == ConfidenceBand.HIGH
    assert assessment.rule_version == "1.0.0"
    assert "authoritative" in assessment.explanation.lower()
    assert assessment.contributions.get("authoritative_vin_decode") == 40


def test_confidence_assessment_penalizes_conflicts() -> None:
    """Verify conflicts reduce confidence score."""
    engine = ConfidenceEngine()
    sources = {SourceSystem.NHTSA_VPIC, SourceSystem.DEALER_FEED}
    fields = {"make": "HONDA", "year": 2017}
    conflict = FieldConflict(
        field_name="year",
        conflicting_candidates=[],
        state=ConflictState.RESOLVED,
        rule_version="1.0.0",
        rationale="NHTSA preferred",
    )

    clean_assessment = engine.assess(fields, [], sources)
    conflict_assessment = engine.assess(fields, [conflict], sources)

    assert conflict_assessment.score < clean_assessment.score
    assert "conflict" in str(conflict_assessment.contributions)


def test_confidence_assessment_low_band() -> None:
    """Verify single non-authoritative source produces LOW confidence band."""
    engine = ConfidenceEngine()
    sources = {SourceSystem.DEALER_FEED}
    fields = {"make": "HONDA"}

    assessment = engine.assess(fields, [], sources)
    assert assessment.score < 50
    assert assessment.band == ConfidenceBand.LOW
