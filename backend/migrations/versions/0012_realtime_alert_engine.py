"""add realtime alert engine mode

Revision ID: 0012_realtime_alert_engine
Revises: 0011_stock_screener
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_realtime_alert_engine"
down_revision: str | None = "0011_stock_screener"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_rules",
        sa.Column("evaluation_mode", sa.String(length=12), nullable=False, server_default="EOD"),
    )
    op.add_column(
        "alert_events",
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "alert_rules",
        sa.Column("session_scope", sa.String(length=16), nullable=False, server_default="REGULAR"),
    )


def downgrade() -> None:
    op.drop_column("alert_events", "event_metadata")
    op.drop_column("alert_rules", "session_scope")
    op.drop_column("alert_rules", "evaluation_mode")
