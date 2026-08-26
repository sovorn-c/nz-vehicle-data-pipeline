"""SQLAlchemy ORM models for source evidence and canonical persistence (ADR 0001, ADR 0004)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
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
