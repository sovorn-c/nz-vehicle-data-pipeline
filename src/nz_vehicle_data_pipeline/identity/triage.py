"""Identity triage logic enforcing ADR 0002 canonical VIN rules."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from nz_vehicle_data_pipeline.identity.vin import validate_vin
from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import NZTAFleetStaged


class IdentityDisposition(StrEnum):
    """Reconciliation eligibility disposition for a normalized observation."""

    ELIGIBLE = "ELIGIBLE"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"


class TriageResult(BaseModel):
    """Result of evaluating an observation's identity eligibility."""

    model_config = ConfigDict(frozen=True)

    disposition: IdentityDisposition
    canonical_vin: str | None = None
    reason: str

    @property
    def is_eligible(self) -> bool:
        """Return True if this observation can create or merge a canonical vehicle."""
        return self.disposition == IdentityDisposition.ELIGIBLE


class IdentityTriage:
    """Evaluates normalized observations to determine canonical identity disposition (ADR 0002)."""

    def evaluate(self, observation: NormalizedObservation) -> TriageResult:
        """Evaluate observation and return triage disposition."""
        staged = observation.staged_data

        # NZTA fleet CSV observations only provide truncated VIN11 or plate
        if isinstance(staged, NZTAFleetStaged):
            return TriageResult(
                disposition=IdentityDisposition.EVIDENCE_ONLY,
                canonical_vin=None,
                reason=(
                    "Truncated or missing 17-char VIN (vin11 observed); "
                    "NZTA fleet snapshot provides attribute evidence only (ADR 0002)"
                ),
            )

        # For sources carrying a candidate VIN string
        candidate_vin = getattr(staged, "vin", None)
        if not candidate_vin:
            return TriageResult(
                disposition=IdentityDisposition.EVIDENCE_ONLY,
                canonical_vin=None,
                reason="No candidate VIN present in normalized observation",
            )

        val_result = validate_vin(candidate_vin)
        if not val_result.is_valid:
            return TriageResult(
                disposition=IdentityDisposition.EVIDENCE_ONLY,
                canonical_vin=None,
                reason=f"Invalid candidate VIN ({candidate_vin}): {val_result.error_reason}",
            )

        return TriageResult(
            disposition=IdentityDisposition.ELIGIBLE,
            canonical_vin=val_result.normalized_vin,
            reason="Verified 17-character ISO 3779 checksum",
        )
