"""Add site config for registration toggle

Revision ID: 20260412_0003
Revises: 20260412_0002
Create Date: 2026-04-12 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260412_0003"
down_revision = "20260412_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allow_registration", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("site_config")
