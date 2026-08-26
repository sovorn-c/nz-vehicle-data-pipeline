"""Pure deterministic reconciliation output and material change hashing (ADR 0003, ADR 0004)."""

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.reconciliation.confidence import ConfidenceAssessment
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink


class ReconciliationResult(BaseModel):
    """Immutable deterministic result of reconciling vehicle evidence (ADR 0004)."""

    model_config = ConfigDict(frozen=True)

    vin: str = Field(description="Canonical 17-character VIN")
    canonical_fields: dict[str, Any] = Field(
        description="Selected canonical field values (omits unresolved fields)"
    )
    field_provenance: dict[str, list[ProvenanceLink]] = Field(
        description="Trace from every canonical field to all same-value supporting observations"
    )
    conflicts: list[FieldConflict] = Field(
        default_factory=list,
        description="Recorded resolved and unresolved field conflicts",
    )
    confidence: ConfidenceAssessment = Field(
        description="Reproducible evidence confidence assessment"
    )
    as_of: datetime = Field(description="Explicit UTC evaluation timestamp used for reconciliation")
    rule_versions: dict[str, str] = Field(
        description="Map of applied resolution and confidence rule versions"
    )

    def material_hash(self) -> str:
        """Compute SHA-256 fingerprint over canonical material for idempotent persistence."""
        canonical_material = {
            "vin": self.vin,
            "canonical_fields": {
                k: self.canonical_fields[k] for k in sorted(self.canonical_fields)
            },
            "field_provenance": {
                k: sorted(p.observation_id for p in self.field_provenance[k])
                for k in sorted(self.field_provenance)
            },
            "conflicts": [
                {
                    "field": c.field_name,
                    "state": c.state.value,
                    "winning_value": c.winning_value,
                    "rule_version": c.rule_version,
                }
                for c in sorted(self.conflicts, key=lambda x: x.field_name)
            ],
            "confidence": {
                "score": self.confidence.score,
                "band": self.confidence.band.value,
                "rule_version": self.confidence.rule_version,
            },
            "rule_versions": {k: self.rule_versions[k] for k in sorted(self.rule_versions)},
        }
        encoded = json.dumps(canonical_material, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
