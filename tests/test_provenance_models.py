"""Tests for ProvenanceLink and CandidateValue models (e02s01 task t01)."""

from datetime import UTC, datetime

from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)


def test_provenance_link_creation() -> None:
    """Verify ProvenanceLink correctly tracks source metadata."""
    now = datetime.now(UTC)
    link = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1HGCR2F85HA000000",
        retrieved_at=now,
        synthetic=False,
    )
    assert link.observation_id == "obs_nhtsa_1"
    assert link.source_system == SourceSystem.NHTSA_VPIC
    assert link.synthetic is False


def test_candidate_value_wraps_field_with_provenance() -> None:
    """Verify CandidateValue pairs an extracted attribute with its ProvenanceLink."""
    link = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1HGCR2F85HA000000",
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )
    candidate = CandidateValue(
        field_name="make",
        value="HONDA",
        provenance=link,
    )
    assert candidate.field_name == "make"
    assert candidate.value == "HONDA"
    assert candidate.provenance.source_system == SourceSystem.NHTSA_VPIC
    assert candidate.provenance.observation_id == "obs_nhtsa_1"
