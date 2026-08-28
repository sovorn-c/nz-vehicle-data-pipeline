"""Connector for NZTA bulk vehicle fleet CSV snapshots."""

import csv
import io
import json
from collections.abc import AsyncIterator

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class NZTAFleetCSVConnector(SourceConnector):
    """Parses NZTA bulk CSV snapshot data."""

    def __init__(self, csv_content: str) -> None:
        self._csv_content = csv_content

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.NZTA_MVR

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        lines = self._csv_content.splitlines()
        if not lines:
            return
        header = lines[0]
        reader = csv.DictReader(io.StringIO(self._csv_content))
        for row_idx, _row in enumerate(reader, start=1):
            raw_line = lines[row_idx] if row_idx < len(lines) else ""
            # Wrap raw CSV line in JSON envelope to preserve original bytes
            yield RawSourceRecord(
                record_id=f"row_{row_idx}",
                payload=json.dumps({"_csv_line": raw_line, "_csv_header": header}),
                source_system=self.source_system,
                synthetic=False,
            )
