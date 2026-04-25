"""Add phase to site_config and is_baseline to users

Revision ID: 20260414_0011
Revises: 20260413_0010
Create Date: 2026-04-14 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_0011"
down_revision = "20260413_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("site_config", sa.Column("phase", sa.String(16), nullable=False, server_default="competition"))


def downgrade() -> None:
    op.drop_column("users", "is_baseline")
    op.drop_column("site_config", "phase")
