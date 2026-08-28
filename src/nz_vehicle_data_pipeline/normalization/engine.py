"""Normalization engine mapping raw observations into validated staged models."""

import csv
import io
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
from nz_vehicle_data_pipeline.normalization.xml_dealer import parse_dealer_xml
from nz_vehicle_data_pipeline.observation.models import (
    SourceObservation,
    SourceSystem,
)

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
            raw_dict = self._parse_payload_to_dict(
                observation.raw_payload, observation.source_system
            )
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

    def _parse_payload_to_dict(
        self, raw_payload: str, source_system: SourceSystem
    ) -> dict[str, Any]:
        """Parse JSON, XML, or key-value formatted payload into dictionary."""
        trimmed = raw_payload.strip()

        # Handle XML payloads for dealer feed
        if trimmed.startswith("<"):
            if source_system == SourceSystem.DEALER_FEED:
                return parse_dealer_xml(raw_payload)
            msg = f"XML payload format not supported for source {source_system.value}"
            raise ValueError(msg)

        if trimmed.startswith("{") and trimmed.endswith("}"):
            res = json.loads(trimmed)
            if isinstance(res, dict):
                # Unwrap NZTA CSV envelope: raw CSV line + header preserved as JSON
                if "_csv_line" in res and "_csv_header" in res:
                    return self._parse_csv_line(res["_csv_header"], res["_csv_line"])
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

    @staticmethod
    def _parse_csv_line(header: str, line: str) -> dict[str, Any]:
        """Parse a raw CSV line using its header into a dictionary."""
        reader = csv.reader(io.StringIO(f"{header}\n{line}"))
        headers = next(reader)
        values = next(reader)
        return {
            h.strip().lower(): (v.strip() if v else None)
            for h, v in zip(headers, values, strict=False)
            if h is not None
        }

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
