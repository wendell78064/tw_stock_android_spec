"""Industry and theme strength snapshots.

Revision ID: 0010_industry_strength
Revises: 0009_industry_theme_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_industry_strength"
down_revision = "0009_industry_theme_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_strength_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("industry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("industries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("window", sa.Integer(), nullable=False),
        sa.Column("equal_weight_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("market_cap_weighted_return", sa.Numeric(10, 4), nullable=True),
        sa.Column("total_members", sa.Integer(), nullable=False),
        sa.Column("valid_members", sa.Integer(), nullable=False),
        sa.Column("coverage_ratio", sa.Numeric(6, 4), nullable=False),
        sa.Column("advancers", sa.Integer(), nullable=False),
        sa.Column("decliners", sa.Integer(), nullable=False),
        sa.Column("unchanged", sa.Integer(), nullable=False),
        sa.Column("advance_ratio", sa.Numeric(6, 4), nullable=False),
        sa.Column("above_ma20_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("above_ma60_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("foreign_net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("investment_trust_net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("dealer_net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("margin_balance_change", sa.Numeric(18, 2), nullable=False),
        sa.Column("short_balance_change", sa.Numeric(18, 2), nullable=False),
        sa.Column("lending_balance_change", sa.Numeric(18, 2), nullable=True),
        sa.Column("turnover_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("turnover_share", sa.Numeric(8, 4), nullable=True),
        sa.Column("turnover_momentum", sa.Numeric(10, 4), nullable=True),
        sa.Column("momentum_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("breadth_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("technical_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("institutional_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("turnover_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("strength_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("component_coverage", sa.Numeric(6, 4), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("algorithm_version", sa.String(64), nullable=False, server_default="twml-industry-strength-v1"),
        sa.Column("data_status", sa.String(32), nullable=False, server_default="FINAL"),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(industry_id IS NOT NULL AND theme_id IS NULL) OR (industry_id IS NULL AND theme_id IS NOT NULL)",
            name="chk_taxonomy_strength_exactly_one_taxonomy",
        ),
    )
    op.create_index(
        "idx_taxonomy_strength_lookup",
        "taxonomy_strength_snapshots",
        ["trade_date", "window", "algorithm_version"],
    )
    op.create_index(
        "idx_taxonomy_strength_ind",
        "taxonomy_strength_snapshots",
        ["industry_id", "trade_date", "window"],
    )
    op.create_index(
        "idx_taxonomy_strength_theme",
        "taxonomy_strength_snapshots",
        ["theme_id", "trade_date", "window"],
    )


def downgrade() -> None:
    op.drop_index("idx_taxonomy_strength_theme", table_name="taxonomy_strength_snapshots")
    op.drop_index("idx_taxonomy_strength_ind", table_name="taxonomy_strength_snapshots")
    op.drop_index("idx_taxonomy_strength_lookup", table_name="taxonomy_strength_snapshots")
    op.drop_table("taxonomy_strength_snapshots")
