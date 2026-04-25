"""Add file_hash to submissions for content-addressed model identity

Revision ID: 20260413_0007
Revises: 20260413_0006
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260413_0007"
down_revision = "20260413_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("file_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_submissions_file_hash", "submissions", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_submissions_file_hash", table_name="submissions")
    op.drop_column("submissions", "file_hash")
