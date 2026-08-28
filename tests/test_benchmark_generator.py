"""Unit tests for deterministic benchmark dataset generator (e05s03)."""

from nz_vehicle_data_pipeline.benchmark.generator import (
    generate_benchmark_dataset,
)
from nz_vehicle_data_pipeline.identity.vin import validate_vin


def test_generator_deterministic_output() -> None:
    """Verify same seed produces identical datasets and different seed produces different."""
    ds1 = generate_benchmark_dataset(count=20, seed=42)
    ds2 = generate_benchmark_dataset(count=20, seed=42)
    ds3 = generate_benchmark_dataset(count=20, seed=99)

    assert ds1.vins == ds2.vins
    assert len(ds1.vins) == 20
    assert len(ds1.connectors) >= 1

    assert ds1.vins != ds3.vins


def test_generator_vins_are_valid() -> None:
    """Verify all generated VINs pass ISO 3779 check-digit validation."""
    ds = generate_benchmark_dataset(count=50, seed=123)
    assert len(ds.vins) == 50

    for v in ds.vins:
        res = validate_vin(v)
        assert res.is_valid is True, f"Generated VIN '{v}' is invalid: {res.error_reason}"


def test_generator_conflict_rate() -> None:
    """Verify conflict rate controls frequency of contradictory observations."""
    ds_no_conflicts = generate_benchmark_dataset(count=30, seed=42, conflict_rate=0.0)
    assert ds_no_conflicts.conflicted_vin_count == 0

    ds_conflicts = generate_benchmark_dataset(count=30, seed=42, conflict_rate=1.0)
    assert ds_conflicts.conflicted_vin_count == 30
