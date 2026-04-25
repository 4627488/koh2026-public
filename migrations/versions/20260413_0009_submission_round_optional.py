"""Make Submission.round_id optional: drop FK, keep as soft reference

Revision ID: 20260413_0009
Revises: 20260413_0008
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260413_0009"
down_revision = "20260413_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_constraint("submissions_round_id_fkey", type_="foreignkey")
        batch_op.alter_column("round_id", nullable=True)


def downgrade() -> None:
    # Note: rows with round_id=NULL would fail the FK re-addition
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.alter_column("round_id", nullable=False)
        batch_op.create_foreign_key(
            "submissions_round_id_fkey", "rounds", ["round_id"], ["id"]
        )
