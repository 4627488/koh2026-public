"""Add schedule window to auto round configuration

Revision ID: 20260417_0017
Revises: 20260417_0016
Create Date: 2026-04-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0017"
down_revision = "20260417_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("auto_round_config") as batch_op:
        batch_op.add_column(sa.Column("competition_starts_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("competition_ends_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("auto_round_config") as batch_op:
        batch_op.drop_column("competition_ends_at")
        batch_op.drop_column("competition_starts_at")
