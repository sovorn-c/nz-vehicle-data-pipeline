"""Tests for deterministic FieldResolver, authority weights, and tie resolution (ADR 0003)."""

from datetime import UTC, datetime
import itertools
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.conflicts import ConflictState
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import FieldResolver


def test_resolve_spec_field_conflict_favors_higher_authority_nhtsa() -> None:
    """Verify NHTSA vPIC (authority 100) wins over Dealer Feed (authority 60) for year."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link_nhtsa = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    link_dealer = ProvenanceLink(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )

    c_nhtsa = CandidateValue(field_name="year", value=2017, provenance=link_nhtsa)
    c_dealer = CandidateValue(field_name="year", value=2018, provenance=link_dealer)

    resolver = FieldResolver()
    result = resolver.resolve_field("year", [c_nhtsa, c_dealer])

    assert result.resolved_value == 2017
    assert len(result.supporting_provenance) == 1
    assert result.supporting_provenance[0].source_system == SourceSystem.NHTSA_VPIC
    assert result.conflict is not None
    assert result.conflict.state == ConflictState.RESOLVED
    assert result.conflict.winning_value == 2017
    assert "Higher authority" in result.conflict.rationale


def test_equal_authority_disagreement_is_unresolved_across_all_permutations() -> None:
    """Verify tied authority candidates (e.g. 60 vs 60) produce UNRESOLVED conflict and None value."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link_dealer_a = ProvenanceLink(
        observation_id="obs_dlr_a",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="A",
        retrieved_at=as_of,
        synthetic=True,
    )
    link_dealer_b = ProvenanceLink(
        observation_id="obs_dlr_b",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="B",
        retrieved_at=as_of,
        synthetic=True,
    )

    c_dealer_a = CandidateValue(field_name="year", value=2017, provenance=link_dealer_a)
    c_dealer_b = CandidateValue(field_name="year", value=2018, provenance=link_dealer_b)

    resolver = FieldResolver()

    # Test both permutations [A, B] and [B, A] - order must never resolve the conflict
    for perm in itertools.permutations([c_dealer_a, c_dealer_b]):
        result = resolver.resolve_field("year", list(perm))
        assert result.resolved_value is None
        assert result.supporting_provenance == []
        assert result.conflict is not None
        assert result.conflict.state == ConflictState.UNRESOLVED
        assert result.conflict.winning_value is None
        assert "Equal authority" in result.conflict.rationale


def test_same_value_candidates_aggregate_all_supporting_provenance() -> None:
    """Verify agreeing candidate observations preserve all supporting ProvenanceLinks."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link1 = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    link2 = ProvenanceLink(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )

    c1 = CandidateValue(field_name="make", value="HONDA", provenance=link1)
    c2 = CandidateValue(field_name="make", value="HONDA", provenance=link2)

    resolver = FieldResolver()
    result = resolver.resolve_field("make", [c1, c2])

    assert result.resolved_value == "HONDA"
    assert len(result.supporting_provenance) == 2
    prov_ids = {p.observation_id for p in result.supporting_provenance}
    assert prov_ids == {"obs_nhtsa_1", "obs_dlr_1"}
    assert result.conflict is None
