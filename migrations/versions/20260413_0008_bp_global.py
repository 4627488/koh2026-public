"""Make BPPreference round-agnostic: drop round_id FK, keep as nullable reference

Revision ID: 20260413_0008
Revises: 20260413_0007
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260413_0008"
down_revision = "20260413_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the FK constraint and make round_id nullable (kept as soft reference only)
    with op.batch_alter_table("bp_preferences") as batch_op:
        batch_op.drop_constraint("bp_preferences_round_id_fkey", type_="foreignkey")
        batch_op.alter_column("round_id", nullable=True)
    # Add index per user (if not already present from a prior partial run)
    op.execute("CREATE INDEX IF NOT EXISTS ix_bp_preferences_user_id ON bp_preferences (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bp_preferences_user_id")
    with op.batch_alter_table("bp_preferences") as batch_op:
        batch_op.alter_column("round_id", nullable=False)
        batch_op.create_foreign_key(
            "bp_preferences_round_id_fkey", "rounds", ["round_id"], ["id"]
        )
