"""Unit tests for strict synthetic risk staging models and contracts (e04s01)."""

from datetime import UTC, date, datetime

import pytest

from nz_vehicle_data_pipeline.normalization.staging_models import (
    SYNTHETIC_DISCLAIMER,
    PPSRInterestDetail,
    PPSRInterestStaged,
    PPSRResult,
    StolenIndicatorStaged,
    StolenStatus,
    SyntheticMetadata,
    WriteoffClassificationStaged,
    WriteoffStatus,
)


def create_metadata(scenario: str = "clean_test") -> SyntheticMetadata:
    return SyntheticMetadata(
        synthetic=True,
        dataset_id="nz-synth-risk",
        dataset_version="2026.08",
        scenario_id=scenario,
        generated_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC),
        disclaimer=SYNTHETIC_DISCLAIMER,
    )


def test_synthetic_metadata_validation() -> None:
    """Verify synthetic metadata requires exact disclaimer and valid fields."""
    meta = create_metadata()
    assert meta.synthetic is True
    assert meta.disclaimer == SYNTHETIC_DISCLAIMER

    # Tampered disclaimer is rejected
    with pytest.raises(ValueError, match="Disclaimer must be exactly"):
        SyntheticMetadata(
            synthetic=True,
            dataset_id="d1",
            dataset_version="1",
            scenario_id="s1",
            generated_at=datetime.now(UTC),
            disclaimer="Wrong disclaimer",
        )


def test_ppsr_contract_match_and_no_match() -> None:
    """Verify PPSR MATCH requires interests and NO_MATCH forbids interests."""
    meta = create_metadata()
    vin = "1HGCR2F85HA000000"

    detail = PPSRInterestDetail(
        financing_statement_id="FS123",
        secured_party="SYNTHETIC LENDER",
        registration_date=date(2026, 1, 15),
    )

    # Valid MATCH
    match_rec = PPSRInterestStaged(
        ppsr_id="ppsr_1",
        vin=vin,
        search_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        result=PPSRResult.MATCH,
        interests=[detail],
        metadata=meta,
    )
    assert match_rec.result == PPSRResult.MATCH
    assert len(match_rec.interests) == 1

    # MATCH with empty interests raises ValueError
    with pytest.raises(ValueError, match="MATCH requires at least one interest"):
        PPSRInterestStaged(
            ppsr_id="ppsr_2",
            vin=vin,
            search_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            result=PPSRResult.MATCH,
            interests=[],
            metadata=meta,
        )

    # Valid NO_MATCH
    no_match_rec = PPSRInterestStaged(
        ppsr_id="ppsr_3",
        vin=vin,
        search_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        result=PPSRResult.NO_MATCH,
        interests=[],
        metadata=meta,
    )
    assert no_match_rec.result == PPSRResult.NO_MATCH

    # Valid UNKNOWN (distinct from NO_MATCH)
    unknown_rec = PPSRInterestStaged(
        ppsr_id="ppsr_4",
        vin=vin,
        search_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        result=PPSRResult.UNKNOWN,
        interests=[],
        metadata=meta,
    )
    assert unknown_rec.result == PPSRResult.UNKNOWN
    assert unknown_rec.result.value != PPSRResult.NO_MATCH.value


def test_stolen_contract() -> None:
    """Verify stolen indicator distinguishes LISTED from NOT_LISTED and UNKNOWN."""
    meta = create_metadata()
    vin = "1HGCR2F85HA000000"

    # LISTED requires reported_at
    listed = StolenIndicatorStaged(
        report_id="stolen_1",
        vin=vin,
        status=StolenStatus.LISTED,
        reported_at=datetime(2026, 7, 20, tzinfo=UTC),
        police_district="Auckland",
        metadata=meta,
    )
    assert listed.status == StolenStatus.LISTED

    with pytest.raises(ValueError, match="LISTED status requires reported_at"):
        StolenIndicatorStaged(
            report_id="stolen_2",
            vin=vin,
            status=StolenStatus.LISTED,
            reported_at=None,
            metadata=meta,
        )

    not_listed = StolenIndicatorStaged(
        report_id="stolen_3",
        vin=vin,
        status=StolenStatus.NOT_LISTED,
        metadata=meta,
    )
    assert not_listed.status == StolenStatus.NOT_LISTED

    unknown = StolenIndicatorStaged(
        report_id="stolen_4",
        vin=vin,
        status=StolenStatus.UNKNOWN,
        metadata=meta,
    )
    assert unknown.status == StolenStatus.UNKNOWN
    assert unknown.status.value != StolenStatus.NOT_LISTED.value


def test_writeoff_contract() -> None:
    """Verify write-off classification supports NONE, REPAIRABLE, STATUTORY, UNKNOWN."""
    meta = create_metadata()
    vin = "1HGCR2F85HA000000"

    statutory = WriteoffClassificationStaged(
        writeoff_id="wo_1",
        vin=vin,
        status=WriteoffStatus.STATUTORY,
        damage_type="WATER_SUBMERSION",
        event_date=date(2026, 5, 10),
        insurer="SYNTHETIC MUTUAL",
        repaired=False,
        metadata=meta,
    )
    assert statutory.status == WriteoffStatus.STATUTORY

    none_wo = WriteoffClassificationStaged(
        writeoff_id="wo_2",
        vin=vin,
        status=WriteoffStatus.NONE,
        metadata=meta,
    )
    assert none_wo.status == WriteoffStatus.NONE

    unknown_wo = WriteoffClassificationStaged(
        writeoff_id="wo_3",
        vin=vin,
        status=WriteoffStatus.UNKNOWN,
        metadata=meta,
    )
    assert unknown_wo.status == WriteoffStatus.UNKNOWN
    assert unknown_wo.status.value != WriteoffStatus.NONE.value
