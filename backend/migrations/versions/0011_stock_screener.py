"""add stock screener

Revision ID: 0011_stock_screener
Revises: 0010_industry_strength
Create Date: 2026-08-11 00:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011_stock_screener"
down_revision: str | None = "0010_industry_strength"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_screeners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expression", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_field", sa.String(length=50), nullable=False, server_default="code"),
        sa.Column("sort_direction", sa.String(length=10), nullable=False, server_default="ASC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("saved_screeners")
