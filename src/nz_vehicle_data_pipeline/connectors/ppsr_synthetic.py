"""Connector for synthetic PPSR security interest records."""

import json
from collections.abc import AsyncIterator
from typing import Any

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class SyntheticPPSRConnector(SourceConnector):
    """Parses synthetic PPSR JSON records."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.PPSR_SYNTHETIC

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        for item in self._data:
            ppsr_id = item.get("ppsr_id") or "UNKNOWN_PPSR"
            # Ensure synthetic flag is always true
            item["synthetic"] = True
            yield RawSourceRecord(
                record_id=str(ppsr_id),
                payload=json.dumps(item),
                source_system=self.source_system,
                synthetic=True,
            )
