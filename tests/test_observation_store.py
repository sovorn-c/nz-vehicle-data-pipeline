"""Tests for ObservationStore repository (e01s01 task t02)."""

from datetime import UTC, datetime
import pytest

from nz_vehicle_data_pipeline.observation.models import (
    SourceObservation,
    SourceSystem,
)
from nz_vehicle_data_pipeline.observation.store import (
    DuplicateObservationError,
    InMemoryObservationStore,
)


@pytest.fixture
def store() -> InMemoryObservationStore:
    return InMemoryObservationStore()


@pytest.fixture
def sample_observation() -> SourceObservation:
    return SourceObservation(
        observation_id="obs_nzta_001",
        source_system=SourceSystem.NZTA_MVR,
        ingestion_run_id="run_100",
        source_record_id="row_1",
        raw_payload="plate=ABC123&make=TOYOTA",
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )


async def test_store_and_get_observation(
    store: InMemoryObservationStore, sample_observation: SourceObservation
) -> None:
    """Verify observation can be stored and retrieved by ID."""
    await store.save(sample_observation)
    retrieved = await store.get_by_id("obs_nzta_001")
    assert retrieved is not None
    assert retrieved.observation_id == "obs_nzta_001"
    assert retrieved.raw_payload == "plate=ABC123&make=TOYOTA"


async def test_store_duplicate_id_with_different_payload_fails(
    store: InMemoryObservationStore, sample_observation: SourceObservation
) -> None:
    """Verify immutable evidence principle: cannot mutate stored observation payload."""
    await store.save(sample_observation)

    conflicting_obs = SourceObservation(
        observation_id="obs_nzta_001",
        source_system=SourceSystem.NZTA_MVR,
        ingestion_run_id="run_101",
        source_record_id="row_1",
        raw_payload="plate=ABC123&make=NISSAN",
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )

    with pytest.raises(DuplicateObservationError):
        await store.save(conflicting_obs)


async def test_store_idempotent_save_same_payload(
    store: InMemoryObservationStore, sample_observation: SourceObservation
) -> None:
    """Verify storing identical observation with same hash is idempotent."""
    await store.save(sample_observation)
    await store.save(sample_observation)
    assert await store.count() == 1


async def test_store_query_by_run_and_system(
    store: InMemoryObservationStore, sample_observation: SourceObservation
) -> None:
    """Verify querying observations by run ID and source system."""
    await store.save(sample_observation)

    obs2 = SourceObservation(
        observation_id="obs_nhtsa_001",
        source_system=SourceSystem.NHTSA_VPIC,
        ingestion_run_id="run_100",
        source_record_id="vpic_55",
        raw_payload='{"VIN": "1HGCR2F83HA000000"}',
        retrieved_at=datetime.now(UTC),
        synthetic=False,
    )
    await store.save(obs2)

    by_run = await store.get_by_run_id("run_100")
    assert len(by_run) == 2

    by_system = await store.get_by_source_system(SourceSystem.NZTA_MVR)
    assert len(by_system) == 1
    assert by_system[0].observation_id == "obs_nzta_001"
