"""Deterministic synthetic observation generator for scale and throughput benchmarking (e05s03)."""

import random
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.connectors.base import SourceConnector
from nz_vehicle_data_pipeline.connectors.dealer import SyntheticDealerConnector
from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector
from nz_vehicle_data_pipeline.connectors.stolen_synthetic import (
    SyntheticStolenConnector,
)
from nz_vehicle_data_pipeline.connectors.writeoff_synthetic import (
    SyntheticWriteoffConnector,
)
from nz_vehicle_data_pipeline.identity.vin import calculate_vin_check_digit
from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER

SAMPLE_MAKES_MODELS: list[tuple[str, str]] = [
    ("TOYOTA", "COROLLA"),
    ("TOYOTA", "RAV4"),
    ("HONDA", "CIVIC"),
    ("HONDA", "ACCORD"),
    ("MAZDA", "MAZDA3"),
    ("MAZDA", "CX-5"),
    ("NISSAN", "LEAF"),
    ("SUBARU", "OUTBACK"),
    ("HYUNDAI", "TUCSON"),
    ("KIA", "SPORTAGE"),
]

WMI_PREFIXES = ["7A8HB000", "1HGCR2F8", "1FA6P8CF", "JM0BL10F", "WAUZZZ8K", "KMHD35LH"]


def generate_valid_vin(prefix: str, serial_num: int) -> str:
    """Generate a 17-character ISO 3779 checksum compliant VIN."""
    serial_str = f"{serial_num:08d}"
    base = f"{prefix}0{serial_str}"
    check = calculate_vin_check_digit(base)
    return f"{prefix}{check}{serial_str}"


