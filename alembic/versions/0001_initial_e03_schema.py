"""Initial schema for source observations, vehicles, and canonical revisions (e03).

Revision ID: 0001
Revises:
Create Date: 2026-08-26 23:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Source observations
    op.create_table(
        "source_observations",
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("ingestion_run_id", sa.String(length=64), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("payload_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "synthetic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("observation_id"),
    )
    op.create_index(
        "ix_source_observations_source_system",
        "source_observations",
        ["source_system"],
    )
    op.create_index(
        "ix_source_observations_ingestion_run_id",
        "source_observations",
        ["ingestion_run_id"],
    )

    # 2. Vehicles
    op.create_table(
        "vehicles",
        sa.Column("vin", sa.String(length=17), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_revision_id", sa.String(length=64), nullable=True),
        sa.Column("current_material_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("vin"),
    )

    # 3. Canonical revisions
    op.create_table(
        "canonical_revisions",
        sa.Column("revision_id", sa.String(length=64), nullable=False),
        sa.Column("vin", sa.String(length=17), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("material_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_fields", sa.JSON(), nullable=False),
        sa.Column("field_provenance", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.JSON(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vin"], ["vehicles.vin"]),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint("vin", "revision_number", name="uq_vin_revision_number"),
    )
    op.create_index("ix_canonical_revisions_vin", "canonical_revisions", ["vin"])
    op.create_index(
        "ix_canonical_revisions_revision_number",
        "canonical_revisions",
        ["revision_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_revisions_revision_number",
        table_name="canonical_revisions",
    )
    op.drop_index("ix_canonical_revisions_vin", table_name="canonical_revisions")
    op.drop_table("canonical_revisions")
    op.drop_table("vehicles")
    op.drop_index(
        "ix_source_observations_ingestion_run_id",
        table_name="source_observations",
    )
    op.drop_index(
        "ix_source_observations_source_system",
        table_name="source_observations",
    )
    op.drop_table("source_observations")
