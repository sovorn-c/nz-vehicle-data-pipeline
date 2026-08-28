"""Strict staging data models for normalized source observations (ADR 0002, ADR 0005)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SYNTHETIC_DISCLAIMER: str = (
    "This record represents no real vehicle, person, police report, insurance decision, "
    "or financial obligation."
)


class WriteoffCategory(StrEnum):
    """Legacy classification of vehicle damage/write-off."""

    STATUTORY = "STATUTORY"
    REPAIRABLE = "REPAIRABLE"
    NONE = "NONE"


class WriteoffStatus(StrEnum):
    """Classification of synthetic vehicle damage/write-off (ADR 0005)."""

    NONE = "NONE"
    REPAIRABLE = "REPAIRABLE"
    STATUTORY = "STATUTORY"
    UNKNOWN = "UNKNOWN"


class PPSRResult(StrEnum):
    """Result of a synthetic PPSR security interest search (ADR 0005)."""

    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    UNKNOWN = "UNKNOWN"


class StolenStatus(StrEnum):
    """Classification of synthetic stolen vehicle indicators (ADR 0005)."""

    LISTED = "LISTED"
    NOT_LISTED = "NOT_LISTED"
    UNKNOWN = "UNKNOWN"


class SyntheticMetadata(BaseModel):
    """Validated shared metadata for all synthetic records (ADR 0005)."""

    model_config = ConfigDict(frozen=True)

    synthetic: Literal[True] = True
    dataset_id: str = Field(description="Unique dataset identifier")
    dataset_version: str = Field(description="Version of synthetic dataset")
    scenario_id: str = Field(description="Scenario identifier within dataset")
    generated_at: datetime = Field(description="Fixed generation timestamp")
    disclaimer: str = Field(
        default=SYNTHETIC_DISCLAIMER, description="Mandatory synthetic disclaimer"
    )

    @field_validator("disclaimer")
    @classmethod
    def validate_disclaimer(cls, v: str) -> str:
        if v != SYNTHETIC_DISCLAIMER:
            msg = f"Disclaimer must be exactly '{SYNTHETIC_DISCLAIMER}'"
            raise ValueError(msg)
        return v


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s.upper() if s else None


def _clean_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def _clean_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


class NZTAFleetStaged(BaseModel):
    """Normalized vehicle record from NZTA bulk fleet snapshot."""

    model_config = ConfigDict(frozen=True)

    make: str = Field(description="Standardized vehicle make")
    model: str = Field(description="Standardized vehicle model")
    year: int | None = Field(default=None, description="Manufacture or registration year")
    vin11: str | None = Field(default=None, description="Truncated 11-char VIN (EVIDENCE ONLY)")
    chassis7: str | None = Field(default=None, description="7-char chassis number")
    engine_number: str | None = Field(default=None, description="Engine identifier")
    cc_rating: int | None = Field(default=None, description="Engine displacement in CC")
    motive_power: str | None = Field(default=None, description="Fuel / motive power type")
    body_type: str | None = Field(default=None, description="Vehicle body classification")
    first_nz_registration_year: int | None = None
    first_nz_registration_month: int | None = None

    @classmethod
    def from_raw_dict(cls, raw: dict[str, Any]) -> Self:
        """Construct normalized instance from raw CSV row dictionary."""
        return cls(
            make=_clean_str(raw.get("make")) or "UNKNOWN",
            model=_clean_str(raw.get("model")) or "UNKNOWN",
            year=_clean_int(raw.get("year")),
            vin11=_clean_str(raw.get("vin11")),
            chassis7=_clean_str(raw.get("chassis7")),
            engine_number=_clean_str(raw.get("engine_number")),
            cc_rating=_clean_int(raw.get("cc_rating")),
            motive_power=_clean_str(raw.get("motive_power")),
            body_type=_clean_str(raw.get("body_type")),
            first_nz_registration_year=_clean_int(raw.get("first_nz_registration_year")),
            first_nz_registration_month=_clean_int(raw.get("first_nz_registration_month")),
        )


class NHTSAVPICStaged(BaseModel):
    """Normalized vehicle record from NHTSA vPIC VIN decode API."""

    model_config = ConfigDict(frozen=True)

    vin: str = Field(description="Full 17-character VIN")
    make: str = Field(description="Manufacturer make")
    model: str = Field(description="Manufacturer model")
    model_year: int | None = Field(default=None, description="Model year")
    vehicle_type: str | None = None
    body_class: str | None = None
    engine_cylinders: int | None = None
    displacement_l: float | None = None
    manufacturer: str | None = None

    @classmethod
    def from_raw_dict(cls, raw: dict[str, Any]) -> Self:
        """Construct normalized instance from NHTSA JSON API response."""
        return cls(
            vin=_clean_str(raw.get("VIN") or raw.get("vin")) or "",
            make=_clean_str(raw.get("Make") or raw.get("make")) or "UNKNOWN",
            model=_clean_str(raw.get("Model") or raw.get("model")) or "UNKNOWN",
            model_year=_clean_int(raw.get("ModelYear") or raw.get("model_year")),
            vehicle_type=_clean_str(raw.get("VehicleType") or raw.get("vehicle_type")),
            body_class=_clean_str(raw.get("BodyClass") or raw.get("body_class")),
            engine_cylinders=_clean_int(raw.get("EngineCylinders") or raw.get("engine_cylinders")),
            displacement_l=_clean_float(raw.get("DisplacementL") or raw.get("displacement_l")),
            manufacturer=_clean_str(raw.get("Manufacturer") or raw.get("manufacturer")),
        )


class DealerListingStaged(BaseModel):
    """Normalized dealer feed listing record (ADR 0005, e04s02)."""

    model_config = ConfigDict(frozen=True)

    dealer_id: str
    listing_id: str
    vin: str
    price_cents: int
    odometer_km: int
    currency: str = "NZD"
    condition: str = "GOOD"
    availability: str = "AVAILABLE"
    make: str | None = None
    model: str | None = None
    model_year: int | None = None
    trim: str | None = None
    asking_price_nzd: str | None = None
    description: str | None = None
    listing_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    listed_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: SyntheticMetadata

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, v: str) -> str:
        return v.strip().upper()


class PPSRInterestDetail(BaseModel):
    """Individual security interest on a PPSR match."""

    model_config = ConfigDict(frozen=True)

    financing_statement_id: str
    secured_party: str
    collateral_type: str = "MOTOR_VEHICLE"
    registration_date: date
    status: str = "ACTIVE"


class PPSRInterestStaged(BaseModel):
    """Normalized synthetic PPSR security interest record (ADR 0005)."""

    model_config = ConfigDict(frozen=True)

    ppsr_id: str
    vin: str
    search_timestamp: datetime
    result: PPSRResult
    interests: list[PPSRInterestDetail] = Field(default_factory=list)
    metadata: SyntheticMetadata

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_ppsr_semantics(self) -> Self:
        if self.result == PPSRResult.MATCH and not self.interests:
            msg = "PPSR MATCH requires at least one interest"
            raise ValueError(msg)
        if self.result == PPSRResult.NO_MATCH and self.interests:
            msg = "PPSR NO_MATCH forbids interests"
            raise ValueError(msg)
        return self


class StolenIndicatorStaged(BaseModel):
    """Normalized synthetic stolen vehicle report (ADR 0005)."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    vin: str
    status: StolenStatus
    reported_at: datetime | None = None
    recovered_at: datetime | None = None
    police_district: str | None = None
    metadata: SyntheticMetadata

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_stolen_semantics(self) -> Self:
        if self.status == StolenStatus.LISTED and not self.reported_at:
            msg = "Stolen LISTED status requires reported_at timestamp"
            raise ValueError(msg)
        return self


class WriteoffClassificationStaged(BaseModel):
    """Normalized synthetic write-off damage record (ADR 0005)."""

    model_config = ConfigDict(frozen=True)

    writeoff_id: str
    vin: str
    status: WriteoffStatus
    damage_type: str | None = None
    event_date: date | None = None
    insurer: str | None = None
    repaired: bool = False
    metadata: SyntheticMetadata

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, v: str) -> str:
        return v.strip().upper()
