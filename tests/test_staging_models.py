"""Tests for strict staging models across all source types (e01s02 task t01)."""

from typing import Any

import pytest
from pydantic import ValidationError

from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
    StolenIndicatorStaged,
    WriteoffClassificationStaged,
)


def test_nzta_fleet_staged_valid_parsing() -> None:
    """Verify NZTA fleet CSV row parsing into typed staged model."""
    raw_data = {
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
    assert staged.make == "TOYOTA"
    assert staged.model == "COROLLA"
    assert staged.year == 2019
    assert staged.vin11 == "JTDKN3DU5A0"
    assert staged.cc_rating == 1798


def test_nzta_fleet_staged_uppercasing_and_trimming() -> None:
    """Verify string fields are stripped and normalized to uppercase."""
    raw_data = {
        "make": " toyota ",
        "model": " corolla ",
        "year": " 2018 ",
        "vin11": " jtdkn3du5a0 ",
        "cc_rating": "1800",
    }
    staged = NZTAFleetStaged.from_raw_dict(raw_data)
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
        "metadata": {
            "synthetic": True,
            "dataset_id": "synth_ds",
            "dataset_version": "1.0",
            "scenario_id": "dealer_scen",
            "generated_at": "2026-08-01T10:00:00Z",
            "disclaimer": (
                "This record represents no real vehicle, person, police report, "
                "insurance decision, or financial obligation."
            ),
        },
    }
    staged = DealerListingStaged.model_validate(raw_data)
    assert staged.dealer_id == "DLR_99"
    assert staged.vin == "1HGCR2F83HA000000"
    assert staged.price_cents == 1850000
    assert staged.odometer_km == 65400


def test_ppsr_synthetic_staged_parsing() -> None:
    """Verify synthetic PPSR interest parsing with strict metadata."""
    raw_data: dict[str, Any] = {
        "ppsr_id": "PPSR_987654",
        "vin": "1HGCR2F83HA000000",
        "search_timestamp": "2026-08-01T12:00:00Z",
        "result": "MATCH",
        "interests": [
            {
                "financing_statement_id": "FS123",
                "secured_party": "ANZ Bank New Zealand Limited",
                "collateral_type": "Motor Vehicle",
                "registration_date": "2023-01-15",
                "status": "ACTIVE",
            }
        ],
        "metadata": {
            "synthetic": True,
            "dataset_id": "synth_ds",
            "dataset_version": "1.0",
            "scenario_id": "match_scenario",
            "generated_at": "2026-08-01T10:00:00Z",
            "disclaimer": (
                "This record represents no real vehicle, person, police report, "
                "insurance decision, or financial obligation."
            ),
        },
    }
    staged = PPSRInterestStaged.model_validate(raw_data)
    assert staged.ppsr_id == "PPSR_987654"
    assert len(staged.interests) == 1
    assert staged.metadata.synthetic is True

    # Fails if synthetic is False
    bad_data = dict(raw_data)
    bad_data["metadata"] = {**raw_data["metadata"], "synthetic": False}
    with pytest.raises(ValidationError):
        PPSRInterestStaged.model_validate(bad_data)


def test_stolen_and_writeoff_staged_parsing() -> None:
    """Verify synthetic stolen indicator and write-off classification staging."""
    meta = {
        "synthetic": True,
        "dataset_id": "synth_ds",
        "dataset_version": "1.0",
        "scenario_id": "risk_scen",
        "generated_at": "2026-08-01T10:00:00Z",
        "disclaimer": (
            "This record represents no real vehicle, person, police report, "
            "insurance decision, or financial obligation."
        ),
    }
    stolen_raw = {
        "report_id": "STL_001",
        "vin": "1HGCR2F83HA000000",
        "status": "LISTED",
        "reported_at": "2024-03-01T00:00:00Z",
        "police_district": "Auckland City",
        "metadata": meta,
    }
    stolen_staged = StolenIndicatorStaged.model_validate(stolen_raw)
    assert stolen_staged.status == "LISTED"
    assert stolen_staged.police_district == "Auckland City"

    writeoff_raw = {
        "writeoff_id": "WO_001",
        "vin": "1HGCR2F83HA000000",
        "status": "STATUTORY",
        "event_date": "2022-11-20",
        "metadata": meta,
    }
    writeoff_staged = WriteoffClassificationStaged.model_validate(writeoff_raw)
    assert writeoff_staged.status == "STATUTORY"
