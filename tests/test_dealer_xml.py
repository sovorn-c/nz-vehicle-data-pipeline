"""Unit tests for bounded dealer XML parsing and security guards (e04s02)."""

from datetime import UTC, datetime

from nz_vehicle_data_pipeline.normalization.engine import (
    NormalizationEngine,
    NormalizedObservation,
    RejectedObservation,
)
from nz_vehicle_data_pipeline.normalization.staging_models import (
    SYNTHETIC_DISCLAIMER,
    DealerListingStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem

VALID_DEALER_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<dealer-listing>
    <dealer_id>DLR_01</dealer_id>
    <listing_id>LST_1001</listing_id>
    <vin>1HGCR2F85HA000000</vin>
    <make>HONDA</make>
    <model>ACCORD</model>
    <model_year>2017</model_year>
    <trim>EX-L</trim>
    <price_cents>2450000</price_cents>
    <currency>NZD</currency>
    <odometer_km>35000</odometer_km>
    <condition>EXCELLENT</condition>
    <availability>AVAILABLE</availability>
    <image_urls>
        <image_url>https://example.com/1.jpg</image_url>
        <image_url>https://example.com/2.jpg</image_url>
    </image_urls>
    <metadata>
        <synthetic>true</synthetic>
        <dataset_id>nz-synth-dealer</dataset_id>
        <dataset_version>2026.08</dataset_version>
        <scenario_id>xml_clean</scenario_id>
        <generated_at>2026-08-01T10:00:00Z</generated_at>
        <disclaimer>{SYNTHETIC_DISCLAIMER}</disclaimer>
    </metadata>
</dealer-listing>
"""


def test_parse_valid_dealer_xml() -> None:
    """Verify valid bounded dealer XML normalizes into DealerListingStaged."""
    engine = NormalizationEngine()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    obs = SourceObservation(
        observation_id="obs_xml_1",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="dealer_xml_LST_1001",
        raw_payload=VALID_DEALER_XML,
        retrieved_at=as_of,
        synthetic=True,
    )

    result = engine.normalize(obs)
    assert isinstance(result, NormalizedObservation)
    assert isinstance(result.staged_data, DealerListingStaged)
    assert result.staged_data.dealer_id == "DLR_01"
    assert result.staged_data.vin == "1HGCR2F85HA000000"
    assert result.staged_data.price_cents == 2450000
    assert result.staged_data.trim == "EX-L"
    assert len(result.staged_data.image_urls) == 2


def test_reject_oversized_xml_payload() -> None:
    """Verify XML exceeding 256 KiB is rejected before parsing."""
    engine = NormalizationEngine()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    # 256 KiB = 262,144 bytes. Generate 262,145 bytes
    padding = " " * (262145 - len(VALID_DEALER_XML))
    oversized = VALID_DEALER_XML + padding

    obs = SourceObservation(
        observation_id="obs_xml_big",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="dealer_xml_big",
        raw_payload=oversized,
        retrieved_at=as_of,
        synthetic=True,
    )

    result = engine.normalize(obs)
    assert isinstance(result, RejectedObservation)
    assert "exceeds maximum allowed size" in result.error_message


def test_reject_doctype_and_entity_declarations() -> None:
    """Verify DOCTYPE and ENTITY declarations are rejected before ElementTree parsing."""
    engine = NormalizationEngine()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    malicious_xml = """<?xml version="1.0"?>
    <!DOCTYPE dealer-listing [
        <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <dealer-listing>
        <dealer_id>&xxe;</dealer_id>
        <listing_id>1</listing_id>
        <vin>1HGCR2F85HA000000</vin>
        <price_cents>1000</price_cents>
        <odometer_km>100</odometer_km>
    </dealer-listing>
    """

    obs = SourceObservation(
        observation_id="obs_xml_xxe",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="dealer_xml_xxe",
        raw_payload=malicious_xml,
        retrieved_at=as_of,
        synthetic=True,
    )

    result = engine.normalize(obs)
    assert isinstance(result, RejectedObservation)
    assert "Forbidden XML declaration" in result.error_message


def test_reject_duplicate_scalar_elements() -> None:
    """Verify duplicate scalar XML elements reject as conflicting input."""
    engine = NormalizationEngine()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    duplicate_xml = """<?xml version="1.0"?>
    <dealer-listing>
        <dealer_id>D1</dealer_id>
        <dealer_id>D2</dealer_id>
        <listing_id>1</listing_id>
        <vin>1HGCR2F85HA000000</vin>
        <price_cents>1000</price_cents>
        <odometer_km>100</odometer_km>
    </dealer-listing>
    """

    obs = SourceObservation(
        observation_id="obs_xml_dup",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="dealer_xml_dup",
        raw_payload=duplicate_xml,
        retrieved_at=as_of,
        synthetic=True,
    )

    result = engine.normalize(obs)
    assert isinstance(result, RejectedObservation)
    assert "Duplicate XML element" in result.error_message


def test_reject_unknown_root_element() -> None:
    """Verify XML with unknown root element is rejected."""
    engine = NormalizationEngine()
    as_of = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    bad_root_xml = """<?xml version="1.0"?>
    <unexpected-root>
        <listing_id>1</listing_id>
    </unexpected-root>
    """

    obs = SourceObservation(
        observation_id="obs_xml_root",
        source_system=SourceSystem.DEALER_FEED,
        ingestion_run_id="run_1",
        source_record_id="dealer_xml_root",
        raw_payload=bad_root_xml,
        retrieved_at=as_of,
        synthetic=True,
    )

    result = engine.normalize(obs)
    assert isinstance(result, RejectedObservation)
    assert "Expected root element" in result.error_message
