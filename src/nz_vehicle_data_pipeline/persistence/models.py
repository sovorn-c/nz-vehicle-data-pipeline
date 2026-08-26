"""SQLAlchemy ORM models for source evidence and canonical persistence (ADR 0001, ADR 0004)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nz_vehicle_data_pipeline.observation.models import SourceObservation, SourceSystem


class Base(DeclarativeBase):
    """Base declarative class for all pipeline tables."""


class SourceObservationRow(Base):
    """PostgreSQL table storing raw immutable source observations."""

    __tablename__ = "source_observations"

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ingestion_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def to_domain(self) -> SourceObservation:
        """Map database row to frozen domain value object."""
        return SourceObservation(
            observation_id=self.observation_id,
            source_system=SourceSystem(self.source_system),
            ingestion_run_id=self.ingestion_run_id,
            source_record_id=self.source_record_id,
            raw_payload=self.raw_payload,
            payload_hash_sha256=self.payload_hash_sha256,
            retrieved_at=self.retrieved_at,
            synthetic=self.synthetic,
        )

    @classmethod
    def from_domain(cls, domain: SourceObservation) -> "SourceObservationRow":
        """Map domain value object to database row."""
        return cls(
            observation_id=domain.observation_id,
            source_system=domain.source_system.value,
            ingestion_run_id=domain.ingestion_run_id,
            source_record_id=domain.source_record_id,
            raw_payload=domain.raw_payload,
            payload_hash_sha256=domain.payload_hash_sha256,
            retrieved_at=domain.retrieved_at,
            synthetic=domain.synthetic,
        )


class VehicleRow(Base):
    """PostgreSQL table tracking canonical vehicle identity root and current revision pointer."""

    __tablename__ = "vehicles"

    vin: Mapped[str] = mapped_column(String(17), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_material_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CanonicalRevisionRow(Base):
    """PostgreSQL table storing immutable published canonical vehicle revisions."""

    __tablename__ = "canonical_revisions"

    revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vin: Mapped[str] = mapped_column(
        String(17), ForeignKey("vehicles.vin"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    material_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    field_provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    conflicts: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("vin", "revision_number", name="uq_vin_revision_number"),)
