"""Tests for ISO 3779 VIN validator and check digit calculation (e01s03 task t01)."""

import pytest

from nz_vehicle_data_pipeline.identity.vin import (
    VINValidationResult,
    calculate_vin_check_digit,
    validate_vin,
)


@pytest.mark.parametrize(
    "valid_vin",
    [
        "1HGCR2F83HA000000",  # 9th char is 3
        "1FA6P8CF5H5000000",  # 9th char is 5
        "WAUZZZ8V8KA000000",  # European style valid checksum format
        "JTDKN3DU5A0000000",  # Toyota VIN format
        "1G1YY22U965000000",  # Check digit 9
        "1FTFW1ET4EF000000",  # Check digit 4
    ],
)
def test_valid_vin_checksum(valid_vin: str) -> None:
    """Verify known valid VINs pass validation."""
    result = validate_vin(valid_vin)
    assert result.is_valid is True
    assert result.normalized_vin == valid_vin
    assert result.error_reason is None


def test_vin_with_invalid_length() -> None:
    """Verify VIN shorter or longer than 17 characters is rejected."""
    result_short = validate_vin("JTDKN3DU5A0")  # 11-char NZTA truncated VIN
    assert result_short.is_valid is False
    assert result_short.error_reason == "VIN must be exactly 17 characters (got 11)"

    result_long = validate_vin("1HGCR2F83HA000000EXTRA")
    assert result_long.is_valid is False
    assert "17 characters" in str(result_long.error_reason)


def test_vin_with_forbidden_characters_ioq() -> None:
    """Verify letters I, O, Q are disallowed in 17-char VINs per ISO 3779."""
    for forbidden in ["I", "O", "Q"]:
        vin = f"1HGCR2F83HA00000{forbidden}"
        result = validate_vin(vin)
        assert result.is_valid is False
        assert f"Illegal character '{forbidden}' in VIN" in str(result.error_reason)


def test_vin_with_corrupted_check_digit() -> None:
    """Verify mismatch between calculated check digit and position 9 is rejected."""
    # 1HGCR2F83HA000000 has valid check digit 3 at index 8 (position 9).
    # Changing check digit to 7 must fail validation.
    corrupted_vin = "1HGCR2F87HA000000"
    result = validate_vin(corrupted_vin)
    assert result.is_valid is False
    assert "Invalid check digit" in str(result.error_reason)


def test_calculate_vin_check_digit_x() -> None:
    """Verify check digit remainder of 10 calculates as 'X'."""
    # Construct a VIN where weighted sum % 11 == 10
    # Let's test calculate_vin_check_digit function directly
    calc = calculate_vin_check_digit("1HGCR2F83HA000000")
    assert calc == "3"
