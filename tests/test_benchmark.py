"""Integration tests for benchmark CLI entrypoint (e05s03)."""

import json
import subprocess
import sys


def test_benchmark_cli_json_format() -> None:
    """Verify benchmark CLI runs with JSON output and valid metrics."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "nz_vehicle_data_pipeline.benchmark",
            "--count",
            "25",
            "--seed",
            "42",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Benchmark CLI failed: {res.stderr}"

    data = json.loads(res.stdout)
    assert data["total_vehicles"] == 25
    assert data["total_observations"] >= 125
    assert data["duration_seconds"] > 0
    assert data["vehicles_per_second"] > 0
    assert data["peak_memory_mb"] > 0


def test_benchmark_cli_table_format() -> None:
    """Verify benchmark CLI runs with human-readable table output."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "nz_vehicle_data_pipeline.benchmark",
            "--count",
            "10",
            "--seed",
            "42",
            "--format",
            "table",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Benchmark CLI failed: {res.stderr}"
    assert "NZ Vehicle Data Pipeline" in res.stdout
    assert "Vehicles Reconciled" in res.stdout
    assert "Throughput" in res.stdout
