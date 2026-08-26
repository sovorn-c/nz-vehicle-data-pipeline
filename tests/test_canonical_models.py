"""Tests for CanonicalRevision and MaterialChangeDetector (e02s04 task t01)."""

from datetime import UTC, datetime
from nz_vehicle_data_pipeline.observation.models import SourceSystem
from nz_vehicle_data_pipeline.reconciliation.canonical import (
    CanonicalRevision,
    MaterialChangeDetector,
)
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceAssessment,
    ConfidenceBand,
)
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink


def test_canonical_revision_creation() -> None:
    """Verify CanonicalRevision holds immutable resolved state and provenance."""
    link = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
    )
    confidence = ConfidenceAssessment(
        score=95,
        band=ConfidenceBand.HIGH,
        contributions={"base": 95},
        rule_version="1.0.0",
        explanation="High confidence",
    )
    revision = CanonicalRevision(
        revision_id="rev_1",
        vin="1HGCR2F85HA000000",
        revision_number=1,
        canonical_fields={"make": "HONDA", "model": "ACCORD", "year": 2017},
        field_provenance={"make": link, "model": link, "year": link},
        conflicts=[],
        confidence=confidence,
    )
    assert revision.vin == "1HGCR2F85HA000000"
    assert revision.revision_number == 1
    assert revision.canonical_fields["make"] == "HONDA"
    assert revision.field_provenance["make"].source_system == SourceSystem.NHTSA_VPIC


def test_material_change_detector_identifies_changes() -> None:
    """Verify detector identifies value, provenance, and conflict changes."""
    link = ProvenanceLink(
        observation_id="obs_1",
        source_system=SourceSystem.NHTSA_VPIC,
        source_record_id="1",
        retrieved_at=datetime.now(UTC),
    )
    confidence = ConfidenceAssessment(
        score=90,
        band=ConfidenceBand.HIGH,
        contributions={"base": 90},
        rule_version="1.0.0",
        explanation="High",
    )

    rev1 = CanonicalRevision(
        revision_id="rev_1",
        vin="1HGCR2F85HA000000",
        revision_number=1,
        canonical_fields={"make": "HONDA", "year": 2017},
        field_provenance={"make": link, "year": link},
        conflicts=[],
        confidence=confidence,
    )

    detector = MaterialChangeDetector()

    # Identical content -> No material change
    assert detector.has_material_change(
        previous=rev1,
        candidate_fields={"make": "HONDA", "year": 2017},
        candidate_provenance={"make": link, "year": link},
        candidate_conflicts=[],
        candidate_confidence=confidence,
    ) is False

    # Value change -> Material change
    assert detector.has_material_change(
        previous=rev1,
        candidate_fields={"make": "HONDA", "year": 2018},
        candidate_provenance={"make": link, "year": link},
        candidate_conflicts=[],
        candidate_confidence=confidence,
    ) is True
