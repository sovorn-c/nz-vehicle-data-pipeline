"""Connector for dealer XML feeds (e04s02)."""

from collections.abc import AsyncIterator

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class DealerXMLConnector(SourceConnector):
    """Parses dealer XML feed records with format-qualified record identifiers."""

    def __init__(self, records: list[tuple[str, str]]) -> None:
        """Takes list of (listing_id, xml_payload)."""
        self._records = records

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.DEALER_FEED

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        for listing_id, xml_payload in self._records:
            yield RawSourceRecord(
                record_id=f"dealer_xml_{listing_id}",
                payload=xml_payload,
                source_system=self.source_system,
                synthetic=True,
            )
