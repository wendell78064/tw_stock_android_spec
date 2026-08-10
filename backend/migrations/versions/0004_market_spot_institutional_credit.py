"""Market spot, institutional, margin and securities lending datasets."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_market_spot"
down_revision = "0003_daily_prices"
branch_labels = None
depends_on = None

status = postgresql.ENUM(
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


def metadata_columns():
    return [
        sa.Column("source_code", sa.String(32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_status", status, nullable=False),
        sa.Column("source_revision", sa.String(64)),
        sa.Column(
            "ingestion_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.id")
        ),
    ]


def margin_columns():
    return [
        sa.Column(name, sa.BigInteger())
        for name in (
            "margin_buy",
            "margin_sell",
            "margin_cash_repayment",
            "margin_balance",
            "margin_balance_change",
            "short_sell",
            "short_cover",
            "short_stock_repayment",
            "short_balance",
            "short_balance_change",
        )
    ]


def lending_columns():
    return [
        sa.Column(name, sa.BigInteger())
        for name in ("lending_sell", "lending_return", "lending_balance", "lending_balance_change")
    ]


def upgrade() -> None:
    op.create_table(
        "market_indexes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("market_code", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("market_code", "code"),
    )
    op.create_table(
        "market_index_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "index_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("market_indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *[
            sa.Column(name, sa.Numeric(24, 8))
            for name in ("open", "high", "low", "close", "change")
        ],
        sa.Column("change_percent", sa.Numeric(16, 8)),
        sa.Column("turnover_amount", sa.Numeric(28, 4)),
        sa.Column("volume", sa.BigInteger()),
        *metadata_columns(),
        sa.UniqueConstraint("index_id", "trade_date"),
    )
    op.create_table(
        "market_breadth",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *[
            sa.Column(name, sa.Integer())
            for name in (
                "advancers",
                "decliners",
                "unchanged",
                "limit_up",
                "limit_down",
                "total_traded",
            )
        ],
        sa.Column("turnover_amount", sa.Numeric(28, 4)),
        *metadata_columns(),
        sa.UniqueConstraint("market_code", "trade_date"),
    )
    op.create_table(
        "market_institutional_spot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("institution_type", sa.String(32), nullable=False),
        sa.Column("dealer_subtype", sa.String(24), nullable=False, server_default="NONE"),
        *[
            sa.Column(name, sa.Numeric(28, 4))
            for name in ("buy_amount", "sell_amount", "net_amount")
        ],
        *metadata_columns(),
        sa.UniqueConstraint("market_code", "trade_date", "institution_type", "dealer_subtype"),
    )
    op.create_table(
        "institution_spot_trading",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("institution_type", sa.String(32), nullable=False),
        sa.Column("dealer_subtype", sa.String(24), nullable=False, server_default="NONE"),
        *[sa.Column(name, sa.BigInteger()) for name in ("buy_shares", "sell_shares", "net_shares")],
        *[
            sa.Column(name, sa.Numeric(28, 4))
            for name in ("buy_amount", "sell_amount", "net_amount")
        ],
        *metadata_columns(),
        sa.UniqueConstraint("security_id", "trade_date", "institution_type", "dealer_subtype"),
    )
    op.create_table(
        "market_margin_trading",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *margin_columns(),
        sa.Column("short_margin_ratio", sa.Numeric(16, 8)),
        *metadata_columns(),
        sa.UniqueConstraint("market_code", "trade_date"),
    )
    op.create_table(
        "margin_trading",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *margin_columns(),
        sa.Column("short_margin_ratio", sa.Numeric(16, 8)),
        sa.Column("margin_utilization", sa.Numeric(16, 8)),
        sa.Column("short_utilization", sa.Numeric(16, 8)),
        *metadata_columns(),
        sa.UniqueConstraint("security_id", "trade_date"),
    )
    op.create_table(
        "market_securities_lending",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *lending_columns(),
        *metadata_columns(),
        sa.UniqueConstraint("market_code", "trade_date"),
    )
    op.create_table(
        "securities_lending",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *lending_columns(),
        *metadata_columns(),
        sa.UniqueConstraint("security_id", "trade_date"),
    )
    for table, columns in (
        ("market_index_daily", ["index_id", "trade_date"]),
        ("market_breadth", ["market_code", "trade_date"]),
        ("market_institutional_spot", ["market_code", "trade_date"]),
        ("institution_spot_trading", ["security_id", "trade_date"]),
        ("market_margin_trading", ["market_code", "trade_date"]),
        ("margin_trading", ["security_id", "trade_date"]),
        ("market_securities_lending", ["market_code", "trade_date"]),
        ("securities_lending", ["security_id", "trade_date"]),
    ):
        op.create_index(f"{table}_lookup_idx", table, columns)


def downgrade() -> None:
    for table in (
        "securities_lending",
        "market_securities_lending",
        "margin_trading",
        "market_margin_trading",
        "institution_spot_trading",
        "market_institutional_spot",
        "market_breadth",
        "market_index_daily",
        "market_indexes",
    ):
        op.drop_table(table)
