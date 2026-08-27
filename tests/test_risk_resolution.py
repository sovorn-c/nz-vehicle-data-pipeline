"""Unit tests for synthetic risk candidate extraction and resolution rules (e04s01)."""

from datetime import UTC, datetime

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    SYNTHETIC_DISCLAIMER,
    PPSRInterestStaged,
    PPSRResult,
    StolenIndicatorStaged,
    StolenStatus,
    SyntheticMetadata,
    WriteoffClassificationStaged,
    WriteoffStatus,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.reconciliation.conflicts import ConflictState
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import FieldResolver


def get_metadata() -> SyntheticMetadata:
    return SyntheticMetadata(
        synthetic=True,
        dataset_id="test-ds",
        dataset_version="1.0",
        scenario_id="risk-scen",
        generated_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        disclaimer=SYNTHETIC_DISCLAIMER,
    )


def test_candidate_extractor_extracts_risk_candidates() -> None:
    """Verify CandidateExtractor extracts ppsr_result, stolen_status, writeoff_status."""
    extractor = CandidateExtractor()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    meta = get_metadata()

    # 1. PPSR
    ppsr_staged = PPSRInterestStaged(
        ppsr_id="ppsr_1",
        vin="1HGCR2F85HA000000",
        search_timestamp=as_of,
        result=PPSRResult.NO_MATCH,
        interests=[],
        metadata=meta,
    )
    obs_ppsr = SourceObservation(
        observation_id="obs_p1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="ppsr_1",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=True,
    )
    norm_ppsr = NormalizedObservation(
        observation_id="obs_p1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        staged_data=ppsr_staged,
    )
    cands_ppsr = extractor.extract(obs_ppsr, norm_ppsr)
    assert len(cands_ppsr) == 1
    assert cands_ppsr[0].field_name == "ppsr_result"
    assert cands_ppsr[0].value == "NO_MATCH"

    # 2. Stolen
    stolen_staged = StolenIndicatorStaged(
        report_id="stolen_1",
        vin="1HGCR2F85HA000000",
        status=StolenStatus.LISTED,
        reported_at=as_of,
        metadata=meta,
    )
    obs_stolen = SourceObservation(
        observation_id="obs_s1",
        source_system=SourceSystem.STOLEN_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="stolen_1",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=True,
    )
    norm_stolen = NormalizedObservation(
        observation_id="obs_s1",
        source_system=SourceSystem.STOLEN_SYNTHETIC,
        staged_data=stolen_staged,
    )
    cands_stolen = extractor.extract(obs_stolen, norm_stolen)
    assert len(cands_stolen) == 1
    assert cands_stolen[0].field_name == "stolen_status"
    assert cands_stolen[0].value == "LISTED"

    # 3. Writeoff
    wo_staged = WriteoffClassificationStaged(
        writeoff_id="wo_1",
        vin="1HGCR2F85HA000000",
        status=WriteoffStatus.STATUTORY,
        metadata=meta,
    )
    obs_wo = SourceObservation(
        observation_id="obs_w1",
        source_system=SourceSystem.WRITEOFF_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="wo_1",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=True,
    )
    norm_wo = NormalizedObservation(
        observation_id="obs_w1",
        source_system=SourceSystem.WRITEOFF_SYNTHETIC,
        staged_data=wo_staged,
    )
    cands_wo = extractor.extract(obs_wo, norm_wo)
    assert len(cands_wo) == 1
    assert cands_wo[0].field_name == "writeoff_status"
    assert cands_wo[0].value == "STATUTORY"


def test_equal_authority_contradictory_risk_is_unresolved() -> None:
    """Verify two contradictory synthetic risk observations yield UNRESOLVED conflict."""
    resolver = FieldResolver()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    l1 = ProvenanceLink(
        observation_id="obs_p1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        source_record_id="1",
        retrieved_at=as_of,
        synthetic=True,
    )
    l2 = ProvenanceLink(
        observation_id="obs_p2",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        source_record_id="2",
        retrieved_at=as_of,
        synthetic=True,
    )

    c1 = CandidateValue(field_name="ppsr_result", value="MATCH", provenance=l1)
    c2 = CandidateValue(field_name="ppsr_result", value="NO_MATCH", provenance=l2)

    res1 = resolver.resolve_field("ppsr_result", [c1, c2])
    assert res1.resolved_value is None
    assert res1.supporting_provenance == []
    assert res1.conflict is not None
    assert res1.conflict.state == ConflictState.UNRESOLVED

    # Order independence
    res2 = resolver.resolve_field("ppsr_result", [c2, c1])
    assert res2.resolved_value is None
    assert res2.conflict is not None
    assert res2.conflict.state == ConflictState.UNRESOLVED
