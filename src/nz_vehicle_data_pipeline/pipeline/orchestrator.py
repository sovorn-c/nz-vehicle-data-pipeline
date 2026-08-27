"""Pipeline orchestrator for source ingestion, normalization, and identity triage."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from nz_vehicle_data_pipeline.connectors.base import SourceConnector
from nz_vehicle_data_pipeline.identity.triage import (
    IdentityDisposition,
    IdentityTriage,
    TriageResult,
)
from nz_vehicle_data_pipeline.normalization.engine import (
    NormalizationEngine,
    NormalizationResult,
    NormalizedObservation,
    RejectedObservation,
)
from nz_vehicle_data_pipeline.observation.models import (
    IngestionRun,
    SourceObservation,
    SourceSystem,
)
from nz_vehicle_data_pipeline.observation.store import ObservationStore


class ProcessedObservation(BaseModel):
    """Pipeline item holding observation, normalization, and triage results."""

    model_config = ConfigDict(frozen=True)

    observation: SourceObservation
    normalization_result: NormalizationResult
    triage_result: TriageResult | None = None


class IngestionBatchResult(BaseModel):
    """Result of an ingestion run on a single connector source."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    source_system: SourceSystem
    total_ingested: int
    normalized_count: int
    rejected_count: int
    eligible_count: int
    evidence_only_count: int
    items: list[ProcessedObservation] = Field(default_factory=list)


class IngestionPipeline:
    """Orchestrates source ingestion, evidence capture, normalization, and identity triage."""

    def __init__(
        self,
        store: ObservationStore,
        engine: NormalizationEngine | None = None,
        triage: IdentityTriage | None = None,
    ) -> None:
        self._store = store
        self._engine = engine or NormalizationEngine()
        self._triage = triage or IdentityTriage()

    async def ingest(
        self,
        connector: SourceConnector,
        run_id: str | None = None,
        captured_at: datetime | None = None,
    ) -> IngestionBatchResult:
        """Run end-to-end ingestion on a connector."""
        actual_run_id = run_id or f"run_{connector.source_system.value.lower()}_{uuid4().hex[:8]}"
        capture_time = captured_at or datetime.now(UTC)

        ingestion_run = IngestionRun(
            ingestion_run_id=actual_run_id,
            source_system=connector.source_system,
            started_at=capture_time,
        )

        processed_items: list[ProcessedObservation] = []
        normalized_count = 0
        rejected_count = 0
        eligible_count = 0
        evidence_only_count = 0

        async for raw_rec in connector.fetch_all():
            obs_id = f"obs_{connector.source_system.value.lower()}_{raw_rec.record_id}"
            observation = SourceObservation(
                observation_id=obs_id,
                source_system=connector.source_system,
                ingestion_run_id=actual_run_id,
                source_record_id=raw_rec.record_id,
                raw_payload=raw_rec.payload,
                retrieved_at=capture_time,
                synthetic=connector.is_synthetic,
            )

            # Persist immutable evidence first (ADR 0001)
            await self._store.save(observation)

            # Derive from original stored observation to preserve immutable metadata on replay
            stored = await self._store.get_by_id(obs_id)
            effective_obs = stored if stored is not None else observation

            # Normalize effective observation
            norm_res = self._engine.normalize(effective_obs)
            triage_res: TriageResult | None = None

            if isinstance(norm_res, NormalizedObservation):
                normalized_count += 1
                triage_res = self._triage.evaluate(norm_res)
                if triage_res.disposition == IdentityDisposition.ELIGIBLE:
                    eligible_count += 1
                else:
                    evidence_only_count += 1
            elif isinstance(norm_res, RejectedObservation):
                rejected_count += 1

            processed_items.append(
                ProcessedObservation(
                    observation=effective_obs,
                    normalization_result=norm_res,
                    triage_result=triage_res,
                )
            )

        ingestion_run.mark_completed(count=len(processed_items))

        return IngestionBatchResult(
            run_id=actual_run_id,
            source_system=connector.source_system,
            total_ingested=len(processed_items),
            normalized_count=normalized_count,
            rejected_count=rejected_count,
            eligible_count=eligible_count,
            evidence_only_count=evidence_only_count,
            items=processed_items,
        )
