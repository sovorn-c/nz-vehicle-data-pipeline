"""Tests for ReconciliationEngine orchestrator under ADR 0003 and ADR 0004."""

from datetime import UTC, datetime
from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.reconciliation.engine import ReconciliationEngine


async def test_reconcile_emits_pure_deterministic_result() -> None:
    """Verify ReconciliationEngine emits ReconciliationResult with no DB publication metadata."""
    vin = "1HGCR2F85HA000000"
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    obs_nhtsa = SourceObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=False,
    )
    staged_nhtsa = NHTSAVPICStaged(
        vin=vin,
        make="HONDA",
        model="ACCORD",
        model_year=2017,
        body_class="Sedan",
    )
    norm_nhtsa = NormalizedObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        staged_data=staged_nhtsa,
    )

    obs_dealer = SourceObservation(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="10",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=True,
    )
    staged_dealer = DealerListingStaged(
        dealer_id="D_1",
        listing_id="L_1",
        vin=vin,
        price_cents=2100000,
        odometer_km=48000,
    )
    norm_dealer = NormalizedObservation(
        observation_id="obs_dlr_1",
        source_system=SourceSystem.DEALER_FEED,
        staged_data=staged_dealer,
    )

    engine = ReconciliationEngine()
    result = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa), (obs_dealer, norm_dealer)],
        as_of=as_of,
    )

    assert result is not None
    assert result.vin == vin
    assert result.as_of == as_of
    assert result.canonical_fields["make"] == "HONDA"
    assert result.canonical_fields["asking_price_cents"] == 2100000
    assert result.field_provenance["make"][0].source_system == SourceSystem.NHTSA_VPIC
    assert result.confidence.score >= 80

    # Ensure no DB publication metadata is present
    assert not hasattr(result, "revision_number")
    assert not hasattr(result, "revision_id")
    assert not hasattr(result, "published_at")


async def test_reconcile_determinism_identical_runs_match_material_hash() -> None:
    """Verify running reconciliation multiple times on identical evidence produces identical material hash."""
    vin = "1HGCR2F85HA000000"
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    obs_nhtsa = SourceObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload="{}",
        retrieved_at=as_of,
        synthetic=False,
    )
    staged_nhtsa = NHTSAVPICStaged(
        vin=vin,
        make="HONDA",
        model="ACCORD",
        model_year=2017,
    )
    norm_nhtsa = NormalizedObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        staged_data=staged_nhtsa,
    )

    engine = ReconciliationEngine()
    res1 = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa)],
        as_of=as_of,
    )
    res2 = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa)],
        as_of=as_of,
    )
    assert res1 is not None and res2 is not None
    assert res1.material_hash() == res2.material_hash()
