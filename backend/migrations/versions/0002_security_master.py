"""Security master and ingestion metadata.

Revision ID: 0002_security_master
Revises: 0001_phase0
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_security_master"
down_revision = "0001_phase0"
branch_labels = None
depends_on = None

data_status = postgresql.ENUM(
    "LIVE",
    "DELAYED",
    "PRELIMINARY",
    "FINAL",
    "STALE",
    "PARTIAL",
    "UNAVAILABLE",
    name="data_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    postgresql.ENUM(
        "LIVE",
        "DELAYED",
        "PRELIMINARY",
        "FINAL",
        "STALE",
        "PARTIAL",
        "UNAVAILABLE",
        name="data_status",
    ).create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(128)),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ingestion_runs_provider_dataset_started_idx",
        "ingestion_runs",
        ["provider", "dataset", "started_at"],
    )
    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Taipei"),
    )
    op.create_table(
        "industries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("classification_source", sa.String(32), nullable=False),
        sa.UniqueConstraint("classification_source", "code", name="uq_industry_source_code"),
    )
    op.create_table(
        "securities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=False
        ),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("security_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("listing_date", sa.Date()),
        sa.Column("delisting_date", sa.Date()),
        sa.Column("source_code", sa.String(32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_status", data_status, nullable=False),
        sa.Column("source_revision", sa.String(64)),
        sa.Column(
            "ingestion_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.id")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("market_id", "code", name="uq_security_market_code"),
    )
    op.create_index("securities_code_idx", "securities", ["code"])
    op.create_index("securities_active_type_idx", "securities", ["is_active", "security_type"])
    op.execute("CREATE INDEX securities_name_trgm_idx ON securities USING gin (name gin_trgm_ops)")
    op.create_table(
        "security_industries",
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "industry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("industries.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "security_industries_primary_idx", "security_industries", ["security_id", "is_primary"]
    )


def downgrade() -> None:
    op.drop_table("security_industries")
    op.drop_table("securities")
    op.drop_table("industries")
    op.drop_table("markets")
    op.drop_table("ingestion_runs")
    postgresql.ENUM(name="data_status").drop(op.get_bind(), checkfirst=True)
