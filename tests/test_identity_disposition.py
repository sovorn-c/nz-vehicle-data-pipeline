"""Tests for IdentityDisposition triage per ADR 0002 (e01s03 task t02)."""

from datetime import UTC, datetime

from nz_vehicle_data_pipeline.identity.triage import (
    IdentityDisposition,
    IdentityTriage,
)
from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    SYNTHETIC_DISCLAIMER,
    DealerListingStaged,
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
    PPSRResult,
    SyntheticMetadata,
)
from nz_vehicle_data_pipeline.observation.models import SourceSystem


def test_triage_nhtsa_with_valid_17_char_vin_is_eligible() -> None:
    """Verify staged record with valid 17-char VIN is triaged as ELIGIBLE."""
    staged = NHTSAVPICStaged(
        vin="1HGCR2F85HA000000",
        make="HONDA",
        model="ACCORD",
        model_year=2017,
    )
    norm_obs = NormalizedObservation(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        staged_data=staged,
        normalized_at=datetime.now(UTC),
    )

    triage = IdentityTriage()
    result = triage.evaluate(norm_obs)

    assert result.disposition == IdentityDisposition.ELIGIBLE
    assert result.canonical_vin == "1HGCR2F85HA000000"
    assert result.is_eligible is True


def test_triage_nzta_fleet_with_11_char_vin_is_evidence_only() -> None:
    """Verify NZTA record with 11-char truncated VIN is triaged as EVIDENCE_ONLY per ADR 0002."""
    staged = NZTAFleetStaged(
        plate="ABC123",
        make="TOYOTA",
        model="COROLLA",
        year=2019,
        vin11="JTDKN3DU5A0",  # Truncated 11 chars
        chassis7="1234567",
        engine_number="2ZR-999",
    )
    norm_obs = NormalizedObservation(
        observation_id="obs_nzta_1",
        source_system=SourceSystem.NZTA_MVR,
        staged_data=staged,
        normalized_at=datetime.now(UTC),
    )

    triage = IdentityTriage()
    result = triage.evaluate(norm_obs)

    assert result.disposition == IdentityDisposition.EVIDENCE_ONLY
    assert result.canonical_vin is None
    assert result.is_eligible is False
    assert "Truncated or missing 17-char VIN" in result.reason


def test_triage_ppsr_with_invalid_checksum_is_evidence_only() -> None:
    """Verify synthetic record with corrupted check digit is triaged as EVIDENCE_ONLY."""
    meta = SyntheticMetadata(
        synthetic=True,
        dataset_id="ds1",
        dataset_version="1",
        scenario_id="scen1",
        generated_at=datetime(2026, 8, 1, tzinfo=UTC),
        disclaimer=SYNTHETIC_DISCLAIMER,
    )
    staged = PPSRInterestStaged(
        ppsr_id="PPSR_001",
        vin="1HGCR2F87HA000000",  # Corrupted check digit 7 (expected 5)
        search_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        result=PPSRResult.NO_MATCH,
        interests=[],
        metadata=meta,
    )
    norm_obs = NormalizedObservation(
        observation_id="obs_ppsr_1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        staged_data=staged,
        normalized_at=datetime.now(UTC),
    )

    triage = IdentityTriage()
    result = triage.evaluate(norm_obs)

    assert result.disposition == IdentityDisposition.EVIDENCE_ONLY
    assert result.canonical_vin is None
    assert "Invalid check digit" in result.reason


def test_triage_dealer_listing_with_valid_vin_is_eligible() -> None:
    """Verify dealer feed listing with valid VIN is ELIGIBLE."""
    staged = DealerListingStaged(
        dealer_id="D_1",
        listing_id="L_1",
        vin="1FA6P8CF8H5000000",
        price_cents=2500000,
        odometer_km=45000,
    )
    norm_obs = NormalizedObservation(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        staged_data=staged,
        normalized_at=datetime.now(UTC),
    )

    triage = IdentityTriage()
    result = triage.evaluate(norm_obs)

    assert result.disposition == IdentityDisposition.ELIGIBLE
    assert result.canonical_vin == "1FA6P8CF8H5000000"
