"""Tests for strict staging models across all source types (e01s02 task t01)."""

from datetime import date

import pytest
from pydantic import ValidationError

from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
    StolenIndicatorStaged,
    WriteoffCategory,
    WriteoffClassificationStaged,
)


def test_nzta_fleet_staged_valid_parsing() -> None:
    """Verify NZTA fleet CSV row parsing into typed staged model."""
    raw_data = {
        "plate": "ABC123",
        "make": "TOYOTA",
        "model": "COROLLA",
        "year": "2019",
        "vin11": "JTDKN3DU5A0",
        "chassis7": "1234567",
        "engine_number": "2ZR-123456",
        "cc_rating": "1798",
        "motive_power": "PETROL",
        "body_type": "HATCHBACK",
        "first_nz_registration_year": "2019",
        "first_nz_registration_month": "5",
    }

    staged = NZTAFleetStaged.from_raw_dict(raw_data)
    assert staged.plate == "ABC123"
    assert staged.make == "TOYOTA"
    assert staged.model == "COROLLA"
    assert staged.year == 2019
    assert staged.vin11 == "JTDKN3DU5A0"
    assert staged.cc_rating == 1798


def test_nzta_fleet_staged_uppercasing_and_trimming() -> None:
    """Verify string fields are stripped and normalized to uppercase."""
    raw_data = {
        "plate": "  abc123  ",
        "make": " toyota ",
        "model": " corolla ",
        "year": " 2018 ",
        "vin11": " jtdkn3du5a0 ",
        "cc_rating": "1800",
    }
    staged = NZTAFleetStaged.from_raw_dict(raw_data)
    assert staged.plate == "ABC123"
    assert staged.make == "TOYOTA"
    assert staged.model == "COROLLA"
    assert staged.year == 2018
    assert staged.vin11 == "JTDKN3DU5A0"


def test_nhtsa_vpic_staged_parsing() -> None:
    """Verify NHTSA vPIC REST API payload parsing."""
    raw_payload = {
        "VIN": "1HGCR2F83HA000000",
        "Make": "HONDA",
        "Model": "ACCORD",
        "ModelYear": "2017",
        "VehicleType": "PASSENGER CAR",
        "BodyClass": "Sedan/Saloon",
        "EngineCylinders": "4",
        "DisplacementL": "2.4",
        "Manufacturer": "HONDA MOTOR CO., LTD.",
    }
    staged = NHTSAVPICStaged.from_raw_dict(raw_payload)
    assert staged.vin == "1HGCR2F83HA000000"
    assert staged.make == "HONDA"
    assert staged.model_year == 2017
    assert staged.engine_cylinders == 4
    assert staged.displacement_l == 2.4


def test_dealer_listing_staged_parsing() -> None:
    """Verify dealer feed listing parsing."""
    raw_data = {
        "dealer_id": "DLR_99",
        "listing_id": "LST_12345",
        "vin": "1HGCR2F83HA000000",
        "price_cents": 1850000,
        "odometer_km": 65400,
        "condition": "EXCELLENT",
        "asking_price_nzd": "18500.00",
    }
    staged = DealerListingStaged.model_validate(raw_data)
    assert staged.dealer_id == "DLR_99"
    assert staged.vin == "1HGCR2F83HA000000"
    assert staged.price_cents == 1850000
    assert staged.odometer_km == 65400


def test_ppsr_synthetic_staged_parsing() -> None:
    """Verify synthetic PPSR interest parsing with synthetic=True enforcement."""
    raw_data = {
        "ppsr_id": "PPSR_987654",
        "vin": "1HGCR2F83HA000000",
        "secured_party": "ANZ Bank New Zealand Limited",
        "collateral_type": "Motor Vehicle",
        "registration_date": "2023-01-15",
        "synthetic": True,
    }
    staged = PPSRInterestStaged.model_validate(raw_data)
    assert staged.ppsr_id == "PPSR_987654"
    assert staged.registration_date == date(2023, 1, 15)
    assert staged.synthetic is True

    # Fails if synthetic is False
    with pytest.raises(ValidationError):
        PPSRInterestStaged.model_validate({**raw_data, "synthetic": False})


def test_stolen_and_writeoff_staged_parsing() -> None:
    """Verify synthetic stolen indicator and write-off classification staging."""
    stolen_raw = {
        "report_id": "STL_001",
        "vin": "1HGCR2F83HA000000",
        "stolen_flag": True,
        "report_date": "2024-03-01",
        "police_district": "Auckland City",
        "synthetic": True,
    }
    stolen_staged = StolenIndicatorStaged.model_validate(stolen_raw)
    assert stolen_staged.stolen_flag is True
    assert stolen_staged.police_district == "Auckland City"

    writeoff_raw = {
        "writeoff_id": "WO_001",
        "vin": "1HGCR2F83HA000000",
        "category": "STATUTORY",
        "damage_date": "2022-11-20",
        "synthetic": True,
    }
    writeoff_staged = WriteoffClassificationStaged.model_validate(writeoff_raw)
    assert writeoff_staged.category == WriteoffCategory.STATUTORY
