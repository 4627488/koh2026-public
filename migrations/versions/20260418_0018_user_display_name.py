"""Add display name to users

Revision ID: 20260418_0018
Revises: 20260417_0017
Create Date: 2026-04-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260418_0018"
down_revision = "20260417_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(length=128), nullable=True))

    op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("display_name", existing_type=sa.String(length=128), nullable=False)
        batch_op.create_index("ix_users_display_name", ["display_name"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_display_name")
        batch_op.drop_column("display_name")
