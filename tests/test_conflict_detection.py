"""Tests for FieldConflict models and ConflictDetector (e02s02 task t01)."""

from datetime import UTC, datetime

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictDetector,
    ConflictState,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)


def test_conflict_detected_when_candidates_differ() -> None:
    """Verify conflict is detected when distinct candidate values are proposed for same field."""
    link_nhtsa = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )
    link_dealer = ProvenanceLink(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )

    c_nhtsa = CandidateValue(field_name="year", value=2017, provenance=link_nhtsa)
    c_dealer = CandidateValue(field_name="year", value=2018, provenance=link_dealer)

    detector = ConflictDetector()
    conflicts = detector.detect_conflicts([c_nhtsa, c_dealer])

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.field_name == "year"
    assert conflict.state == ConflictState.DETECTED
    assert len(conflict.conflicting_candidates) == 2


def test_no_conflict_when_candidates_agree() -> None:
    """Verify agreeing candidate values from different sources produce no conflict."""
    link1 = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
    )
    link2 = ProvenanceLink(
        observation_id="obs_2",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )

    c1 = CandidateValue(field_name="make", value="HONDA", provenance=link1)
    c2 = CandidateValue(field_name="make", value="HONDA", provenance=link2)

    detector = ConflictDetector()
    conflicts = detector.detect_conflicts([c1, c2])
    assert len(conflicts) == 0
