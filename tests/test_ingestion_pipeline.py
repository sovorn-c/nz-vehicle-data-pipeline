"""Tests for IngestionPipeline orchestrator (e01s04, e04s03)."""

from datetime import UTC, datetime, timedelta

from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.nzta_csv import NZTAFleetCSVConnector
from nz_vehicle_data_pipeline.identity.triage import (
    IdentityDisposition,
    IdentityTriage,
)
from nz_vehicle_data_pipeline.normalization.engine import NormalizationEngine
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.observation.store import InMemoryObservationStore
from nz_vehicle_data_pipeline.pipeline.orchestrator import IngestionPipeline


async def test_pipeline_ingests_nzta_csv_batch() -> None:
    """Verify pipeline processes NZTA CSV, stores observations, and triages as EVIDENCE_ONLY."""
    store = InMemoryObservationStore()
    engine = NormalizationEngine()
    triage = IdentityTriage()
    pipeline = IngestionPipeline(store=store, engine=engine, triage=triage)

    csv_text = (
        "MAKE,MODEL,YEAR,VIN11,CHASSIS7,CC_RATING\n"
        "HONDA,ACCORD,2017,1HGCR2F85HA,1234567,2356\n"
        "MAZDA,AXELA,2015,JM0BL10F200,7654321,1998\n"
    )
    connector = NZTAFleetCSVConnector(csv_content=csv_text)

    batch_result = await pipeline.ingest(connector, run_id="run_nzta_001")

    assert batch_result.run_id == "run_nzta_001"
    assert batch_result.source_system == SourceSystem.NZTA_MVR
    assert batch_result.total_ingested == 2
    assert batch_result.normalized_count == 2
    assert batch_result.rejected_count == 0
    assert batch_result.eligible_count == 0  # Truncated 11-char VINs are EVIDENCE_ONLY
    assert batch_result.evidence_only_count == 2

    # Verify stored in observation repository
    assert await store.count() == 2
    stored = await store.get_by_run_id("run_nzta_001")
    assert len(stored) == 2


async def test_pipeline_ingests_nhtsa_vpic_batch() -> None:
    """Verify pipeline processes NHTSA response and triages valid 17-char VINs as ELIGIBLE."""
    store = InMemoryObservationStore()
    engine = NormalizationEngine()
    triage = IdentityTriage()
    pipeline = IngestionPipeline(store=store, engine=engine, triage=triage)

    api_response = {
        "Results": [
            {
                "VIN": "1HGCR2F85HA000000",
                "Make": "HONDA",
                "Model": "ACCORD",
                "ModelYear": "2017",
            }
        ]
    }
    connector = NHTSAVPICConnector(data=api_response)

    batch_result = await pipeline.ingest(connector, run_id="run_nhtsa_001")

    assert batch_result.total_ingested == 1
    assert batch_result.eligible_count == 1
    assert batch_result.items[0].triage_result is not None
    assert batch_result.items[0].triage_result.disposition == IdentityDisposition.ELIGIBLE
    assert batch_result.items[0].triage_result.canonical_vin == "1HGCR2F85HA000000"


async def test_ingestion_pipeline_replay_derives_from_original_stored_observation() -> None:
    """Verify identical replay reuses original stored observation timestamp and metadata."""
    store = InMemoryObservationStore()
    engine = NormalizationEngine()
    triage = IdentityTriage()
    pipeline = IngestionPipeline(store=store, engine=engine, triage=triage)

    time_1 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC)
    time_2 = time_1 + timedelta(days=5)

    data = [{"VIN": "1HGCR2F85HA000000", "Make": "HONDA", "Model": "ACCORD", "ModelYear": "2017"}]
    connector = NHTSAVPICConnector(data=data)

    # First run at time_1
    res1 = await pipeline.ingest(connector, run_id="run_1", captured_at=time_1)
    assert res1.total_ingested == 1
    assert res1.items[0].observation.retrieved_at == time_1
    assert res1.items[0].observation.ingestion_run_id == "run_1"

    # Second run with same data at time_2
    res2 = await pipeline.ingest(connector, run_id="run_2", captured_at=time_2)
    assert res2.total_ingested == 1
    # Derived from originally stored observation -> retains time_1 and run_1
    assert res2.items[0].observation.retrieved_at == time_1
    assert res2.items[0].observation.ingestion_run_id == "run_1"
