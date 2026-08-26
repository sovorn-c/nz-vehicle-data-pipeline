"""Tests for raw source observation and ingestion models (e01s01)."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nz_vehicle_data_pipeline.observation.models import (
    IngestionRun,
    SourceObservation,
    SourceSystem,
)


def test_source_system_enum_values() -> None:
    """Verify all recognized source systems are present."""
    expected = {
        "NZTA_MVR",
        "NHTSA_VPIC",
        "DEALER_FEED",
        "PPSR_SYNTHETIC",
        "STOLEN_SYNTHETIC",
        "WRITEOFF_SYNTHETIC",
    }
    actual = {s.value for s in SourceSystem}
    assert actual == expected


def test_source_observation_creates_sha256_hash_if_omitted() -> None:
    """Verify observation computes SHA-256 hash automatically from raw_payload."""
    payload = {"plate": "ABC123", "make": "TOYOTA", "year": 2018}
    payload_str = json.dumps(payload, sort_keys=True)
    expected_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    obs = SourceObservation(
        observation_id="obs_001",
        source_system=SourceSystem.NZTA_MVR,
        ingestion_run_id="run_001",
        source_record_id="row_42",
        raw_payload=payload_str,
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )

    assert obs.payload_hash_sha256 == expected_hash
    assert obs.synthetic is False


def test_source_observation_verifies_provided_hash_matches() -> None:
    """Verify error raised if provided hash does not match payload content."""
    payload_str = "make=TOYOTA&model=COROLLA"
    invalid_hash = "0" * 64

    with pytest.raises(ValidationError) as exc_info:
        SourceObservation(
            observation_id="obs_002",
            source_system=SourceSystem.NZTA_MVR,
            ingestion_run_id="run_001",
            source_record_id="row_43",
            raw_payload=payload_str,
            payload_hash_sha256=invalid_hash,
            retrieved_at=datetime.now(UTC),
            synthetic=False,
        )
    assert "payload_hash_sha256 does not match SHA-256 of raw_payload" in str(exc_info.value)


def test_source_observation_synthetic_flag_enforcement() -> None:
    """Verify synthetic source systems must have synthetic=True."""
    payload_str = '{"vin": "TEST1234567890123", "lien": true}'

    with pytest.raises(ValidationError) as exc_info:
        SourceObservation(
            observation_id="obs_003",
            source_system=SourceSystem.PPSR_SYNTHETIC,
            ingestion_run_id="run_002",
            source_record_id="ppsr_99",
            raw_payload=payload_str,
            retrieved_at=datetime.now(UTC),
            synthetic=False,
        )
    assert "Synthetic source system must have synthetic=True" in str(exc_info.value)


def test_ingestion_run_lifecycle() -> None:
    """Verify IngestionRun tracks progress and record metrics."""
    started = datetime.now(UTC)
    run = IngestionRun(
        ingestion_run_id="run_100",
        source_system=SourceSystem.NHTSA_VPIC,
        started_at=started,
    )
    assert run.status == "in_progress"
    assert run.record_count == 0
    assert run.completed_at is None

    run.mark_completed(count=150)
    assert run.status == "completed"
    assert run.record_count == 150
    assert run.completed_at is not None
