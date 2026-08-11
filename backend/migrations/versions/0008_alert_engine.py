"""Daily alert rules, events, and evaluation audit."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_alert_engine"
down_revision = "0007_watchlist_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("securities.id")),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "watchlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
        ),
        sa.Column("ma_period", sa.Integer),
        sa.Column("threshold_price", sa.Numeric(24, 8)),
        sa.Column("threshold_percent", sa.Numeric(10, 4)),
        sa.Column("consecutive_days", sa.Integer),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("cooldown_minutes", sa.Integer, nullable=False),
        sa.Column("daily_limit", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(security_id,portfolio_id,watchlist_id)=1", name="alert_rule_one_scope"
        ),
        sa.CheckConstraint(
            "ma_period IS NULL OR ma_period IN (5,10,20,60,120,240)", name="alert_rule_ma_period"
        ),
        sa.CheckConstraint(
            "threshold_price IS NULL OR threshold_price>0", name="alert_rule_price_positive"
        ),
        sa.CheckConstraint(
            "threshold_percent IS NULL OR threshold_percent>0 AND threshold_percent<=20",
            name="alert_rule_percent_range",
        ),
        sa.CheckConstraint(
            "consecutive_days IS NULL OR consecutive_days BETWEEN 2 AND 60",
            name="alert_rule_days_range",
        ),
        sa.CheckConstraint("cooldown_minutes>=0 AND daily_limit>0", name="alert_rule_limits"),
    )
    op.create_index("alert_rules_enabled_idx", "alert_rules", ["enabled"])
    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "alert_rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alert_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id"),
            nullable=False,
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("trigger_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("reference_value", sa.Numeric(24, 8), nullable=False),
        sa.Column("reference_type", sa.String(32), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column(
            "data_status",
            postgresql.ENUM(
                "FINAL",
                "PRELIMINARY",
                "PARTIAL",
                "STALE",
                "UNAVAILABLE",
                name="data_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("notification_eligible", sa.Boolean, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("alert_events_feed_idx", "alert_events", ["triggered_at", "id"])
    op.create_index("alert_events_rule_date_idx", "alert_events", ["alert_rule_id", "trade_date"])
    op.create_table(
        "alert_evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("target_trade_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rules_evaluated", sa.Integer, nullable=False),
        sa.Column("securities_evaluated", sa.Integer, nullable=False),
        sa.Column("events_created", sa.Integer, nullable=False),
        sa.Column("errors", sa.Integer, nullable=False),
        sa.Column("run_metadata", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("alert_evaluation_runs")
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
