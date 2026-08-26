"""Reconciliation, provenance tracking, and conflict resolution engine."""

from nz_vehicle_data_pipeline.reconciliation.canonical import (
    CanonicalRevision,
    MaterialChangeDetector,
)
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceAssessment,
    ConfidenceBand,
    ConfidenceEngine,
)
from nz_vehicle_data_pipeline.reconciliation.conflicts import (
    ConflictDetector,
    ConflictState,
    FieldConflict,
)
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import (
    FieldResolutionResult,
    FieldResolver,
)

__all__ = [
    "CandidateExtractor",
    "CandidateValue",
    "CanonicalRevision",
    "ConfidenceAssessment",
    "ConfidenceBand",
    "ConfidenceEngine",
    "ConflictDetector",
    "ConflictState",
    "FieldConflict",
    "FieldResolutionResult",
    "FieldResolver",
    "MaterialChangeDetector",
    "ProvenanceLink",
]
