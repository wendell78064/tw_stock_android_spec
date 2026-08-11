"""Industry and theme taxonomy foundation.

Revision ID: 0009_industry_theme_foundation
Revises: 0008_alert_engine
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_industry_theme_foundation"
down_revision = "0008_alert_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("classification_type", sa.String(32), nullable=False, server_default="CUSTOM"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "security_themes",
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("themes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("security_themes_security_idx", "security_themes", ["security_id"])
    op.create_index("security_themes_theme_idx", "security_themes", ["theme_id"])


def downgrade() -> None:
    op.drop_index("security_themes_theme_idx", table_name="security_themes")
    op.drop_index("security_themes_security_idx", table_name="security_themes")
    op.drop_table("security_themes")
    op.drop_table("themes")
