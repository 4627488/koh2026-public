"""Initial schema

Revision ID: 20260410_0001
Revises: None
Create Date: 2026-04-10 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260410_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("elo", sa.Float(), nullable=False, server_default=sa.text("1000")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("strategy_opens_at", sa.DateTime(), nullable=False),
        sa.Column("strategy_closes_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("token", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)

    op.create_table(
        "maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("map_idx", sa.Integer(), nullable=False),
        sa.Column("seed", sa.String(length=128), nullable=False),
        sa.Column("layout_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_maps_round_id", "maps", ["round_id"], unique=False)

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"], unique=False)
    op.create_index(
        "ix_submissions_round_id", "submissions", ["round_id"], unique=False
    )

    op.create_table(
        "bp_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("ban_priority", sa.JSON(), nullable=False),
        sa.Column("pick_priority", sa.JSON(), nullable=False),
        sa.Column("role_preference", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_bp_preferences_user_id", "bp_preferences", ["user_id"], unique=False
    )
    op.create_index(
        "ix_bp_preferences_round_id", "bp_preferences", ["round_id"], unique=False
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("map_id", sa.Integer(), sa.ForeignKey("maps.id"), nullable=False),
        sa.Column("team_a_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_b_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_matches_round_id", "matches", ["round_id"], unique=False)
    op.create_index("ix_matches_map_id", "matches", ["map_id"], unique=False)
    op.create_index("ix_matches_team_a_id", "matches", ["team_a_id"], unique=False)
    op.create_index("ix_matches_team_b_id", "matches", ["team_b_id"], unique=False)

    op.create_table(
        "replays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False
        ),
        sa.Column("map_id", sa.Integer(), sa.ForeignKey("maps.id"), nullable=False),
        sa.Column("frames_path", sa.Text(), nullable=False),
    )
    op.create_index("ix_replays_match_id", "replays", ["match_id"], unique=False)
    op.create_index("ix_replays_map_id", "replays", ["map_id"], unique=False)

    op.create_table(
        "elo_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column("elo_before", sa.Float(), nullable=False),
        sa.Column("elo_after", sa.Float(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
    )
    op.create_index("ix_elo_history_user_id", "elo_history", ["user_id"], unique=False)
    op.create_index(
        "ix_elo_history_round_id", "elo_history", ["round_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_elo_history_round_id", table_name="elo_history")
    op.drop_index("ix_elo_history_user_id", table_name="elo_history")
    op.drop_table("elo_history")

    op.drop_index("ix_replays_map_id", table_name="replays")
    op.drop_index("ix_replays_match_id", table_name="replays")
    op.drop_table("replays")

    op.drop_index("ix_matches_team_b_id", table_name="matches")
    op.drop_index("ix_matches_team_a_id", table_name="matches")
    op.drop_index("ix_matches_map_id", table_name="matches")
    op.drop_index("ix_matches_round_id", table_name="matches")
    op.drop_table("matches")

    op.drop_index("ix_bp_preferences_round_id", table_name="bp_preferences")
    op.drop_index("ix_bp_preferences_user_id", table_name="bp_preferences")
    op.drop_table("bp_preferences")

    op.drop_index("ix_submissions_round_id", table_name="submissions")
    op.drop_index("ix_submissions_user_id", table_name="submissions")
    op.drop_table("submissions")

    op.drop_index("ix_maps_round_id", table_name="maps")
    op.drop_table("maps")

    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_table("rounds")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
