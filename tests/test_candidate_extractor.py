"""Tests for CandidateExtractor (e02s01 task t02)."""

from datetime import UTC, date, datetime

import pytest

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    PPSRInterestStaged,
    StolenIndicatorStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor


@pytest.fixture
def extractor() -> CandidateExtractor:
    return CandidateExtractor()


def test_extract_nhtsa_candidates(extractor: CandidateExtractor) -> None:
    """Verify extracting specification candidates from NHTSA staged observation."""
    obs = SourceObservation(
        observation_id="obs_nhtsa_01",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1HGCR2F85HA000000",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )
    staged = NHTSAVPICStaged(
        vin="1HGCR2F85HA000000",
        make="HONDA",
        model="ACCORD",
        model_year=2017,
        body_class="Sedan/Saloon",
        engine_cylinders=4,
        displacement_l=2.4,
    )
    norm = NormalizedObservation(
        observation_id="obs_nhtsa_01",
        source_system=SourceSystem.NHTSA_VPIC,
        staged_data=staged,
    )

    candidates = extractor.extract(obs, norm)
    field_names = {c.field_name for c in candidates}
    assert "make" in field_names
    assert "model" in field_names
    assert "year" in field_names
    assert "body_type" in field_names
    assert "engine_cylinders" in field_names
    assert "displacement_l" in field_names

    make_c = next(c for c in candidates if c.field_name == "make")
    assert make_c.value == "HONDA"
    assert make_c.provenance.source_system == SourceSystem.NHTSA_VPIC
    assert make_c.provenance.observation_id == "obs_nhtsa_01"


def test_extract_dealer_and_ppsr_candidates(extractor: CandidateExtractor) -> None:
    """Verify extracting dealer market fields and synthetic PPSR interest."""
    obs_dealer = SourceObservation(
        observation_id="obs_dlr_01",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="L_100",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    staged_dealer = DealerListingStaged(
        dealer_id="DLR_1",
        listing_id="L_100",
        vin="1HGCR2F85HA000000",
        price_cents=1999000,
        odometer_km=52000,
    )
    norm_dealer = NormalizedObservation(
        observation_id="obs_dlr_01",
        source_system=SourceSystem.DEALER_FEED,
        staged_data=staged_dealer,
    )

    dealer_candidates = extractor.extract(obs_dealer, norm_dealer)
    price_c = next(c for c in dealer_candidates if c.field_name == "asking_price_cents")
    assert price_c.value == 1999000
    assert price_c.provenance.synthetic is True

    # Test PPSR extraction
    obs_ppsr = SourceObservation(
        observation_id="obs_ppsr_01",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="PPSR_9",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    staged_ppsr = PPSRInterestStaged(
        ppsr_id="PPSR_9",
        vin="1HGCR2F85HA000000",
        secured_party="ANZ Bank",
        collateral_type="Vehicle",
        registration_date=date(2023, 5, 1),
        synthetic=True,
    )
    norm_ppsr = NormalizedObservation(
        observation_id="obs_ppsr_01",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        staged_data=staged_ppsr,
    )

    ppsr_candidates = extractor.extract(obs_ppsr, norm_ppsr)
    assert len(ppsr_candidates) == 1
    assert ppsr_candidates[0].field_name == "ppsr_interests"
    assert ppsr_candidates[0].value["ppsr_id"] == "PPSR_9"


def test_extract_stolen_indicator(extractor: CandidateExtractor) -> None:
    """Verify extracting stolen status candidate."""
    obs_stolen = SourceObservation(
        observation_id="obs_stl_01",
        source_system=SourceSystem.STOLEN_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="STL_99",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    staged_stolen = StolenIndicatorStaged(
        report_id="STL_99",
        vin="1HGCR2F85HA000000",
        stolen_flag=True,
        report_date=date(2024, 2, 10),
        police_district="Wellington",
        synthetic=True,
    )
    norm_stolen = NormalizedObservation(
        observation_id="obs_stl_01",
        source_system=SourceSystem.STOLEN_SYNTHETIC,
        staged_data=staged_stolen,
    )

    stolen_candidates = extractor.extract(obs_stolen, norm_stolen)
    status_c = next(c for c in stolen_candidates if c.field_name == "stolen_status")
    assert status_c.value == "LISTED"
