"""Derivatives products, contracts, positions, options and volatility."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_derivatives"
down_revision = "0004_market_spot"
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
        sa.Column("source_code", sa.String(48), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_status", status, nullable=False),
        sa.Column("source_revision", sa.String(64)),
        sa.Column(
            "ingestion_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.id")
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "futures_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("contract_multiplier", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("session_type", sa.String(24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "futures_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("futures_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("contract_code", sa.String(24), nullable=False),
        sa.Column("contract_month", sa.String(12), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("last_trade_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("product_id", "contract_code"),
    )
    op.create_table(
        "futures_daily_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("futures_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(24), nullable=False),
        *[
            sa.Column(name, sa.Numeric(24, 8))
            for name in (
                "open",
                "high",
                "low",
                "close",
                "settlement_price",
                "change",
                "change_percent",
            )
        ],
        sa.Column("volume", sa.BigInteger()),
        sa.Column("open_interest", sa.BigInteger()),
        *metadata_columns(),
        sa.UniqueConstraint("contract_id", "trade_date", "session_type"),
    )
    op.create_table(
        "institution_futures_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("futures_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("institution_type", sa.String(32), nullable=False),
        *[
            sa.Column(name, sa.BigInteger())
            for name in (
                "long_volume",
                "short_volume",
                "net_volume",
                "long_oi",
                "short_oi",
                "net_oi",
            )
        ],
        *[
            sa.Column(name, sa.Numeric(28, 4))
            for name in (
                "long_amount",
                "short_amount",
                "net_amount",
                "long_oi_amount",
                "short_oi_amount",
                "net_oi_amount",
            )
        ],
        *metadata_columns(),
        sa.UniqueConstraint("product_id", "trade_date", "institution_type"),
    )
    op.create_table(
        "trader_concentration",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("futures_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("contract_scope", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("top_n", sa.SmallInteger(), nullable=False),
        sa.Column("open_interest", sa.BigInteger()),
        sa.Column("market_open_interest", sa.BigInteger()),
        sa.Column("concentration_ratio", sa.Numeric(16, 8)),
        sa.Column("specific_institution_oi", sa.BigInteger()),
        *metadata_columns(),
        sa.UniqueConstraint("product_id", "trade_date", "contract_scope", "side", "top_n"),
    )
    op.create_table(
        "option_put_call_ratios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("put_volume", sa.BigInteger()),
        sa.Column("call_volume", sa.BigInteger()),
        sa.Column("volume_put_call_ratio", sa.Numeric(16, 8)),
        sa.Column("put_open_interest", sa.BigInteger()),
        sa.Column("call_open_interest", sa.BigInteger()),
        sa.Column("oi_put_call_ratio", sa.Numeric(16, 8)),
        *metadata_columns(),
        sa.UniqueConstraint("product_code", "trade_date"),
    )
    op.create_table(
        "option_strike_open_interest",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_code", sa.String(16), nullable=False),
        sa.Column("expiry", sa.String(12), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("option_type", sa.String(8), nullable=False),
        sa.Column("strike", sa.Numeric(24, 8), nullable=False),
        sa.Column("open_interest", sa.BigInteger()),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("settlement_price", sa.Numeric(24, 8)),
        *metadata_columns(),
        sa.UniqueConstraint("product_code", "expiry", "trade_date", "option_type", "strike"),
    )
    op.create_table(
        "volatility_indexes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(24), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        *[sa.Column(name, sa.Numeric(24, 8)) for name in ("open", "high", "low", "close")],
        *metadata_columns(),
        sa.UniqueConstraint("code", "trade_date"),
    )
    op.create_table(
        "continuous_futures_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("futures_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("roll_method", sa.String(24), nullable=False),
        sa.Column("source_contract", sa.String(24), nullable=False),
        sa.Column("roll_date", sa.Date()),
        sa.Column("adjustment_method", sa.String(24), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        *[sa.Column(name, sa.Numeric(24, 8)) for name in ("open", "high", "low", "close")],
        sa.Column("volume", sa.BigInteger()),
        sa.Column("open_interest", sa.BigInteger()),
        *metadata_columns(),
        sa.UniqueConstraint("product_id", "trade_date", "roll_method"),
    )
    for table, columns in (
        ("futures_contracts", ["product_id", "contract_month"]),
        ("futures_daily_prices", ["contract_id", "trade_date"]),
        ("institution_futures_positions", ["product_id", "trade_date"]),
        ("trader_concentration", ["product_id", "trade_date"]),
        ("option_put_call_ratios", ["product_code", "trade_date"]),
        ("option_strike_open_interest", ["product_code", "expiry", "trade_date"]),
        ("volatility_indexes", ["code", "trade_date"]),
        ("continuous_futures_points", ["product_id", "trade_date"]),
    ):
        op.create_index(f"{table}_lookup_idx", table, columns)


def downgrade() -> None:
    for table in (
        "continuous_futures_points",
        "volatility_indexes",
        "option_strike_open_interest",
        "option_put_call_ratios",
        "trader_concentration",
        "institution_futures_positions",
        "futures_daily_prices",
        "futures_contracts",
        "futures_products",
    ):
        op.drop_table(table)
