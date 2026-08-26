"""Normalization engine mapping raw observations into validated staged models."""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
    StolenIndicatorStaged,
    WriteoffClassificationStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem

type StagedData = (
    NZTAFleetStaged
    | NHTSAVPICStaged
    | DealerListingStaged
    | PPSRInterestStaged
    | StolenIndicatorStaged
    | WriteoffClassificationStaged
)


class NormalizedObservation(BaseModel):
    """Successfully validated and typed staged observation."""

    model_config = ConfigDict(frozen=True)

    observation_id: str
    source_system: SourceSystem
    staged_data: StagedData
    normalized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RejectedObservation(BaseModel):
    """Observation that failed validation or normalization parsing."""

    model_config = ConfigDict(frozen=True)

    observation_id: str
    source_system: SourceSystem
    error_message: str
    rejected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


type NormalizationResult = NormalizedObservation | RejectedObservation


class NormalizationEngine:
    """Transforms raw source observations into structured staged representations."""

    def normalize(self, observation: SourceObservation) -> NormalizationResult:
        """Normalize observation into typed model or return rejection outcome."""
        try:
            raw_dict = self._parse_payload_to_dict(observation.raw_payload)
            staged = self._map_to_staged_model(observation.source_system, raw_dict)
            return NormalizedObservation(
                observation_id=observation.observation_id,
                source_system=observation.source_system,
                staged_data=staged,
            )
        except Exception as exc:
            return RejectedObservation(
                observation_id=observation.observation_id,
                source_system=observation.source_system,
                error_message=f"Failed to parse payload: {exc}",
            )

    def _parse_payload_to_dict(self, raw_payload: str) -> dict[str, Any]:
        """Parse JSON or key-value formatted payload into dictionary."""
        trimmed = raw_payload.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            res = json.loads(trimmed)
            if isinstance(res, dict):
                return res
            msg = f"Expected JSON object, got {type(res).__name__}"
            raise ValueError(msg)

        # Fallback for key-value or query-string like rows (e.g. k1=v1&k2=v2)
        if "=" in trimmed:
            pairs = trimmed.split("&") if "&" in trimmed else trimmed.split(",")
            parsed: dict[str, Any] = {}
            for pair in pairs:
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    parsed[k.strip()] = v.strip()
            if parsed:
                return parsed

        msg = f"Unrecognized payload format: {raw_payload[:50]}"
        raise ValueError(msg)

    def _map_to_staged_model(self, source_system: SourceSystem, data: dict[str, Any]) -> StagedData:
        """Map raw dictionary to source-specific staging model."""
        match source_system:
            case SourceSystem.NZTA_MVR:
                return NZTAFleetStaged.from_raw_dict(data)
            case SourceSystem.NHTSA_VPIC:
                return NHTSAVPICStaged.from_raw_dict(data)
            case SourceSystem.DEALER_FEED:
                return DealerListingStaged.model_validate(data)
            case SourceSystem.PPSR_SYNTHETIC:
                return PPSRInterestStaged.model_validate(data)
            case SourceSystem.STOLEN_SYNTHETIC:
                return StolenIndicatorStaged.model_validate(data)
            case SourceSystem.WRITEOFF_SYNTHETIC:
                return WriteoffClassificationStaged.model_validate(data)
