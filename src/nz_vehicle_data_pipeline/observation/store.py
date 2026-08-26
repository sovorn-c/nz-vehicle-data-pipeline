"""Observation storage interface and in-memory implementation."""

from abc import ABC, abstractmethod

from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem


class DuplicateObservationError(Exception):
    """Raised when attempting to overwrite an observation with different content."""


class ObservationStore(ABC):
    """Abstract interface for storing and retrieving immutable source observations."""

    @abstractmethod
    async def save(self, observation: SourceObservation) -> None:
        """Save a source observation. Must be idempotent for identical content."""

    @abstractmethod
    async def get_by_id(self, observation_id: str) -> SourceObservation | None:
        """Retrieve an observation by its unique identifier."""

    @abstractmethod
    async def get_by_run_id(self, ingestion_run_id: str) -> list[SourceObservation]:
        """Retrieve all observations associated with an ingestion run."""

    @abstractmethod
    async def get_by_source_system(self, source_system: SourceSystem) -> list[SourceObservation]:
        """Retrieve all observations from a specific source system."""

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of stored observations."""


class InMemoryObservationStore(ObservationStore):
    """In-memory observation store for testing and pipeline buffering."""

    def __init__(self) -> None:
        self._records: dict[str, SourceObservation] = {}

    async def save(self, observation: SourceObservation) -> None:
        """Save observation with immutability and duplicate payload validation."""
        existing = self._records.get(observation.observation_id)
        if existing is not None:
            if existing.payload_hash_sha256 != observation.payload_hash_sha256:
                msg = (
                    f"Observation {observation.observation_id} already exists with a different "
                    f"payload hash ({existing.payload_hash_sha256} vs "
                    f"{observation.payload_hash_sha256})"
                )
                raise DuplicateObservationError(msg)
            # Idempotent re-save of exact same observation
            return

        self._records[observation.observation_id] = observation

    async def get_by_id(self, observation_id: str) -> SourceObservation | None:
        """Get observation by identifier."""
        return self._records.get(observation_id)

    async def get_by_run_id(self, ingestion_run_id: str) -> list[SourceObservation]:
        """Get all observations for an ingestion run."""
        return [obs for obs in self._records.values() if obs.ingestion_run_id == ingestion_run_id]

    async def get_by_source_system(self, source_system: SourceSystem) -> list[SourceObservation]:
        """Get all observations for a source system."""
        return [obs for obs in self._records.values() if obs.source_system == source_system]

    async def count(self) -> int:
        """Return count of stored observations."""
        return len(self._records)
