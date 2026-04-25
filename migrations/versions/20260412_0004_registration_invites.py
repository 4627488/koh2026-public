"""Add registration invite links

Revision ID: 20260412_0004
Revises: 20260412_0003
Create Date: 2026-04-12 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260412_0004"
down_revision = "20260412_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registration_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_registration_invites_token",
        "registration_invites",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_registration_invites_created_by_user_id",
        "registration_invites",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_registration_invites_created_by_user_id", table_name="registration_invites")
    op.drop_index("ix_registration_invites_token", table_name="registration_invites")
    op.drop_table("registration_invites")
