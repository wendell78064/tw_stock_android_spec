"""account and watchlist sync foundation

Revision ID: 0013_account_sync_foundation
Revises: 0012_realtime_alert_engine
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_account_sync_foundation"
down_revision: str | None = "0012_realtime_alert_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("login_identifier", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("auth_sessions_user_idx", "auth_sessions", ["user_id"])
    op.create_table(
        "user_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_public_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(120)),
        sa.Column("platform", sa.String(24), nullable=False),
        sa.Column("app_version", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "device_public_id"),
    )
    op.create_index("user_devices_user_idx", "user_devices", ["user_id"])
    for table in ("watchlists", "watchlist_items"):
        op.add_column(table, sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True)))
        op.create_foreign_key(
            f"{table}_user_fk", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        op.create_index(f"{table}_user_updated_idx", table, ["user_id", "updated_at"])
    op.create_table(
        "sync_changes",
        sa.Column("sequence", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("sync_changes_user_cursor_idx", "sync_changes", ["user_id", "sequence"])
    op.create_table(
        "sync_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "operation_id"),
    )
    op.create_index("sync_operations_user_idx", "sync_operations", ["user_id"])


def downgrade() -> None:
    op.drop_table("sync_operations")
    op.drop_table("sync_changes")
    for table in ("watchlist_items", "watchlists"):
        op.drop_index(f"{table}_user_updated_idx", table_name=table)
        op.drop_constraint(f"{table}_user_fk", table, type_="foreignkey")
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "version")
        op.drop_column(table, "user_id")
    op.drop_table("user_devices")
    op.drop_table("auth_sessions")
    op.drop_table("users")
