"""Replace elo-based ranking with score-based settlement and add map difficulty

Revision ID: 20260417_0016
Revises: 20260416_0015
Create Date: 2026-04-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "20260417_0016"
down_revision = "20260416_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("score", sa.Float(), nullable=False, server_default="0")
        )
    conn = op.get_bind()
    conn.execute(text("UPDATE users SET score = COALESCE(elo, 0)"))
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("elo")

    with op.batch_alter_table("map_templates") as batch_op:
        batch_op.add_column(
            sa.Column("difficulty", sa.Float(), nullable=False, server_default="0.5")
        )
    with op.batch_alter_table("maps") as batch_op:
        batch_op.add_column(
            sa.Column("difficulty", sa.Float(), nullable=False, server_default="0.5")
        )

    op.create_table(
        "score_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("score_before", sa.Float(), nullable=False),
        sa.Column("score_after", sa.Float(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
    )
    op.create_index("ix_score_history_user_id", "score_history", ["user_id"])
    op.create_index("ix_score_history_round_id", "score_history", ["round_id"])

    conn.execute(
        text(
            "INSERT INTO score_history (id, user_id, round_id, score_before, score_after, delta) "
            "SELECT id, user_id, round_id, elo_before, elo_after, delta FROM elo_history"
        )
    )
    op.drop_table("elo_history")


def downgrade() -> None:
    op.create_table(
        "elo_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("elo_before", sa.Float(), nullable=False),
        sa.Column("elo_after", sa.Float(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
    )
    op.create_index("ix_elo_history_user_id", "elo_history", ["user_id"])
    op.create_index("ix_elo_history_round_id", "elo_history", ["round_id"])

    conn = op.get_bind()
    conn.execute(
        text(
            "INSERT INTO elo_history (id, user_id, round_id, elo_before, elo_after, delta) "
            "SELECT id, user_id, round_id, score_before, score_after, delta FROM score_history"
        )
    )
    op.drop_index("ix_score_history_user_id", table_name="score_history")
    op.drop_index("ix_score_history_round_id", table_name="score_history")
    op.drop_table("score_history")

    with op.batch_alter_table("maps") as batch_op:
        batch_op.drop_column("difficulty")
    with op.batch_alter_table("map_templates") as batch_op:
        batch_op.drop_column("difficulty")

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("elo", sa.Float(), nullable=False, server_default="1000")
        )
    conn.execute(text("UPDATE users SET elo = COALESCE(score, 0)"))
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("score")
