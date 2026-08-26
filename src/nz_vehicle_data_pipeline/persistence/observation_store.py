"""PostgreSQL implementation of ObservationStore (ADR 0001, ADR 0004)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem
from nz_vehicle_data_pipeline.observation.store import (
    DuplicateObservationError,
    ObservationStore,
)
from nz_vehicle_data_pipeline.persistence.models import SourceObservationRow


class PostgresObservationStore(ObservationStore):
    """Asynchronous PostgreSQL repository for immutable source observations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, observation: SourceObservation) -> None:
        """Persist a source observation with immutable idempotency and collision checks."""
        stmt = select(SourceObservationRow).where(
            SourceObservationRow.observation_id == observation.observation_id
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            is_identical = (
                existing.payload_hash_sha256 == observation.payload_hash_sha256
                and existing.source_system == observation.source_system.value
                and existing.source_record_id == observation.source_record_id
                and existing.synthetic == observation.synthetic
            )
            if is_identical:
                return

            msg = (
                f"Observation '{observation.observation_id}' already exists "
                f"with different payload hash or metadata"
            )
            raise DuplicateObservationError(msg)

        row = SourceObservationRow.from_domain(observation)
        self._session.add(row)
        await self._session.commit()

    async def get_by_id(self, observation_id: str) -> SourceObservation | None:
        """Retrieve a single observation by its unique identifier."""
        stmt = select(SourceObservationRow).where(
            SourceObservationRow.observation_id == observation_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row.to_domain() if row else None

    async def get(self, observation_id: str) -> SourceObservation | None:
        """Retrieve a single observation by ID (alias for get_by_id)."""
        return await self.get_by_id(observation_id)

    async def get_by_run_id(self, ingestion_run_id: str) -> list[SourceObservation]:
        """Retrieve all observations from an ingestion run in deterministic order."""
        stmt = (
            select(SourceObservationRow)
            .where(SourceObservationRow.ingestion_run_id == ingestion_run_id)
            .order_by(
                SourceObservationRow.retrieved_at,
                SourceObservationRow.observation_id,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [r.to_domain() for r in rows]

    async def get_by_source_system(self, source_system: SourceSystem) -> list[SourceObservation]:
        """Retrieve all observations from a source system in deterministic order."""
        stmt = (
            select(SourceObservationRow)
            .where(SourceObservationRow.source_system == source_system.value)
            .order_by(
                SourceObservationRow.retrieved_at,
                SourceObservationRow.observation_id,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [r.to_domain() for r in rows]

    async def count(self) -> int:
        """Return total count of stored observations."""
        stmt = select(func.count(SourceObservationRow.observation_id))
        count = (await self._session.execute(stmt)).scalar_one()
        return int(count)
