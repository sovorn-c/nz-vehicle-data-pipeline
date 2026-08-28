"""Release composition service for reconciliation and publication (e04s03)."""

from collections import defaultdict
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from nz_vehicle_data_pipeline.connectors.base import SourceConnector
from nz_vehicle_data_pipeline.identity.triage import (
    IdentityDisposition,
    IdentityTriage,
)
from nz_vehicle_data_pipeline.normalization.engine import (
    NormalizationEngine,
    NormalizedObservation,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation
from nz_vehicle_data_pipeline.observation.store import ObservationStore
from nz_vehicle_data_pipeline.persistence.canonical_store import (
    PostgresCanonicalStore,
)
from nz_vehicle_data_pipeline.pipeline.orchestrator import IngestionPipeline
from nz_vehicle_data_pipeline.reconciliation.engine import ReconciliationEngine


class VinPublicationSummary(BaseModel):
    """Publication outcome for an individual canonical VIN."""

    model_config = ConfigDict(frozen=True)

    vin: str
    revision_id: str
    revision_number: int
    created: bool
    material_hash: str


class ReleasePipelineSummary(BaseModel):
    """Structured result summary of a deterministic release pipeline execution."""

    model_config = ConfigDict(frozen=True)

    manifest_id: str
    total_observations: int
    eligible_count: int
    rejected_count: int
    evidence_only_count: int
    vehicles_processed: int
    revisions_created: int
    revisions_reused: int
    vin_outcomes: list[VinPublicationSummary]
    source_counts: dict[str, int]


class ReleasePipeline:
    """Orchestrates multi-connector ingestion, VIN reconciliation, and publication."""

    def __init__(
        self,
        obs_store: ObservationStore,
        canonical_store: PostgresCanonicalStore,
        normalization_engine: NormalizationEngine | None = None,
        identity_triage: IdentityTriage | None = None,
        reconciliation_engine: ReconciliationEngine | None = None,
    ) -> None:
        self._ingestion_pipeline = IngestionPipeline(
            store=obs_store,
            engine=normalization_engine,
            triage=identity_triage,
        )
        self._canonical_store = canonical_store
        self._reconciliation_engine = reconciliation_engine or ReconciliationEngine()

    async def run(
        self,
        connectors: list[SourceConnector],
        capture_times: dict[str, datetime] | None = None,
        as_of: datetime | None = None,
        manifest_id: str = "default_manifest",
        run_id_prefix: str | None = None,
    ) -> ReleasePipelineSummary:
        """Run complete release cycle across all connectors deterministically."""
        eval_as_of = as_of or datetime.now(UTC)

        total_obs = 0
        total_eligible = 0
        total_rejected = 0
        total_evidence_only = 0
        source_counts: dict[str, int] = {}

        # Eligible observations grouped by valid canonical VIN
        eligible_groups: dict[str, list[tuple[SourceObservation, NormalizedObservation]]] = (
            defaultdict(list)
        )

        for connector in connectors:
            source_sys = connector.source_system.value
            cap_time = capture_times.get(source_sys) if capture_times else None
            deterministic_run_id = (
                f"{run_id_prefix}__{source_sys.lower()}" if run_id_prefix else None
            )

            batch_res = await self._ingestion_pipeline.ingest(
                connector, run_id=deterministic_run_id, captured_at=cap_time
            )
            total_obs += batch_res.total_ingested
            total_eligible += batch_res.eligible_count
            total_rejected += batch_res.rejected_count
            total_evidence_only += batch_res.evidence_only_count
            source_counts[source_sys] = source_counts.get(source_sys, 0) + batch_res.total_ingested

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

        # Lexical sorting of canonical VINs for deterministic execution order
        sorted_vins = sorted(eligible_groups.keys())
        vin_outcomes: list[VinPublicationSummary] = []
        revs_created = 0
        revs_reused = 0

        for vin in sorted_vins:
            pairs = eligible_groups[vin]
            recon_res = await self._reconciliation_engine.reconcile(
                vin=vin, eligible_pairs=pairs, as_of=eval_as_of
            )
            rev_rec, created = await self._canonical_store.publish(recon_res)

            if created:
                revs_created += 1
            else:
                revs_reused += 1

            vin_outcomes.append(
                VinPublicationSummary(
                    vin=vin,
                    revision_id=rev_rec.revision_id,
                    revision_number=rev_rec.revision_number,
                    created=created,
                    material_hash=rev_rec.material_hash,
                )
            )

        return ReleasePipelineSummary(
            manifest_id=manifest_id,
            total_observations=total_obs,
            eligible_count=total_eligible,
            rejected_count=total_rejected,
            evidence_only_count=total_evidence_only,
            vehicles_processed=len(sorted_vins),
            revisions_created=revs_created,
            revisions_reused=revs_reused,
            vin_outcomes=vin_outcomes,
            source_counts=source_counts,
        )
