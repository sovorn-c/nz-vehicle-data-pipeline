"""CLI entrypoint for scale and throughput benchmark (e05s03)."""

import argparse
import asyncio
import sys

from nz_vehicle_data_pipeline.benchmark.generator import generate_benchmark_dataset
from nz_vehicle_data_pipeline.benchmark.runner import (
    BenchmarkMetrics,
    run_scale_benchmark,
)


def _render_table(metrics: BenchmarkMetrics, seed: int, conflict_rate: float) -> str:
    """Render human-readable formatted benchmark metrics."""
    return f"""============================================================
NZ Vehicle Data Pipeline — Scale & Throughput Benchmark
============================================================
Config:                    Seed={seed}, ConflictRate={conflict_rate * 100:.1f}%
Vehicles Reconciled:       {metrics.total_vehicles}
Total Observations:        {metrics.total_observations}
Conflicts Detected:        {metrics.conflicts_detected}
Duration:                  {metrics.duration_seconds:.4f}s
Throughput (Obs/sec):      {metrics.observations_per_second:,.1f} obs/s
Throughput (Vehicles/sec): {metrics.vehicles_per_second:,.1f} veh/s
Peak Heap Memory:          {metrics.peak_memory_mb:.2f} MB
============================================================"""


async def _run(count: int, seed: int, conflict_rate: float, output_format: str) -> None:
    dataset = generate_benchmark_dataset(count=count, seed=seed, conflict_rate=conflict_rate)
    metrics = await run_scale_benchmark(dataset)

    if output_format == "json":
        print(metrics.model_dump_json(indent=2))
    else:
        print(_render_table(metrics, seed, conflict_rate))


def main() -> None:
    """CLI entrypoint parsing options and executing benchmark."""
    parser = argparse.ArgumentParser(
        description="Run deterministic scale and throughput benchmark on vehicle pipeline."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of synthetic vehicles to reconcile (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic pseudo-random seed (default: 42)",
    )
    parser.add_argument(
        "--conflict-rate",
        type=float,
        default=0.1,
        help="Fraction of vehicles with intentional source conflicts (default: 0.1)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output report formatting (default: table)",
    )

    args = parser.parse_args()

    if args.count <= 0:
        print("Error: --count must be a positive integer", file=sys.stderr)
        sys.exit(1)

    if not 0.0 <= args.conflict_rate <= 1.0:
        print("Error: --conflict-rate must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(_run(args.count, args.seed, args.conflict_rate, args.format))
    except Exception as exc:
        print(f"Benchmark error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
