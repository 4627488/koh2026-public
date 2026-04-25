"""Add agent telemetry table and agent flag columns on users

Revision ID: 20260414_0014
Revises: 20260414_0013
Create Date: 2026-04-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_0014"
down_revision = "20260414_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_agent", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("agent_name", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("model_name", sa.String(128), nullable=True))

    op.create_table(
        "agent_telemetry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(256), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_telemetry_user_id", "agent_telemetry", ["user_id"])
    op.create_index("ix_agent_telemetry_recorded_at", "agent_telemetry", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_telemetry_recorded_at", table_name="agent_telemetry")
    op.drop_index("ix_agent_telemetry_user_id", table_name="agent_telemetry")
    op.drop_table("agent_telemetry")
    op.drop_column("users", "model_name")
    op.drop_column("users", "agent_name")
    op.drop_column("users", "is_agent")
