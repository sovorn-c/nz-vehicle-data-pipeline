"""Tests for NormalizationEngine and result models (e01s02 task t02)."""

import json
from datetime import UTC, datetime

import pytest

from nz_vehicle_data_pipeline.normalization.engine import (
    NormalizationEngine,
    NormalizedObservation,
    RejectedObservation,
)
from nz_vehicle_data_pipeline.normalization.staging_models import (
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem


@pytest.fixture
def engine() -> NormalizationEngine:
    return NormalizationEngine()


def test_normalize_valid_nzta_csv_row(engine: NormalizationEngine) -> None:
    """Verify normalizing a valid NZTA CSV row into NormalizedObservation."""
    payload = json.dumps(
        {
            "plate": "XYZ789",
            "make": "MAZDA",
            "model": "AXELA",
            "year": "2015",
            "vin11": "JM0BL10F200",
            "cc_rating": "1998",
        }
    )
    obs = SourceObservation(
        observation_id="obs_nzta_10",
        source_system=SourceSystem.NZTA_MVR,
        ingestion_run_id="run_1",
        source_record_id="row_10",
        raw_payload=payload,
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )

    result = engine.normalize(obs)
    assert isinstance(result, NormalizedObservation)
    assert result.observation_id == "obs_nzta_10"
    assert isinstance(result.staged_data, NZTAFleetStaged)
    assert result.staged_data.plate == "XYZ789"
    assert result.staged_data.make == "MAZDA"


def test_normalize_valid_nhtsa_json(engine: NormalizationEngine) -> None:
    """Verify normalizing NHTSA vPIC payload."""
    payload = json.dumps(
        {
            "VIN": "1HGCR2F83HA000000",
            "Make": "HONDA",
            "Model": "ACCORD",
            "ModelYear": "2017",
        }
    )
    obs = SourceObservation(
        observation_id="obs_nhtsa_10",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="vpic_1",
        raw_payload=payload,
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )

    result = engine.normalize(obs)
    assert isinstance(result, NormalizedObservation)
    assert isinstance(result.staged_data, NHTSAVPICStaged)
    assert result.staged_data.vin == "1HGCR2F83HA000000"


def test_normalize_valid_synthetic_ppsr(engine: NormalizationEngine) -> None:
    """Verify normalizing synthetic PPSR record."""
    payload = json.dumps(
        {
            "ppsr_id": "PPSR_111",
            "vin": "1HGCR2F83HA000000",
            "search_timestamp": "2026-08-01T12:00:00Z",
            "result": "NO_MATCH",
            "interests": [],
            "metadata": {
                "synthetic": True,
                "dataset_id": "synth_ds",
                "dataset_version": "1.0",
                "scenario_id": "clean_no_match",
                "generated_at": "2026-08-01T10:00:00Z",
                "disclaimer": (
                    "This record represents no real vehicle, person, police report, "
                    "insurance decision, or financial obligation."
                ),
            },
        }
    )
    obs = SourceObservation(
        observation_id="obs_ppsr_1",
        source_system=SourceSystem.PPSR_SYNTHETIC,
        ingestion_run_id="run_1",
        source_record_id="ppsr_1",
        raw_payload=payload,
        retrieved_at=datetime.now(UTC),
        synthetic=True,
    )

    result = engine.normalize(obs)
    assert isinstance(result, NormalizedObservation)
    assert isinstance(result.staged_data, PPSRInterestStaged)
    assert result.staged_data.result == "NO_MATCH"


def test_normalize_malformed_payload_produces_rejected_observation(
    engine: NormalizationEngine,
) -> None:
    """Verify unparseable payload produces a RejectedObservation without crashing."""
    corrupted_payload = "NOT_A_VALID_JSON_OR_ROW"
    obs = SourceObservation(
        observation_id="obs_bad_1",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_1",
        source_record_id="bad_1",
        raw_payload=corrupted_payload,
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )

    result = engine.normalize(obs)
    assert isinstance(result, RejectedObservation)
    assert result.observation_id == "obs_bad_1"
    assert result.source_system == SourceSystem.NHTSA_VPIC
    assert "Failed to parse payload" in result.error_message
