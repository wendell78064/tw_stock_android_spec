"""personal data sync (portfolio, alert rules, saved screeners, settings)

Revision ID: 0014_personal_data_sync
Revises: 0013_account_sync_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_personal_data_sync"
down_revision: str | None = "0013_account_sync_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = ["portfolios", "portfolio_transactions", "alert_rules", "saved_screeners"]
    for table in tables:
        op.add_column(table, sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True)))
        op.create_foreign_key(
            f"{table}_user_fk", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        op.create_index(f"{table}_user_updated_idx", table, ["user_id", "updated_at"])

    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "key"),
    )
    op.create_index("user_settings_user_updated_idx", "user_settings", ["user_id", "updated_at"])


def downgrade() -> None:
    op.drop_table("user_settings")
    tables = ["saved_screeners", "alert_rules", "portfolio_transactions", "portfolios"]
    for table in tables:
        op.drop_index(f"{table}_user_updated_idx", table_name=table)
        op.drop_constraint(f"{table}_user_fk", table, type_="foreignkey")
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "version")
        op.drop_column(table, "user_id")
