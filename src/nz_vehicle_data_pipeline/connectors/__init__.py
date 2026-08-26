"""Source connectors for external and synthetic vehicle data."""

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.connectors.dealer import DealerFeedConnector
from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.nzta_csv import NZTAFleetCSVConnector
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector

__all__ = [
    "DealerFeedConnector",
    "NHTSAVPICConnector",
    "NZTAFleetCSVConnector",
    "RawSourceRecord",
    "SourceConnector",
    "SyntheticPPSRConnector",
]
