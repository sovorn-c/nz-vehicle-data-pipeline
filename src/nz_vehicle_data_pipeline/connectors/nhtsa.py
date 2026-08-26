"""Connector for NHTSA vPIC VIN decode REST API."""

import json
from collections.abc import AsyncIterator
from typing import Any

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


class NHTSAVPICConnector(SourceConnector):
    """Parses NHTSA vPIC VIN decode API responses."""

    def __init__(self, data: dict[str, Any] | list[dict[str, Any]]) -> None:
        self._data = data

    @property
    def source_system(self) -> SourceSystem:
        return SourceSystem.NHTSA_VPIC

    async def fetch_all(self) -> AsyncIterator[RawSourceRecord]:
        results: list[dict[str, Any]] = []
        if isinstance(self._data, dict):
            if "Results" in self._data and isinstance(self._data["Results"], list):
                results = self._data["Results"]
            else:
                results = [self._data]
        elif isinstance(self._data, list):
            results = self._data

        for row in results:
            vin = row.get("VIN") or row.get("vin") or "UNKNOWN_VIN"
            yield RawSourceRecord(
                record_id=str(vin),
                payload=json.dumps(row),
                source_system=self.source_system,
                synthetic=False,
            )
