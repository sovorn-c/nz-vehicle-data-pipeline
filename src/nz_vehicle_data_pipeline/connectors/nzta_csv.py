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
        reader = csv.DictReader(io.StringIO(self._csv_content))
        for row_idx, row in enumerate(reader, start=1):
            normalized_row = {
                k.strip().lower(): (v.strip() if v else None)
                for k, v in row.items()
                if k is not None
            }
            yield RawSourceRecord(
                record_id=f"row_{row_idx}",
                payload=json.dumps(normalized_row),
                source_system=self.source_system,
                synthetic=False,
            )
