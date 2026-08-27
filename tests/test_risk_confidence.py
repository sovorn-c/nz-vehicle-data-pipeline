"""Unit tests for synthetic risk freshness and confidence scoring (e04s01, ADR 0005)."""

from datetime import UTC, datetime, timedelta

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceBand,
    ConfidenceEngine,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)


def test_risk_freshness_boundaries() -> None:
    """Verify 30-day and 90-day freshness boundaries for risk fields."""
    engine = ConfidenceEngine()
    eval_time = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    def assess_age(days: int) -> int:
        retrieved_at = eval_time - timedelta(days=days)
        link = ProvenanceLink(
            observation_id="obs_1",
            source_system=SourceSystem.PPSR_SYNTHETIC,
            source_record_id="1",
            retrieved_at=retrieved_at,
            synthetic=True,
        )
        c = CandidateValue(field_name="ppsr_result", value="MATCH", provenance=link)
        res = engine.assess(
            resolved_fields={"ppsr_result": "MATCH"},
            field_provenance={"ppsr_result": [link]},
            conflicts=[],
            field_candidates={"ppsr_result": [c]},
            as_of=eval_time,
        )
        return res.field_components["ppsr_result"]["freshness"]

    assert assess_age(0) == 100
    assert assess_age(30) == 100
    assert assess_age(31) == 70
    assert assess_age(90) == 70
    assert assess_age(91) == 40
    assert assess_age(180) == 40


def test_single_current_valid_synthetic_risk_record_reaches_medium() -> None:
    """Verify single current valid synthetic risk record reaches MEDIUM confidence (75)."""
    engine = ConfidenceEngine()
    eval_time = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    retrieved_at = eval_time - timedelta(days=5)  # <= 30d -> freshness 100

    link = ProvenanceLink(
        observation_id="obs_p1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        source_record_id="1",
        retrieved_at=retrieved_at,
        synthetic=True,
    )
    c = CandidateValue(field_name="ppsr_result", value="NO_MATCH", provenance=link)

    res = engine.assess(
        resolved_fields={"ppsr_result": "NO_MATCH"},
        field_provenance={"ppsr_result": [link]},
        conflicts=[],
        field_candidates={"ppsr_result": [c]},
        as_of=eval_time,
    )

    # Authority: 60 (synthetic), Agreement: 70 (single), Freshness: 100 (<=30d), Validation: 100
    # Score: 60*0.4 + 70*0.3 + 100*0.2 + 100*0.1 = 24 + 21 + 20 + 10 = 75
    assert res.score == 75
    assert res.band == ConfidenceBand.MEDIUM
