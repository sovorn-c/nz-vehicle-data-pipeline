"""Unit tests for strict synthetic dealer listing contracts (e04s02)."""

from datetime import UTC, datetime
import pytest
from pydantic import ValidationError

from nz_vehicle_data_pipeline.normalization.staging_models import (
    SYNTHETIC_DISCLAIMER,
    DealerListingStaged,
    SyntheticMetadata,
)


def get_dealer_metadata() -> SyntheticMetadata:
    return SyntheticMetadata(
        synthetic=True,
        dataset_id="nz-synth-dealer",
        dataset_version="2026.08",
        scenario_id="clean_listing",
        generated_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC),
        disclaimer=SYNTHETIC_DISCLAIMER,
    )


def test_dealer_contract_complete_fields() -> None:
    """Verify DealerListingStaged requires SyntheticMetadata and supports researched vocabulary."""
    meta = get_dealer_metadata()
    listed_at = datetime(2026, 8, 1, 9, 0, 0, tzinfo=UTC)

    staged = DealerListingStaged(
        dealer_id="DLR_AKL_01",
        listing_id="LST_9901",
        vin="1HGCR2F85HA000000",
        make="HONDA",
        model="ACCORD",
        model_year=2017,
        trim="EX-L",
        condition="EXCELLENT",
        price_cents=2150000,
        currency="NZD",
        odometer_km=48500,
        availability="AVAILABLE",
        listing_url="https://example.com/listings/LST_9901",
        image_urls=["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
        listed_at=listed_at,
        updated_at=listed_at,
        description="Clean one-owner vehicle",
        metadata=meta,
    )

    assert staged.dealer_id == "DLR_AKL_01"
    assert staged.listing_id == "LST_9901"
    assert staged.vin == "1HGCR2F85HA000000"
    assert staged.price_cents == 2150000
    assert staged.currency == "NZD"
    assert staged.trim == "EX-L"
    assert len(staged.image_urls) == 2
    assert staged.metadata.synthetic is True
    assert staged.metadata.disclaimer == SYNTHETIC_DISCLAIMER


def test_dealer_contract_requires_metadata() -> None:
    """Verify DealerListingStaged rejects missing or invalid synthetic metadata."""
    with pytest.raises(ValidationError):
        DealerListingStaged(
            dealer_id="DLR_01",
            listing_id="LST_01",
            vin="1HGCR2F85HA000000",
            price_cents=1000000,
            odometer_km=50000,
            metadata=None,  # type: ignore[arg-type]
        )
