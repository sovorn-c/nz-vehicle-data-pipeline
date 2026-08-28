"""Scale and throughput benchmark runner measuring latency, throughput, and memory (e05s03)."""

import time
import tracemalloc
from collections import defaultdict
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.benchmark.generator import BenchmarkDataset
from nz_vehicle_data_pipeline.identity.triage import (
    IdentityDisposition,
    IdentityTriage,
)
from nz_vehicle_data_pipeline.normalization.engine import (
    NormalizationEngine,
    NormalizedObservation,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation
from nz_vehicle_data_pipeline.observation.store import InMemoryObservationStore
from nz_vehicle_data_pipeline.pipeline.orchestrator import IngestionPipeline
from nz_vehicle_data_pipeline.reconciliation.engine import ReconciliationEngine


class BenchmarkMetrics(BaseModel):
    """Performance metrics captured during benchmark run."""

    model_config = ConfigDict(frozen=True)

    total_vehicles: int = Field(description="Total canonical vehicles reconciled")
    total_observations: int = Field(description="Total raw observations ingested")
    duration_seconds: float = Field(description="Total execution time in seconds")
    observations_per_second: float = Field(description="Ingestion throughput (obs/sec)")
    vehicles_per_second: float = Field(description="Canonical throughput (vehicles/sec)")
    peak_memory_mb: float = Field(description="Peak heap memory allocated in megabytes")
    conflicts_detected: int = Field(description="Total field conflicts detected")


async def run_scale_benchmark(
    dataset: BenchmarkDataset,
    as_of: datetime | None = None,
) -> BenchmarkMetrics:
    """Execute end-to-end ingestion and reconciliation benchmark, measuring performance."""
    eval_as_of = as_of or datetime.now(UTC)

    obs_store = InMemoryObservationStore()
    norm_engine = NormalizationEngine()
    triage = IdentityTriage()
    ingestion = IngestionPipeline(store=obs_store, engine=norm_engine, triage=triage)
    reconciliation = ReconciliationEngine()

    tracemalloc.start()
    t0 = time.perf_counter()

    total_observations = 0
    eligible_groups: dict[str, list[tuple[SourceObservation, NormalizedObservation]]] = (
        defaultdict(list)
    )

    for connector in dataset.connectors:
        batch_res = await ingestion.ingest(connector, captured_at=eval_as_of)
        total_observations += batch_res.total_ingested

        for item in batch_res.items:
            if (
                isinstance(item.normalization_result, NormalizedObservation)
                and item.triage_result is not None
                and item.triage_result.disposition == IdentityDisposition.ELIGIBLE
                and item.triage_result.canonical_vin
            ):
                eligible_groups[item.triage_result.canonical_vin].append(
                    (item.observation, item.normalization_result)
                )

    conflicts_detected = 0
    for vin in sorted(eligible_groups.keys()):
        pairs = eligible_groups[vin]
        res = await reconciliation.reconcile(vin=vin, eligible_pairs=pairs, as_of=eval_as_of)
        conflicts_detected += len(res.conflicts)

    duration = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    duration = max(duration, 0.0001)  # Guard against division by zero on fast runs
    total_vehicles = len(eligible_groups)
    obs_per_sec = total_observations / duration
    veh_per_sec = total_vehicles / duration
    peak_mb = peak_bytes / (1024 * 1024)

    return BenchmarkMetrics(
        total_vehicles=total_vehicles,
        total_observations=total_observations,
        duration_seconds=round(duration, 4),
        observations_per_second=round(obs_per_sec, 2),
        vehicles_per_second=round(veh_per_sec, 2),
        peak_memory_mb=round(peak_mb, 2),
        conflicts_detected=conflicts_detected,
    )
