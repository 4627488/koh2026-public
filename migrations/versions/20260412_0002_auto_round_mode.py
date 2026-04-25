"""Add auto round scheduler config and round metadata

Revision ID: 20260412_0002
Revises: 20260410_0001
Create Date: 2026-04-12 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260412_0002"
down_revision = "20260410_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rounds",
        sa.Column(
            "created_mode",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "rounds",
        sa.Column("auto_slot_start", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_rounds_auto_slot_start",
        "rounds",
        ["auto_slot_start"],
        unique=True,
    )

    op.create_table(
        "auto_round_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("strategy_window_minutes", sa.Integer(), nullable=False),
        sa.Column("max_open_rounds", sa.Integer(), nullable=False),
        sa.Column("max_pending_matches", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auto_round_config")
    op.drop_index("ix_rounds_auto_slot_start", table_name="rounds")
    op.drop_column("rounds", "auto_slot_start")
    op.drop_column("rounds", "created_mode")
