"""Unit tests for synthetic risk connectors (e04s01)."""

import json
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector
from nz_vehicle_data_pipeline.connectors.stolen_synthetic import (
    SyntheticStolenConnector,
)
from nz_vehicle_data_pipeline.connectors.writeoff_synthetic import (
    SyntheticWriteoffConnector,
)
from nz_vehicle_data_pipeline.observation.models import SourceSystem


async def test_synthetic_ppsr_connector_preserves_input_without_repair() -> None:
    """Verify connector yields raw record without modifying synthetic flag or payload."""
    raw_item = {
        "ppsr_id": "PPSR001",
        "vin": "1HGCR2F85HA000000",
        "result": "MATCH",
        "synthetic": True,
    }
    connector = SyntheticPPSRConnector(data=[raw_item])
    assert connector.source_system == SourceSystem.PPSR_SYNTHETIC

    records = [r async for r in connector.fetch_all()]
    assert len(records) == 1
    assert records[0].record_id == "PPSR001"
    parsed_payload = json.loads(records[0].payload)
    assert parsed_payload["ppsr_id"] == "PPSR001"


async def test_synthetic_stolen_connector() -> None:
    """Verify SyntheticStolenConnector emits records with STOLEN_SYNTHETIC source."""
    raw_item = {
        "report_id": "STOLEN001",
        "vin": "1HGCR2F85HA000000",
        "status": "LISTED",
        "synthetic": True,
    }
    connector = SyntheticStolenConnector(data=[raw_item])
    assert connector.source_system == SourceSystem.STOLEN_SYNTHETIC

    records = [r async for r in connector.fetch_all()]
    assert len(records) == 1
    assert records[0].record_id == "STOLEN001"


async def test_synthetic_writeoff_connector() -> None:
    """Verify SyntheticWriteoffConnector emits records with WRITEOFF_SYNTHETIC source."""
    raw_item = {
        "writeoff_id": "WO001",
        "vin": "1HGCR2F85HA000000",
        "status": "STATUTORY",
        "synthetic": True,
    }
    connector = SyntheticWriteoffConnector(data=[raw_item])
    assert connector.source_system == SourceSystem.WRITEOFF_SYNTHETIC

    records = [r async for r in connector.fetch_all()]
    assert len(records) == 1
    assert records[0].record_id == "WO001"
