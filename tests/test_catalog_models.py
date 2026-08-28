"""Unit tests for vehicle catalog schemas and validation (e05s01)."""

import pytest
from pydantic import ValidationError

from nz_vehicle_data_pipeline.api.schemas import (
    VehicleCatalogPage,
    VehicleSummary,
)


def test_vehicle_summary_schema_valid() -> None:
    """Verify VehicleSummary can be constructed with canonical fields."""
    summary = VehicleSummary(
        vin="7A8HB000000000001",
        make="Toyota",
        model="Corolla",
        year=2021,
        registration_status="active",
        confidence_score=0.95,
        has_conflicts=False,
        revision_number=1,
        synthetic=True,
    )
    assert summary.vin == "7A8HB000000000001"
    assert summary.make == "Toyota"
    assert summary.model == "Corolla"
    assert summary.year == 2021
    assert summary.confidence_score == 0.95
    assert summary.has_conflicts is False
    assert summary.synthetic is True


def test_vehicle_catalog_page_validation() -> None:
    """Verify VehicleCatalogPage validates pagination and items."""
    item = VehicleSummary(
        vin="7A8HB000000000001",
        make="Toyota",
        model="Corolla",
        year=2021,
        confidence_score=0.90,
        has_conflicts=True,
        revision_number=1,
        synthetic=True,
    )
    page = VehicleCatalogPage(
        items=[item],
        total=1,
        limit=20,
        offset=0,
        disclaimer="Synthetic demonstration data only.",
    )
    assert page.total == 1
    assert page.limit == 20
    assert page.offset == 0
    assert len(page.items) == 1
    assert page.items[0].vin == "7A8HB000000000001"
    assert page.disclaimer == "Synthetic demonstration data only."


def test_vehicle_catalog_page_negative_bounds() -> None:
    """Verify negative limit or offset fails validation."""
    with pytest.raises(ValidationError):
        VehicleCatalogPage(items=[], total=0, limit=-1, offset=0)

    with pytest.raises(ValidationError):
        VehicleCatalogPage(items=[], total=0, limit=20, offset=-1)