class BenchmarkDataset(BaseModel):
    """Encapsulates generated synthetic connectors and vehicle manifest."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    vins: list[str] = Field(description="Generated unique canonical VINs")
    connectors: list[SourceConnector] = Field(description="Connector instances ready for ingestion")
    conflicted_vin_count: int = Field(description="Number of VINs containing intentional conflicts")
    total_observations: int = Field(description="Total observations across all connectors")


def generate_benchmark_dataset(
    count: int = 100,
    seed: int = 42,
    conflict_rate: float = 0.1,
) -> BenchmarkDataset:
    """Generate deterministic benchmark dataset across multi-source connectors."""
    rng = random.Random(seed)

    vins: list[str] = []
    nhtsa_records: list[dict[str, Any]] = []
    dealer_records: list[dict[str, Any]] = []
    ppsr_records: list[dict[str, Any]] = []
    stolen_records: list[dict[str, Any]] = []
    writeoff_records: list[dict[str, Any]] = []

    conflicted_vins = 0

    for i in range(1, count + 1):
        wmi = WMI_PREFIXES[(i - 1) % len(WMI_PREFIXES)]
        serial_val = (((seed % 1000) * 100000) + i) % 100_000_000
        vin = generate_valid_vin(wmi, serial_val)
        vins.append(vin)

        make, model = SAMPLE_MAKES_MODELS[(i - 1) % len(SAMPLE_MAKES_MODELS)]
        year = 2015 + ((i - 1) % 10)
        has_conflict = (rng.random() < conflict_rate) if conflict_rate > 0.0 else False

        # 1. NHTSA observation
        nhtsa_records.append(
            {
                "VIN": vin,
                "Make": make,
                "Model": model,
                "ModelYear": year,
                "BodyClass": "Sedan",
                "VehicleType": "PASSENGER CAR",
                "DisplacementL": "2.0",
                "EngineConfiguration": "I-4",
                "Manufacturer": f"{make} MOTOR COMPANY",
            }
        )

        # 2. Dealer observation
        dealer_records.append(
            {
                "dealer_id": f"DLR_{((i - 1) % 5) + 1:02d}",
                "listing_id": f"LST_BENCH_{i:06d}",
                "vin": vin,
                "make": make,
                "model": model,
                "model_year": year,
                "price_cents": 2000000 + ((i * 100000) % 3000000),
                "odometer_km": 30000 + ((i * 5000) % 150000),
                "condition": "GOOD",
                "availability": "AVAILABLE",
                "currency": "NZD",
                "image_urls": [],
                "metadata": {
                    "synthetic": True,
                    "dataset_id": f"benchmark-seed-{seed}",
                    "dataset_version": "2026.08",
                    "scenario_id": "scale_benchmark",
                    "generated_at": "2026-08-01T10:00:00Z",
                    "disclaimer": SYNTHETIC_DISCLAIMER,
                },
            }
        )

        # 3. PPSR observation
        if has_conflict:
            conflicted_vins += 1
            ppsr_records.append(
                {
                    "ppsr_id": f"PPSR_BENCH_{i:06d}_A",
                    "vin": vin,
                    "search_timestamp": "2026-08-01T12:00:00Z",
                    "result": "MATCH",
                    "interests": [
                        {
                            "financing_statement_id": f"FS_BENCH_{i:06d}",
                            "secured_party": "BENCHMARK FINANCE",
                            "collateral_type": "MOTOR_VEHICLE",
                            "registration_date": "2025-01-01",
                            "status": "ACTIVE",
                        }
                    ],
                    "metadata": {
                        "synthetic": True,
                        "dataset_id": f"benchmark-seed-{seed}",
                        "dataset_version": "2026.08",
                        "scenario_id": "scale_benchmark_conflict",
                        "generated_at": "2026-08-01T10:00:00Z",
                        "disclaimer": SYNTHETIC_DISCLAIMER,
                    },
                }
            )
            ppsr_records.append(
                {
                    "ppsr_id": f"PPSR_BENCH_{i:06d}_B",
                    "vin": vin,
                    "search_timestamp": "2026-08-01T12:00:00Z",
                    "result": "NO_MATCH",
                    "interests": [],
                    "metadata": {
                        "synthetic": True,
                        "dataset_id": f"benchmark-seed-{seed}",
                        "dataset_version": "2026.08",
                        "scenario_id": "scale_benchmark_conflict",
                        "generated_at": "2026-08-01T10:00:00Z",
                        "disclaimer": SYNTHETIC_DISCLAIMER,
                    },
                }
            )
        else:
            ppsr_records.append(
                {
                    "ppsr_id": f"PPSR_BENCH_{i:06d}",
                    "vin": vin,
                    "search_timestamp": "2026-08-01T12:00:00Z",
                    "result": "NO_MATCH",
                    "interests": [],
                    "metadata": {
                        "synthetic": True,
                        "dataset_id": f"benchmark-seed-{seed}",
                        "dataset_version": "2026.08",
                        "scenario_id": "scale_benchmark",
                        "generated_at": "2026-08-01T10:00:00Z",
                        "disclaimer": SYNTHETIC_DISCLAIMER,
                    },
                }
            )

        # 4. Stolen observation
        stolen_records.append(
            {
                "report_id": f"STOLEN_BENCH_{i:06d}",
                "vin": vin,
                "status": "NOT_LISTED",
                "incident_date": None,
                "metadata": {
                    "synthetic": True,
                    "dataset_id": f"benchmark-seed-{seed}",
                    "dataset_version": "2026.08",
                    "scenario_id": "scale_benchmark",
                    "generated_at": "2026-08-01T10:00:00Z",
                    "disclaimer": SYNTHETIC_DISCLAIMER,
                },
            }
        )

        # 5. Writeoff observation
        writeoff_records.append(
            {
                "writeoff_id": f"WRITEOFF_BENCH_{i:06d}",
                "vin": vin,
                "status": "NONE",
                "damage_type": "NONE",
                "loss_date": None,
                "metadata": {
                    "synthetic": True,
                    "dataset_id": f"benchmark-seed-{seed}",
                    "dataset_version": "2026.08",
                    "scenario_id": "scale_benchmark",
                    "generated_at": "2026-08-01T10:00:00Z",
                    "disclaimer": SYNTHETIC_DISCLAIMER,
                },
            }
        )

    connectors: list[SourceConnector] = [
        NHTSAVPICConnector(data=nhtsa_records),
        SyntheticDealerConnector(data=dealer_records),
        SyntheticPPSRConnector(data=ppsr_records),
        SyntheticStolenConnector(data=stolen_records),
        SyntheticWriteoffConnector(data=writeoff_records),
    ]

    total_obs = (
        len(nhtsa_records)
        + len(dealer_records)
        + len(ppsr_records)
        + len(stolen_records)
        + len(writeoff_records)
    )

    return BenchmarkDataset(
        vins=vins,
        connectors=connectors,
        conflicted_vin_count=conflicted_vins,
        total_observations=total_obs,
    )
