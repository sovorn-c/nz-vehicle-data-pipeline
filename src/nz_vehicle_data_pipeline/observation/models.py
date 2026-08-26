"""Data models for raw source observations and ingestion runs."""

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceSystem(StrEnum):
    """Identified origin publishing vehicle-related observations."""

    NZTA_MVR = "NZTA_MVR"
    NHTSA_VPIC = "NHTSA_VPIC"
    DEALER_FEED = "DEALER_FEED"
    PPSR_SYNTHETIC = "PPSR_SYNTHETIC"
    STOLEN_SYNTHETIC = "STOLEN_SYNTHETIC"
    WRITEOFF_SYNTHETIC = "WRITEOFF_SYNTHETIC"

    @property
    def is_synthetic(self) -> bool:
        """Return True if this source system is a synthetic test registry."""
        return self in {
            SourceSystem.DEALER_FEED,
            SourceSystem.PPSR_SYNTHETIC,
            SourceSystem.STOLEN_SYNTHETIC,
            SourceSystem.WRITEOFF_SYNTHETIC,
        }


class SourceObservation(BaseModel):
    """Immutable captured statement from a Source System (ADR 0001)."""

    model_config = ConfigDict(frozen=True)

    observation_id: str = Field(description="Unique identifier for this observation")
    source_system: SourceSystem = Field(description="Originating source system")
    ingestion_run_id: str = Field(description="Ingestion run that captured this observation")
    source_record_id: str = Field(description="Identifier within source system (e.g. row, key)")
    raw_payload: str = Field(description="Exact captured payload (JSON, CSV row, XML snippet)")
    payload_hash_sha256: str = Field(
        default="", description="SHA-256 hexadecimal digest of raw_payload"
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when payload was fetched",
    )
    synthetic: bool = Field(
        default=False, description="Flag indicating synthetic demonstration record"
    )

    @model_validator(mode="after")
    def validate_hash_and_synthetic_integrity(self) -> Self:
        """Enforce payload SHA-256 hash consistency and synthetic source labeling."""
        expected_hash = hashlib.sha256(self.raw_payload.encode("utf-8")).hexdigest()
        if not self.payload_hash_sha256:
            object.__setattr__(self, "payload_hash_sha256", expected_hash)
        elif self.payload_hash_sha256 != expected_hash:
            raise ValueError(
                f"payload_hash_sha256 does not match SHA-256 of raw_payload: "
                f"expected {expected_hash}, got {self.payload_hash_sha256}"
            )

        if self.source_system.is_synthetic and not self.synthetic:
            msg = f"Synthetic source system must have synthetic=True ({self.source_system.value})"
            raise ValueError(msg)
        return self


class IngestionRun(BaseModel):
    """Tracks execution lifecycle for an ingestion run."""

    ingestion_run_id: str
    source_system: SourceSystem
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "in_progress"
    record_count: int = 0
    error_message: str | None = None

    def mark_completed(self, count: int) -> None:
        """Mark run completed with total records ingested."""
        self.status = "completed"
        self.record_count = count
        self.completed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """Mark run failed with error message."""
        self.status = "failed"
        self.error_message = error
        self.completed_at = datetime.now(UTC)
