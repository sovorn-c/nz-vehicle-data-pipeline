"""Tests for IngestionPipeline orchestrator (e01s04 task t02)."""

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
        "PLATE,MAKE,MODEL,YEAR,VIN11,CHASSIS7,CC_RATING\n"
        "ABC123,TOYOTA,COROLLA,2019,JTDKN3DU5A0,1234567,1798\n"
        "XYZ789,MAZDA,AXELA,2015,JM0BL10F200,7654321,1998\n"
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
