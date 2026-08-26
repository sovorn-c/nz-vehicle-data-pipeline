"""Identity validation and canonical triage (ADR 0002)."""

from nz_vehicle_data_pipeline.identity.triage import (
    IdentityDisposition,
    IdentityTriage,
    TriageResult,
)
from nz_vehicle_data_pipeline.identity.vin import (
    VINValidationResult,
    calculate_vin_check_digit,
    validate_vin,
)

__all__ = [
    "IdentityDisposition",
    "IdentityTriage",
    "TriageResult",
    "VINValidationResult",
    "calculate_vin_check_digit",
    "validate_vin",
]
