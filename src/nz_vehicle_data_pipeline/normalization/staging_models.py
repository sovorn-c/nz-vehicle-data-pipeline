"""Strict staging data models for normalized source observations."""

from datetime import date
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WriteoffCategory(StrEnum):
    """Classification of vehicle damage/write-off."""

    STATUTORY = "STATUTORY"
    REPAIRABLE = "REPAIRABLE"
    NONE = "NONE"


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

    plate: str = Field(description="NZ registration plate")
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
            plate=_clean_str(raw.get("plate")) or "",
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
    """Normalized dealer feed listing record."""

    model_config = ConfigDict(frozen=True)

    dealer_id: str
    listing_id: str
    vin: str
    price_cents: int
    odometer_km: int
    condition: str = "GOOD"
    asking_price_nzd: str | None = None
    description: str | None = None

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, v: str) -> str:
        return v.strip().upper()


class PPSRInterestStaged(BaseModel):
    """Normalized synthetic PPSR security interest record."""

    model_config = ConfigDict(frozen=True)

    ppsr_id: str
    vin: str
    secured_party: str
    collateral_type: str
    registration_date: date
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_synthetic(self) -> Self:
        if not self.synthetic:
            msg = "Synthetic PPSR records must have synthetic=True"
            raise ValueError(msg)
        return self


class StolenIndicatorStaged(BaseModel):
    """Normalized synthetic stolen vehicle report."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    vin: str
    stolen_flag: bool
    report_date: date
    police_district: str | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_synthetic(self) -> Self:
        if not self.synthetic:
            msg = "Synthetic stolen records must have synthetic=True"
            raise ValueError(msg)
        return self


class WriteoffClassificationStaged(BaseModel):
    """Normalized synthetic write-off damage record."""

    model_config = ConfigDict(frozen=True)

    writeoff_id: str
    vin: str
    category: WriteoffCategory
    damage_date: date | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_synthetic(self) -> Self:
        if not self.synthetic:
            msg = "Synthetic write-off records must have synthetic=True"
            raise ValueError(msg)
        return self
