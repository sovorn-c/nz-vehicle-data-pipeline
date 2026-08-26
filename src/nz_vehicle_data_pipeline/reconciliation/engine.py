"""Reconciliation engine coordinating candidate resolution, conflicts, and revisions."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.reconciliation.canonical import (
    CanonicalRevision,
    MaterialChangeDetector,
)
from nz_vehicle_data_pipeline.reconciliation.confidence import ConfidenceEngine
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.extractor import CandidateExtractor
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)
from nz_vehicle_data_pipeline.reconciliation.resolution import FieldResolver


class ReconciliationEngine:
    """Orchestrates candidate extraction and canonical revisions (ADR 0001, ADR 0003)."""

    def __init__(
        self,
        extractor: CandidateExtractor | None = None,
        resolver: FieldResolver | None = None,
        confidence_engine: ConfidenceEngine | None = None,
        change_detector: MaterialChangeDetector | None = None,
    ) -> None:
        self._extractor = extractor or CandidateExtractor()
        self._resolver = resolver or FieldResolver()
        self._confidence_engine = confidence_engine or ConfidenceEngine()
        self._change_detector = change_detector or MaterialChangeDetector()

    async def reconcile(
        self,
        vin: str,
        eligible_pairs: list[tuple[SourceObservation, NormalizedObservation]],
        previous_revision: CanonicalRevision | None = None,
    ) -> CanonicalRevision | None:
        """Reconcile all eligible source observations for a canonical VIN."""
        if not eligible_pairs:
            return previous_revision

        all_candidates: list[CandidateValue] = []
        sources_seen: set[SourceSystem] = set()

        for obs, norm in eligible_pairs:
            sources_seen.add(obs.source_system)
            cands = self._extractor.extract(obs, norm)
            all_candidates.extend(cands)

        by_field: dict[str, list[CandidateValue]] = {}
        for c in all_candidates:
            by_field.setdefault(c.field_name, []).append(c)

        canonical_fields: dict[str, Any] = {}
        field_provenance: dict[str, ProvenanceLink] = {}
        conflicts: list[FieldConflict] = []

        for field_name, cands in by_field.items():
            res = self._resolver.resolve_field(field_name, cands)
            canonical_fields[field_name] = res.resolved_value
            field_provenance[field_name] = res.winning_provenance
            if res.conflict:
                conflicts.append(res.conflict)

        confidence = self._confidence_engine.assess(canonical_fields, conflicts, sources_seen)

        # Check if material change occurred relative to previous revision
        if previous_revision is not None and not self._change_detector.has_material_change(
            previous=previous_revision,
            candidate_fields=canonical_fields,
            candidate_provenance=field_provenance,
            candidate_conflicts=conflicts,
            candidate_confidence=confidence,
        ):
            return previous_revision

        new_rev_number = (previous_revision.revision_number + 1) if previous_revision else 1
        rev_id = f"rev_{vin}_{new_rev_number}_{uuid4().hex[:6]}"

        return CanonicalRevision(
            revision_id=rev_id,
            vin=vin,
            revision_number=new_rev_number,
            canonical_fields=canonical_fields,
            field_provenance=field_provenance,
            conflicts=conflicts,
            confidence=confidence,
            reconciled_at=datetime.now(UTC),
        )
