"""Tests for ReconciliationResult, byte-level determinism, and material hashing (ADR 0003, ADR 0004)."""

from datetime import UTC, datetime
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceAssessment,
    ConfidenceBand,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink
from nz_vehicle_data_pipeline.reconciliation.result import ReconciliationResult


def test_reconciliation_result_pure_determinism() -> None:
    """Verify ReconciliationResult has no ambient timestamp or random ID and produces identical material hashes."""
    as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    link = ProvenanceLink(
        observation_id="obs_nhtsa_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=as_of,
    )
    confidence = ConfidenceAssessment(
        score=91,
        band=ConfidenceBand.HIGH,
        field_scores={"make": 91},
        field_components={"make": {"authority": 100, "agreement": 70, "freshness": 100, "validation": 100}},
        rule_version="confidence-v1",
        explanation="High confidence",
    )

    res1 = ReconciliationResult(
        vin="1HGCR2F85HA000000",
        canonical_fields={"make": "HONDA"},
        field_provenance={"make": [link]},
        conflicts=[],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )

    res2 = ReconciliationResult(
        vin="1HGCR2F85HA000000",
        canonical_fields={"make": "HONDA"},
        field_provenance={"make": [link]},
        conflicts=[],
        confidence=confidence,
        as_of=as_of,
        rule_versions={"resolution": "resolution-v1", "confidence": "confidence-v1"},
    )

    assert res1.material_hash() == res2.material_hash()
    assert len(res1.material_hash()) == 64  # SHA-256 hex digest
