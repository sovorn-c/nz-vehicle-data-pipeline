"""Reconciliation, provenance tracking, and conflict resolution engine (ADR 0003, ADR 0004)."""

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
from nz_vehicle_data_pipeline.reconciliation.engine import ReconciliationEngine
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import (
    FieldResolutionResult,
    FieldResolver,
)
from nz_vehicle_data_pipeline.reconciliation.result import ReconciliationResult

__all__ = [
    "CandidateExtractor",
    "CandidateValue",
    "ConfidenceAssessment",
    "ConfidenceBand",
    "ConfidenceEngine",
    "ConflictDetector",
    "ConflictState",
    "FieldConflict",
    "FieldResolutionResult",
    "FieldResolver",
    "ProvenanceLink",
    "ReconciliationEngine",
    "ReconciliationResult",
]
