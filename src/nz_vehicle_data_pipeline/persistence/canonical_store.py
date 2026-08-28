"""PostgreSQL storage for atomic canonical vehicle revisions (ADR 0001, ADR 0004)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from nz_vehicle_data_pipeline.persistence.models import (
    CanonicalRevisionRow,
    VehicleRow,
)
from nz_vehicle_data_pipeline.reconciliation.confidence import (
    ConfidenceAssessment,
)
from nz_vehicle_data_pipeline.reconciliation.conflicts import FieldConflict
from nz_vehicle_data_pipeline.reconciliation.provenance import ProvenanceLink
from nz_vehicle_data_pipeline.reconciliation.result import ReconciliationResult


class CanonicalRevisionRecord(BaseModel):
    """Published canonical revision value object."""

    model_config = ConfigDict(frozen=True)

    revision_id: str = Field(description="Unique revision identifier")
    vin: str = Field(description="Canonical 17-character VIN")
    revision_number: int = Field(description="Monotonic revision number")
    material_hash: str = Field(description="SHA-256 fingerprint of canonical material")
    canonical_fields: dict[str, Any] = Field(description="Resolved canonical fields")
    field_provenance: dict[str, list[ProvenanceLink]] = Field(
        description="Lineage to all supporting source observations"
    )
    conflicts: list[FieldConflict] = Field(
        default_factory=list, description="Recorded field conflicts"
    )
    confidence: ConfidenceAssessment = Field(description="Confidence assessment")
    as_of: datetime = Field(description="Evaluation timestamp")
    published_at: datetime = Field(description="Database publication timestamp")


class PostgresCanonicalStore:
    """PostgreSQL repository handling row-locked atomic revision publications (ADR 0004)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, result: ReconciliationResult) -> tuple[CanonicalRevisionRecord, bool]:
        """Atomically lock vehicle, check material hash, and publish new revision if changed."""
        now = datetime.now(UTC)

        # Ensure vehicle row exists; handle concurrent initial inserts with on_conflict_do_nothing
        init_stmt = (
            pg_insert(VehicleRow)
            .values(
                vin=result.vin,
                created_at=now,
                current_revision_id=None,
                current_material_hash=None,
            )
            .on_conflict_do_nothing(index_elements=["vin"])
        )
        await self._session.execute(init_stmt)

        # Acquire exclusive row lock on the vehicle
        v_stmt = select(VehicleRow).where(VehicleRow.vin == result.vin).with_for_update()
        vehicle = (await self._session.execute(v_stmt)).scalar_one()

        mat_hash = result.material_hash()
        if vehicle.current_revision_id is not None:
            curr_stmt = select(CanonicalRevisionRow).where(
                CanonicalRevisionRow.revision_id == vehicle.current_revision_id
            )
            existing_row = (await self._session.execute(curr_stmt)).scalar_one()
            if vehicle.current_material_hash == mat_hash or existing_row.as_of > result.as_of:
                # Idempotent replay with identical hash OR incoming result is older
                return self._row_to_record(existing_row), False

        # Determine next revision number
        latest_rev_stmt = select(func.max(CanonicalRevisionRow.revision_number)).where(
            CanonicalRevisionRow.vin == result.vin
        )
        max_rev = (await self._session.execute(latest_rev_stmt)).scalar_one_or_none() or 0
        next_rev_num = max_rev + 1
        rev_id = f"rev_{result.vin}_{next_rev_num}"

        prov_json = {
            k: [p.model_dump(mode="json") for p in provs]
            for k, provs in result.field_provenance.items()
        }
        conf_json = [c.model_dump(mode="json") for c in result.conflicts]
        confidence_json = result.confidence.model_dump(mode="json")

        rev_row = CanonicalRevisionRow(
            revision_id=rev_id,
            vin=result.vin,
            revision_number=next_rev_num,
            material_hash=mat_hash,
            canonical_fields=result.canonical_fields,
            field_provenance=prov_json,
            conflicts=conf_json,
            confidence=confidence_json,
            as_of=result.as_of,
            published_at=now,
        )
        self._session.add(rev_row)

        vehicle.current_revision_id = rev_id
        vehicle.current_material_hash = mat_hash

        await self._session.commit()
        return self._row_to_record(rev_row), True

    async def get_current_revision(self, vin: str) -> CanonicalRevisionRecord | None:
        """Retrieve the current published revision for a VIN."""
        v_stmt = select(VehicleRow).where(VehicleRow.vin == vin)
        vehicle = (await self._session.execute(v_stmt)).scalar_one_or_none()
        if not vehicle or not vehicle.current_revision_id:
            return None

        r_stmt = select(CanonicalRevisionRow).where(
            CanonicalRevisionRow.revision_id == vehicle.current_revision_id
        )
        row = (await self._session.execute(r_stmt)).scalar_one_or_none()
        return self._row_to_record(row) if row else None

    async def get_revision_by_number(
        self, vin: str, revision_number: int
    ) -> CanonicalRevisionRecord | None:
        """Retrieve a specific revision by its monotonic number."""
        r_stmt = select(CanonicalRevisionRow).where(
            CanonicalRevisionRow.vin == vin,
            CanonicalRevisionRow.revision_number == revision_number,
        )
        row = (await self._session.execute(r_stmt)).scalar_one_or_none()
        return self._row_to_record(row) if row else None

    async def get_revision_history(
        self, vin: str, limit: int = 50, cursor: int | None = None
    ) -> list[CanonicalRevisionRecord]:
        """Retrieve revision history for a VIN in descending revision order."""
        stmt = select(CanonicalRevisionRow).where(CanonicalRevisionRow.vin == vin)
        if cursor is not None:
            stmt = stmt.where(CanonicalRevisionRow.revision_number < cursor)

        stmt = stmt.order_by(CanonicalRevisionRow.revision_number.desc()).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_record(r) for r in rows]

    async def list_current_vehicles(
        self, limit: int = 20, offset: int = 0
    ) -> tuple[list[CanonicalRevisionRecord], int]:
        """Retrieve paginated current canonical vehicle revisions sorted by VIN ascending."""
        count_stmt = (
            select(func.count())
            .select_from(VehicleRow)
            .where(VehicleRow.current_revision_id.is_not(None))
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        if total == 0:
            return [], 0

        stmt = (
            select(CanonicalRevisionRow)
            .join(
                VehicleRow,
                VehicleRow.current_revision_id == CanonicalRevisionRow.revision_id,
            )
            .order_by(CanonicalRevisionRow.vin.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_record(r) for r in rows], total

    def _row_to_record(self, row: CanonicalRevisionRow) -> CanonicalRevisionRecord:
        """Map database row to immutable domain record."""
        prov_dict = {
            k: [ProvenanceLink.model_validate(p) for p in provs]
            for k, provs in row.field_provenance.items()
        }
        conflicts_list = [FieldConflict.model_validate(c) for c in row.conflicts]
        confidence_obj = ConfidenceAssessment.model_validate(row.confidence)

        return CanonicalRevisionRecord(
            revision_id=row.revision_id,
            vin=row.vin,
            revision_number=row.revision_number,
            material_hash=row.material_hash,
            canonical_fields=row.canonical_fields,
            field_provenance=prov_dict,
            conflicts=conflicts_list,
            confidence=confidence_obj,
            as_of=row.as_of,
            published_at=row.published_at,
        )
