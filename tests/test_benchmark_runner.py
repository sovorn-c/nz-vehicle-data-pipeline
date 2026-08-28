"""Unit tests for async benchmark runner (e05s03)."""

import pytest

from nz_vehicle_data_pipeline.benchmark.generator import generate_benchmark_dataset
from nz_vehicle_data_pipeline.benchmark.runner import (
    BenchmarkMetrics,
    run_scale_benchmark,
)


@pytest.mark.asyncio
async def test_benchmark_runner_executes_in_memory() -> None:
    """Verify run_scale_benchmark executes in-memory and produces valid metrics."""
    dataset = generate_benchmark_dataset(count=20, seed=42, conflict_rate=0.2)
    metrics = await run_scale_benchmark(dataset)

    assert isinstance(metrics, BenchmarkMetrics)
    assert metrics.total_vehicles == 20
    assert metrics.total_observations >= 100
    assert metrics.duration_seconds > 0.0
    assert metrics.vehicles_per_second > 0.0
    assert metrics.observations_per_second > 0.0
    assert metrics.peak_memory_mb > 0.0
    assert metrics.conflicts_detected >= 1
