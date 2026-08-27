"""Source connector interfaces and concrete implementations."""

from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord, SourceConnector
from nz_vehicle_data_pipeline.connectors.dealer import (
    DealerFeedConnector,
    SyntheticDealerConnector,
)
from nz_vehicle_data_pipeline.connectors.dealer_xml import DealerXMLConnector
from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.nzta_csv import NZTAFleetCSVConnector
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector
from nz_vehicle_data_pipeline.connectors.stolen_synthetic import (
    SyntheticStolenConnector,
)
from nz_vehicle_data_pipeline.connectors.writeoff_synthetic import (
    SyntheticWriteoffConnector,
)

__all__ = [
    "DealerFeedConnector",
    "DealerXMLConnector",
    "NHTSAVPICConnector",
    "NZTAFleetCSVConnector",
    "RawSourceRecord",
    "SourceConnector",
    "SyntheticDealerConnector",
    "SyntheticPPSRConnector",
    "SyntheticStolenConnector",
    "SyntheticWriteoffConnector",
]
