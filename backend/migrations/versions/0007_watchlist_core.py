"""Watchlist groups, settings, and manual ordering."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_watchlist_core"
down_revision: str | None = "0006_portfolio_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="watchlists_name_nonempty"),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "watchlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("target_price", sa.Numeric(24, 8)),
        sa.Column("stop_price", sa.Numeric(24, 8)),
        sa.Column("add_price", sa.Numeric(24, 8)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("watchlist_id", "security_id", name="uq_watchlist_item_security"),
        sa.CheckConstraint(
            "target_price IS NULL OR target_price > 0", name="watchlist_target_positive"
        ),
        sa.CheckConstraint("stop_price IS NULL OR stop_price > 0", name="watchlist_stop_positive"),
        sa.CheckConstraint("add_price IS NULL OR add_price > 0", name="watchlist_add_positive"),
    )
    op.create_index("watchlist_items_order_idx", "watchlist_items", ["watchlist_id", "sort_order"])
    op.create_index("watchlist_items_security_idx", "watchlist_items", ["security_id"])
    op.execute(
        sa.text(
            "INSERT INTO watchlists (id,name,sort_order,created_at,updated_at) "
            "VALUES ('00000000-0000-0000-0000-000000000001','我的自選',0,now(),now())"
        )
    )


def downgrade() -> None:
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
