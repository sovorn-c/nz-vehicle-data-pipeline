"""Connector for synthetic write-off damage records (ADR 0005)."""

import json
from collections.abc import AsyncIterator
from typing import Any

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class SyntheticWriteoffConnector(SourceConnector):
    """Parses synthetic write-off JSON records."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.WRITEOFF_SYNTHETIC

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        for item in self._data:
            writeoff_id = item.get("writeoff_id") or "UNKNOWN_WRITEOFF"
            is_synthetic = bool(item.get("synthetic", True))
            yield RawSourceRecord(
                record_id=str(writeoff_id),
                payload=json.dumps(item),
                source_system=self.source_system,
                synthetic=is_synthetic,
            )
