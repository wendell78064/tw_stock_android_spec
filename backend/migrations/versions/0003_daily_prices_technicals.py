"""Daily prices and deterministic technical snapshots.

Revision ID: 0003_daily_prices
Revises: 0002_security_master
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_daily_prices"
down_revision = "0002_security_master"
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
    op.create_table(
        "daily_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *[
            sa.Column(name, sa.Numeric(24, 8))
            for name in (
                "open",
                "high",
                "low",
                "close",
                "adjusted_open",
                "adjusted_high",
                "adjusted_low",
                "adjusted_close",
            )
        ],
        sa.Column("volume_shares", sa.BigInteger()),
        sa.Column("turnover_amount", sa.Numeric(28, 4)),
        sa.Column("source_code", sa.String(32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_status", data_status, nullable=False),
        sa.Column("source_revision", sa.String(64)),
        sa.Column("missing_reason", sa.String(128)),
        sa.Column(
            "ingestion_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.id")
        ),
        sa.UniqueConstraint("security_id", "trade_date", name="uq_daily_price_security_date"),
    )
    op.create_index(
        "daily_prices_security_date_idx",
        "daily_prices",
        ["security_id", sa.text("trade_date DESC")],
    )
    op.create_index("daily_prices_trade_date_idx", "daily_prices", ["trade_date"])
    op.create_table(
        "technical_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("price_basis", sa.String(16), nullable=False),
        *[
            sa.Column(name, sa.Numeric(28, 8))
            for name in (
                "ma5",
                "ma10",
                "ma20",
                "ma60",
                "ma120",
                "ma240",
                "ema12",
                "ema26",
                "rsi14",
                "macd",
                "macd_signal",
                "macd_histogram",
                "kd_k",
                "kd_d",
                "atr14",
                "obv",
                "bollinger_upper",
                "bollinger_middle",
                "bollinger_lower",
                "williams_r",
            )
        ],
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_status", data_status, nullable=False),
        sa.UniqueConstraint(
            "security_id", "trade_date", "price_basis", name="uq_technical_security_date_basis"
        ),
    )
    op.create_index(
        "technical_security_basis_date_idx",
        "technical_snapshots",
        ["security_id", "price_basis", sa.text("trade_date DESC")],
    )


def downgrade() -> None:
    op.drop_table("technical_snapshots")
    op.drop_table("daily_prices")
