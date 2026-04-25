"""Replace BP ban/pick with map pool preferences (ordered preference list)

Revision ID: 20260413_0006
Revises: 20260413_0005
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260413_0006"
down_revision = "20260413_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bp_preferences",
        sa.Column("map_preferences", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.drop_column("bp_preferences", "ban_priority")
    op.drop_column("bp_preferences", "pick_priority")
    op.drop_column("bp_preferences", "role_preference")


def downgrade() -> None:
    op.add_column("bp_preferences", sa.Column("ban_priority", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("bp_preferences", sa.Column("pick_priority", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("bp_preferences", sa.Column("role_preference", sa.JSON(), nullable=False, server_default="{}"))
    op.drop_column("bp_preferences", "map_preferences")
