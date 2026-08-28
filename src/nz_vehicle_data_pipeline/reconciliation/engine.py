"""Reconciliation engine coordinating candidate resolution, conflicts, and confidence."""

from datetime import datetime
from typing import Any

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.observation.models import SourceObservation
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    CONFIDENCE_RULE_VERSION,
    ConfidenceEngine,
)
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import (
    RESOLUTION_RULE_VERSION,
    FieldResolver,
)
from nz_vehicle_data_pipeline.reconciliation.result import ReconciliationResult


class ReconciliationEngine:
    """Orchestrates candidate extraction, field resolution, and confidence (ADR 0003, ADR 0004)."""

    def __init__(
        self,
        extractor: CandidateExtractor | None = None,
        resolver: FieldResolver | None = None,
        confidence_engine: ConfidenceEngine | None = None,
    ) -> None:
        self._extractor = extractor or CandidateExtractor()
        self._resolver = resolver or FieldResolver()
        self._confidence_engine = confidence_engine or ConfidenceEngine()

    async def reconcile(
        self,
        vin: str,
        eligible_pairs: list[tuple[SourceObservation, NormalizedObservation]],
        as_of: datetime,
    ) -> ReconciliationResult:
        # Filter out observations captured after as_of
        valid_pairs = [(obs, norm) for obs, norm in eligible_pairs if obs.retrieved_at <= as_of]

        # For observations from the same source entity (e.g. same dealer_id or source record),
        # keep the latest point-in-time observation as of the evaluation timestamp
        effective_by_key: dict[
            tuple[str, str], tuple[SourceObservation, NormalizedObservation]
        ] = {}
        for obs, norm in valid_pairs:
            source_key = obs.source_system.value
            record_key = getattr(norm.staged_data, "dealer_id", None) or obs.source_record_id
            composite_key = (source_key, str(record_key))

            existing = effective_by_key.get(composite_key)
            if existing is None or obs.retrieved_at > existing[0].retrieved_at:
                effective_by_key[composite_key] = (obs, norm)

        all_candidates: list[CandidateValue] = []
        for obs, norm in effective_by_key.values():
            cands = self._extractor.extract(obs, norm)
            all_candidates.extend(cands)

        by_field: dict[str, list[CandidateValue]] = {}
        for c in all_candidates:
            by_field.setdefault(c.field_name, []).append(c)

        canonical_fields: dict[str, Any] = {}
        field_provenance: dict[str, list[ProvenanceLink]] = {}
        conflicts: list[FieldConflict] = []

        for field_name in sorted(by_field.keys()):
            cands = by_field[field_name]
            res = self._resolver.resolve_field(field_name, cands)

            if res.resolved_value is not None:
                canonical_fields[field_name] = res.resolved_value
                field_provenance[field_name] = res.supporting_provenance

            if res.conflict is not None:
                conflicts.append(res.conflict)

        confidence = self._confidence_engine.assess(
            resolved_fields=canonical_fields,
            field_provenance=field_provenance,
            conflicts=conflicts,
            field_candidates=by_field,
            as_of=as_of,
        )

        # Sort conflicts for deterministic output
        conflicts.sort(key=lambda c: c.field_name)

        return ReconciliationResult(
            vin=vin,
            canonical_fields=canonical_fields,
            field_provenance=field_provenance,
            conflicts=conflicts,
            confidence=confidence,
            as_of=as_of,
            rule_versions={
                "resolution": RESOLUTION_RULE_VERSION,
                "confidence": CONFIDENCE_RULE_VERSION,
            },
        )
