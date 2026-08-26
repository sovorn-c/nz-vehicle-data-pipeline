"""Base connector abstractions for source data ingestion."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from nz_vehicle_data_pipeline.observation.models import SourceSystem


class RawSourceRecord(BaseModel):
    """Raw payload yielded by a source connector."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    payload: str
    source_system: SourceSystem
    synthetic: bool = False


class SourceConnector(ABC):
    """Abstract base class for all vehicle data source connectors."""

    @property
    @abstractmethod
    def source_system(self) -> SourceSystem:
        """The source system identified by this connector."""

    @property
    def is_synthetic(self) -> bool:
        """Whether this connector supplies synthetic demonstration data."""
        return self.source_system.is_synthetic

    @abstractmethod
    def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        """Asynchronously stream or fetch raw source records."""
