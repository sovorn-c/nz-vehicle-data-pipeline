"""Tests for deterministic FieldResolver and resolution policies (e02s02 task t02)."""

from datetime import UTC, datetime
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.conflicts import ConflictState
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import FieldResolver


def test_resolve_spec_field_conflict_favors_nhtsa() -> None:
    """Verify manufacturer NHTSA decode wins over dealer listing for vehicle year."""
    link_nhtsa = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
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

    resolver = FieldResolver()
    result = resolver.resolve_field("year", [c_nhtsa, c_dealer])

    assert result.resolved_value == 2017
    assert result.winning_provenance.source_system == SourceSystem.NHTSA_VPIC
    assert result.conflict is not None
    assert result.conflict.state == ConflictState.RESOLVED
    assert result.conflict.winning_candidate == c_nhtsa
    assert "NHTSA manufacturer VIN decode is authoritative" in result.conflict.rationale


def test_resolve_single_candidate_cleanly() -> None:
    """Verify single candidate resolves without conflict."""
    link = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
    )
    c = CandidateValue(field_name="make", value="HONDA", provenance=link)

    resolver = FieldResolver()
    result = resolver.resolve_field("make", [c])

    assert result.resolved_value == "HONDA"
    assert result.winning_provenance == link
    assert result.conflict is None


def test_resolve_dealer_market_price() -> None:
    """Verify dealer feed is authoritative for asking price."""
    link = ProvenanceLink(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    c = CandidateValue(field_name="asking_price_cents", value=2500000, provenance=link)

    resolver = FieldResolver()
    result = resolver.resolve_field("asking_price_cents", [c])
    assert result.resolved_value == 2500000
    assert result.winning_provenance.source_system == SourceSystem.DEALER_FEED
