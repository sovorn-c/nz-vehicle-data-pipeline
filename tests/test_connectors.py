"""Tests for source connectors (e01s04 task t01)."""

import json
from nz_vehicle_data_pipeline.connectors.base import RawSourceRecord
from nz_vehicle_data_pipeline.connectors.dealer import DealerFeedConnector
from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.nzta_csv import NZTAFleetCSVConnector
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector
from nz_vehicle_data_pipeline.observation.models import SourceSystem


async def test_nzta_csv_connector_parses_csv_rows() -> None:
    """Verify NZTA CSV connector yields RawSourceRecords from CSV text."""
    csv_text = (
        "PLATE,MAKE,MODEL,YEAR,VIN11,CHASSIS7,CC_RATING\n"
        "ABC123,TOYOTA,COROLLA,2019,JTDKN3DU5A0,1234567,1798\n"
        "XYZ789,MAZDA,AXELA,2015,JM0BL10F200,7654321,1998\n"
    )
    connector = NZTAFleetCSVConnector(csv_content=csv_text)
    assert connector.source_system == SourceSystem.NZTA_MVR

    records: list[RawSourceRecord] = []
    async for rec in connector.fetch_all():
        records.append(rec)

    assert len(records) == 2
    assert records[0].record_id == "row_1"
    parsed_0 = json.loads(records[0].payload)
    assert parsed_0["plate"] == "ABC123"
    assert parsed_0["make"] == "TOYOTA"


async def test_nhtsa_vpic_connector_parses_response() -> None:
    """Verify NHTSA vPIC connector parses API JSON response into raw records."""
    api_response = {
        "Count": 1,
        "Message": "Results returned successfully",
        "Results": [
            {
                "VIN": "1HGCR2F85HA000000",
                "Make": "HONDA",
                "Model": "ACCORD",
                "ModelYear": "2017",
                "VehicleType": "PASSENGER CAR",
            }
        ],
    }
    connector = NHTSAVPICConnector(data=api_response)
    assert connector.source_system == SourceSystem.NHTSA_VPIC

    records: list[RawSourceRecord] = []
    async for rec in connector.fetch_all():
        records.append(rec)

    assert len(records) == 1
    assert records[0].record_id == "1HGCR2F85HA000000"
    parsed = json.loads(records[0].payload)
    assert parsed["Make"] == "HONDA"


async def test_dealer_feed_connector_parses_json_feed() -> None:
    """Verify Dealer feed connector yields records."""
    feed_data = [
        {
            "dealer_id": "DLR_10",
            "listing_id": "LST_900",
            "vin": "1FA6P8CF8H5000000",
            "price_cents": 3200000,
            "odometer_km": 28000,
        }
    ]
    connector = DealerFeedConnector(data=feed_data)
    assert connector.source_system == SourceSystem.DEALER_FEED

    records: list[RawSourceRecord] = []
    async for rec in connector.fetch_all():
        records.append(rec)

    assert len(records) == 1
    assert records[0].record_id == "LST_900"


async def test_synthetic_ppsr_connector_parses_records() -> None:
    """Verify synthetic PPSR connector yields records with synthetic=True."""
    ppsr_data = [
        {
            "ppsr_id": "PPSR_555",
            "vin": "1HGCR2F85HA000000",
            "secured_party": "ASB Bank",
            "collateral_type": "Motor Vehicle",
            "registration_date": "2023-05-20",
            "synthetic": True,
        }
    ]
    connector = SyntheticPPSRConnector(data=ppsr_data)
    assert connector.source_system == SourceSystem.PPSR_SYNTHETIC

    records: list[RawSourceRecord] = []
    async for rec in connector.fetch_all():
        records.append(rec)

    assert len(records) == 1
    assert records[0].record_id == "PPSR_555"
