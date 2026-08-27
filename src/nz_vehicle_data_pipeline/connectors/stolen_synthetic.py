"""Connector for synthetic stolen vehicle reports (ADR 0005)."""

import json
from collections.abc import AsyncIterator
from typing import Any

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class SyntheticStolenConnector(SourceConnector):
    """Parses synthetic stolen vehicle JSON records."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.STOLEN_SYNTHETIC

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        for item in self._data:
            report_id = item.get("report_id") or "UNKNOWN_STOLEN"
            is_synthetic = bool(item.get("synthetic", True))
            yield RawSourceRecord(
                record_id=str(report_id),
                payload=json.dumps(item),
                source_system=self.source_system,
                synthetic=is_synthetic,
            )
