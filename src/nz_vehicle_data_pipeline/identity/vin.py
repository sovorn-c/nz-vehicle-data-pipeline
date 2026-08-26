"""ISO 3779 Vehicle Identification Number (VIN) validation and checksum logic (ADR 0002)."""

from pydantic import BaseModel, ConfigDict

# ISO 3779 character transliteration map
VIN_TRANSLITERATION_MAP: dict[str, int] = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
    "J": 1,
    "K": 2,
    "L": 3,
    "M": 4,
    "N": 5,
    "P": 7,
    "R": 9,
    "S": 2,
    "T": 3,
    "U": 4,
    "V": 5,
    "W": 6,
    "X": 7,
    "Y": 8,
    "Z": 9,
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
}

# ISO 3779 position weights (17 positions, index 8 / pos 9 weight is 0)
VIN_POSITION_WEIGHTS: list[int] = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

FORBIDDEN_VIN_CHARS: set[str] = {"I", "O", "Q"}


class VINValidationResult(BaseModel):
    """Result of validating a candidate VIN string."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    normalized_vin: str | None = None
    error_reason: str | None = None


def calculate_vin_check_digit(vin: str) -> str:
    """Calculate the ISO 3779 check digit for a 17-character VIN."""
    normalized = vin.strip().upper()
    if len(normalized) != 17:
        msg = f"VIN must be 17 characters to calculate check digit (got {len(normalized)})"
        raise ValueError(msg)

    total = 0
    for i, char in enumerate(normalized):
        weight = VIN_POSITION_WEIGHTS[i]
        if weight == 0:
            continue
        val = VIN_TRANSLITERATION_MAP.get(char)
        if val is None:
            msg = f"Invalid character '{char}' in VIN at position {i + 1}"
            raise ValueError(msg)
        total += val * weight

    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def validate_vin(raw_vin: str) -> VINValidationResult:
    """Validate a candidate VIN against ISO 3779 specifications (ADR 0002)."""
    if raw_vin is None:
        return VINValidationResult(is_valid=False, error_reason="VIN cannot be None")

    vin = raw_vin.strip().upper()

    if len(vin) != 17:
        return VINValidationResult(
            is_valid=False,
            normalized_vin=vin,
            error_reason=f"VIN must be exactly 17 characters (got {len(vin)})",
        )

    for char in vin:
        if char in FORBIDDEN_VIN_CHARS:
            return VINValidationResult(
                is_valid=False,
                normalized_vin=vin,
                error_reason=f"Illegal character '{char}' in VIN (I, O, Q are prohibited)",
            )
        if char not in VIN_TRANSLITERATION_MAP:
            return VINValidationResult(
                is_valid=False,
                normalized_vin=vin,
                error_reason=f"Non-alphanumeric character '{char}' in VIN",
            )

    expected_check_digit = calculate_vin_check_digit(vin)
    actual_check_digit = vin[8]

    if actual_check_digit != expected_check_digit:
        return VINValidationResult(
            is_valid=False,
            normalized_vin=vin,
            error_reason=(
                f"Invalid check digit at position 9: "
                f"expected '{expected_check_digit}', found '{actual_check_digit}'"
            ),
        )

    return VINValidationResult(
        is_valid=True,
        normalized_vin=vin,
    )
