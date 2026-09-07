"""data quality anomalies tracking

Revision ID: 0015_data_quality_anomalies
Revises: 0014_personal_data_sync
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_data_quality_anomalies"
down_revision: str | None = "0014_personal_data_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_quality_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column("anomaly_type", sa.String(64), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.UniqueConstraint("dedupe_key", name="uq_data_quality_anomalies_dedupe_key"),
    )
    op.create_index("ix_data_quality_anomalies_status", "data_quality_anomalies", ["status"])
    op.create_index("ix_data_quality_anomalies_target_date", "data_quality_anomalies", ["target_date"])


def downgrade() -> None:
    op.drop_index("ix_data_quality_anomalies_target_date", table_name="data_quality_anomalies")
    op.drop_index("ix_data_quality_anomalies_status", table_name="data_quality_anomalies")
    op.drop_table("data_quality_anomalies")
