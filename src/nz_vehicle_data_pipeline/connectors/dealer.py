"""Connector for dealer inventory feeds (JSON / XML)."""

import json
from collections.abc import AsyncIterator
from typing import Any

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class DealerFeedConnector(SourceConnector):
    """Parses dealer feed JSON records."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.DEALER_FEED

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        for item in self._data:
            listing_id = item.get("listing_id") or "UNKNOWN_LISTING"
            yield RawSourceRecord(
                record_id=str(listing_id),
                payload=json.dumps(item),
                source_system=self.source_system,
                synthetic=True,
            )
