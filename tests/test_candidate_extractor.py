"""Tests for CandidateExtractor under ADR 0002, ADR 0003, and e02 scope."""

from datetime import UTC, date, datetime
import pytest

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
    StolenIndicatorStaged,
    WriteoffClassificationStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor


@pytest.fixture
def extractor() -> CandidateExtractor:
    return CandidateExtractor()


def test_extract_nhtsa_candidates(extractor: CandidateExtractor) -> None:
    """Verify extracting specification candidates from NHTSA staged observation."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    obs = SourceObservation(
        observation_id="obs_nhtsa_01",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1HGCR2F85HA000000",
        raw_payload="{}",
        retrieved_at=as_of,
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
    assert make_c.provenance.retrieved_at == as_of


def test_extract_dealer_candidates(extractor: CandidateExtractor) -> None:
    """Verify extracting dealer market fields and specs."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    obs_dealer = SourceObservation(
        observation_id="obs_dlr_01",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="L_100",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=True,
    )
    staged_dealer = DealerListingStaged(
        dealer_id="DLR_1",
        listing_id="L_100",
        vin="1HGCR2F85HA000000",
        make="HONDA",
        model="ACCORD",
        model_year=2018,
        price_cents=1999000,
        odometer_km=52000,
    )
    norm_dealer = NormalizedObservation(
        observation_id="obs_dlr_01",
        source_system=SourceSystem.DEALER_FEED,
        staged_data=staged_dealer,
    )

    dealer_candidates = extractor.extract(obs_dealer, norm_dealer)
    fields = {c.field_name: c.value for c in dealer_candidates}
    assert fields["make"] == "HONDA"
    assert fields["model"] == "ACCORD"
    assert fields["year"] == 2018
    assert fields["asking_price_cents"] == 1999000
    assert fields["odometer_km"] == 52000


def test_nzta_and_synthetic_risk_yield_zero_candidates_in_e02(
    extractor: CandidateExtractor,
) -> None:
    """Verify NZTA (EVIDENCE_ONLY) and synthetic risk records yield 0 candidates in e02."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    # NZTA Evidence Only
    obs_nzta = SourceObservation(
        observation_id="obs_nzta_01",
        source_system=SourceSystem.NZTA_FLEET,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload="{}",
        retrieved_at=as_of,
    )
    staged_nzta = NZTAFleetStaged(vin11="1HGCR2F85HA", make="HONDA", model="ACCORD")
    norm_nzta = NormalizedObservation(
        observation_id="obs_nzta_01",
        source_system=SourceSystem.NZTA_FLEET,
        staged_data=staged_nzta,
    )
    assert extractor.extract(obs_nzta, norm_nzta) == []

    # Synthetic PPSR (deferred to e04)
    obs_ppsr = SourceObservation(
        observation_id="obs_ppsr_01",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="PPSR_9",
        raw_payload="{}",
        retrieved_at=as_of,
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
    assert extractor.extract(obs_ppsr, norm_ppsr) == []
