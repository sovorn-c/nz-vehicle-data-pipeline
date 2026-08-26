"""Tests for ConfidenceEngine mathematical calculations under ADR 0003 (confidence-v1)."""

from datetime import UTC, datetime, timedelta

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceBand,
    ConfidenceEngine,
)
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictState,
    FieldConflict,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)


def test_confidence_calculation_authoritative_single_fresh_source() -> None:
    """Verify single fresh NHTSA observation:
    Authority: 100 * 0.40 = 40
    Agreement:  70 * 0.30 = 21
    Freshness: 100 * 0.20 = 20 (age <= 365 days)
    Validation: 100 * 0.10 = 10
    Total = 40 + 21 + 20 + 10 = 91 -> HIGH
    """
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    retrieved = as_of - timedelta(days=30)
    link = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=retrieved,
    )
    c = CandidateValue(field_name="make", value="HONDA", provenance=link)

    engine = ConfidenceEngine()
    assessment = engine.assess(
        resolved_fields={"make": "HONDA"},
        field_provenance={"make": [link]},
        conflicts=[],
        field_candidates={"make": [c]},
        as_of=as_of,
    )

    assert assessment.score == 91
    assert assessment.band == ConfidenceBand.HIGH
    assert assessment.rule_version == "confidence-v1"
    assert assessment.field_scores["make"] == 91
    comp = assessment.field_components["make"]
    assert comp["authority"] == 100
    assert comp["agreement"] == 70
    assert comp["freshness"] == 100
    assert comp["validation"] == 100


def test_confidence_calculation_multi_source_agreement() -> None:
    """Verify multiple agreeing sources:
    Authority: 100 * 0.40 = 40
    Agreement: 100 * 0.30 = 30 (multiple sources agree)
    Freshness: 100 * 0.20 = 20
    Validation: 100 * 0.10 = 10
    Total = 40 + 30 + 20 + 10 = 100 -> HIGH
    """
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link1 = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    link2 = ProvenanceLink(
        observation_id="obs_2",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )
    c1 = CandidateValue(field_name="make", value="HONDA", provenance=link1)
    c2 = CandidateValue(field_name="make", value="HONDA", provenance=link2)

    engine = ConfidenceEngine()
    assessment = engine.assess(
        resolved_fields={"make": "HONDA"},
        field_provenance={"make": [link1, link2]},
        conflicts=[],
        field_candidates={"make": [c1, c2]},
        as_of=as_of,
    )

    assert assessment.score == 100
    assert assessment.band == ConfidenceBand.HIGH
    assert assessment.field_components["make"]["agreement"] == 100


def test_confidence_calculation_resolved_disagreement() -> None:
    """Verify resolved conflict:
    Agreement: 50 * 0.30 = 15 (resolved conflict)
    Authority: 100 * 0.40 = 40
    Freshness: 100 * 0.20 = 20
    Validation: 100 * 0.10 = 10
    Total = 40 + 15 + 20 + 10 = 85 -> HIGH
    """
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link_nhtsa = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    link_dealer = ProvenanceLink(
        observation_id="obs_2",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )
    c1 = CandidateValue(field_name="year", value=2017, provenance=link_nhtsa)
    c2 = CandidateValue(field_name="year", value=2018, provenance=link_dealer)

    conflict = FieldConflict(
        field_name="year",
        conflicting_candidates=[c1, c2],
        state=ConflictState.RESOLVED,
        winning_value=2017,
        rule_version="resolution-v1",
        rationale="NHTSA wins",
    )

    engine = ConfidenceEngine()
    assessment = engine.assess(
        resolved_fields={"year": 2017},
        field_provenance={"year": [link_nhtsa]},
        conflicts=[conflict],
        field_candidates={"year": [c1, c2]},
        as_of=as_of,
    )

    assert assessment.score == 85
    assert assessment.field_components["year"]["agreement"] == 50


def test_confidence_calculation_unresolved_disagreement_scores_zero() -> None:
    """Verify unresolved field conflict yields score 0."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link_a = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="1",
        retrieved_at=as_of,
        synthetic=True,
    )
    link_b = ProvenanceLink(
        observation_id="obs_2",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )
    c1 = CandidateValue(field_name="year", value=2017, provenance=link_a)
    c2 = CandidateValue(field_name="year", value=2018, provenance=link_b)

    conflict = FieldConflict(
        field_name="year",
        conflicting_candidates=[c1, c2],
        state=ConflictState.UNRESOLVED,
        winning_value=None,
        rule_version="resolution-v1",
        rationale="Tie",
    )

    engine = ConfidenceEngine()
    assessment = engine.assess(
        resolved_fields={},
        field_provenance={},
        conflicts=[conflict],
        field_candidates={"year": [c1, c2]},
        as_of=as_of,
    )

    assert assessment.score == 0
    assert assessment.band == ConfidenceBand.LOW
    assert assessment.field_scores.get("year") == 0


def test_confidence_freshness_decay() -> None:
    """Verify freshness decays to 70 for 366-730 days and 40 for >730 days."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    retrieved_medium = as_of - timedelta(days=400)
    link_medium = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=retrieved_medium,
    )
    c_medium = CandidateValue(field_name="make", value="HONDA", provenance=link_medium)

    engine = ConfidenceEngine()
    assessment_medium = engine.assess(
        resolved_fields={"make": "HONDA"},
        field_provenance={"make": [link_medium]},
        conflicts=[],
        field_candidates={"make": [c_medium]},
        as_of=as_of,
    )
    # Auth 100*0.4=40, Agree 70*0.3=21, Fresh 70*0.2=14, Valid 100*0.1=10 -> 85
    assert assessment_medium.field_components["make"]["freshness"] == 70
    assert assessment_medium.score == 85

    retrieved_old = as_of - timedelta(days=800)
    link_old = ProvenanceLink(
        observation_id="obs_2",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="2",
        retrieved_at=retrieved_old,
    )
    c_old = CandidateValue(field_name="make", value="HONDA", provenance=link_old)

    assessment_old = engine.assess(
        resolved_fields={"make": "HONDA"},
        field_provenance={"make": [link_old]},
        conflicts=[],
        field_candidates={"make": [c_old]},
        as_of=as_of,
    )
    # Auth 40, Agree 21, Fresh 40*0.2=8, Valid 10 -> 79 (MEDIUM)
    assert assessment_old.field_components["make"]["freshness"] == 40
    assert assessment_old.score == 79
    assert assessment_old.band == ConfidenceBand.MEDIUM
