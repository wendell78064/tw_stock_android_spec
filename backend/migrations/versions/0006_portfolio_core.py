"""Portfolio transaction ledger for moving-average accounting."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_portfolio_core"
down_revision = "0005_derivatives"
branch_labels = None
depends_on = None

DEFAULT_PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False, server_default="TWD"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "portfolio_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id"),
            nullable=False,
        ),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity_shares", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("lot_type", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_shares > 0", name="portfolio_transaction_quantity_positive"),
        sa.CheckConstraint("price > 0", name="portfolio_transaction_price_positive"),
        sa.CheckConstraint("fee >= 0", name="portfolio_transaction_fee_nonnegative"),
    )
    op.create_index(
        "portfolio_transactions_portfolio_executed_idx",
        "portfolio_transactions",
        ["portfolio_id", "executed_at"],
    )
    op.create_index(
        "portfolio_transactions_security_executed_idx",
        "portfolio_transactions",
        ["portfolio_id", "security_id", "executed_at"],
    )
    portfolios = sa.table(
        "portfolios",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("base_currency", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        portfolios.insert().values(
            id=DEFAULT_PORTFOLIO_ID,
            name="Default Portfolio",
            base_currency="TWD",
            is_default=True,
            created_at=sa.func.now(),
            updated_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    op.drop_index(
        "portfolio_transactions_security_executed_idx", table_name="portfolio_transactions"
    )
    op.drop_index(
        "portfolio_transactions_portfolio_executed_idx", table_name="portfolio_transactions"
    )
    op.drop_table("portfolio_transactions")
    op.drop_table("portfolios")
