"""Tests for ReconciliationEngine orchestrator (e02s04 task t02)."""

from datetime import UTC, date, datetime

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    PPSRInterestStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.reconciliation.engine import ReconciliationEngine


async def test_reconcile_greenfield_vehicle() -> None:
    """Verify reconciling first observations for a VIN creates revision 1."""
    vin = "1HGCR2F85HA000000"
    obs_nhtsa = SourceObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
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
        retrieved_at=datetime.now(UTC),
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
    revision = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa), (obs_dealer, norm_dealer)],
        previous_revision=None,
    )

    assert revision is not None
    assert revision.vin == vin
    assert revision.revision_number == 1
    assert revision.canonical_fields["make"] == "HONDA"
    assert revision.canonical_fields["asking_price_cents"] == 2100000
    assert revision.field_provenance["make"].source_system == SourceSystem.NHTSA_VPIC
    assert revision.field_provenance["asking_price_cents"].source_system == SourceSystem.DEALER_FEED


async def test_reconcile_idempotent_reprocessing_creates_no_new_revision() -> None:
    """Verify identical evidence returns existing revision without incrementing sequence."""
    vin = "1HGCR2F85HA000000"
    obs_nhtsa = SourceObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
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
    rev1 = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa)],
        previous_revision=None,
    )
    assert rev1 is not None

    rev2 = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa)],
        previous_revision=rev1,
    )
    # Should return existing rev1 unchanged (no new revision created)
    assert rev2 is not None
    assert rev2.revision_id == rev1.revision_id
    assert rev2.revision_number == 1


async def test_reconcile_with_material_change_increments_revision_number() -> None:
    """Verify new conflicting or material evidence creates revision 2."""
    vin = "1HGCR2F85HA000000"
    obs_nhtsa = SourceObservation(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="1",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
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
    rev1 = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa)],
        previous_revision=None,
    )
    assert rev1 is not None

    # Now add PPSR finance lien evidence
    obs_ppsr = SourceObservation(
        observation_id="obs_ppsr_1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        ingestion_run_id="run_2",
        source_record_id="PPSR_10",
        raw_payload="{}",
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    staged_ppsr = PPSRInterestStaged(
        ppsr_id="PPSR_10",
        vin=vin,
        secured_party="BNZ",
        collateral_type="Vehicle",
        registration_date=date(2023, 6, 1),
        synthetic=True,
    )
    norm_ppsr = NormalizedObservation(
        observation_id="obs_ppsr_1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        staged_data=staged_ppsr,
    )

    rev2 = await engine.reconcile(
        vin=vin,
        eligible_pairs=[(obs_nhtsa, norm_nhtsa), (obs_ppsr, norm_ppsr)],
        previous_revision=rev1,
    )
    assert rev2 is not None
    assert rev2.revision_number == 2
    assert "ppsr_interests" in rev2.canonical_fields
