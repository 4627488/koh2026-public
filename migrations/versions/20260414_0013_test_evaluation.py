"""Add test evaluation tables

Revision ID: 20260414_0013
Revises: 20260414_0012
Create Date: 2026-04-14 03:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_0013"
down_revision = "20260414_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_bundles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "attack_submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id"),
            nullable=False,
        ),
        sa.Column(
            "defense_submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id"),
            nullable=False,
        ),
        sa.Column("bp_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_submission_bundles_user_id", "submission_bundles", ["user_id"])
    op.create_index(
        "ix_submission_bundles_attack_submission_id",
        "submission_bundles",
        ["attack_submission_id"],
    )
    op.create_index(
        "ix_submission_bundles_defense_submission_id",
        "submission_bundles",
        ["defense_submission_id"],
    )

    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bundle_id", sa.Integer(), sa.ForeignKey("submission_bundles.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("baseline_pack_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_test_runs_bundle_id", "test_runs", ["bundle_id"])
    op.create_index("ix_test_runs_user_id", "test_runs", ["user_id"])

    op.create_table(
        "test_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("test_run_id", sa.Integer(), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("contestant_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("baseline_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "attack_submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id"),
            nullable=False,
        ),
        sa.Column(
            "defense_submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id"),
            nullable=False,
        ),
        sa.Column("map_template_id", sa.Integer(), sa.ForeignKey("map_templates.id"), nullable=True),
        sa.Column("map_idx", sa.Integer(), nullable=False),
        sa.Column("map_name", sa.String(length=128), nullable=False),
        sa.Column("layout_json", sa.JSON(), nullable=False),
        sa.Column("team_a_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_b_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("replay_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_test_matches_test_run_id", "test_matches", ["test_run_id"])
    op.create_index(
        "ix_test_matches_contestant_user_id",
        "test_matches",
        ["contestant_user_id"],
    )
    op.create_index("ix_test_matches_baseline_user_id", "test_matches", ["baseline_user_id"])
    op.create_index(
        "ix_test_matches_attack_submission_id",
        "test_matches",
        ["attack_submission_id"],
    )
    op.create_index(
        "ix_test_matches_defense_submission_id",
        "test_matches",
        ["defense_submission_id"],
    )
    op.create_index("ix_test_matches_map_template_id", "test_matches", ["map_template_id"])
    op.create_index("ix_test_matches_team_a_id", "test_matches", ["team_a_id"])
    op.create_index("ix_test_matches_team_b_id", "test_matches", ["team_b_id"])


def downgrade() -> None:
    op.drop_index("ix_test_matches_team_b_id", table_name="test_matches")
    op.drop_index("ix_test_matches_team_a_id", table_name="test_matches")
    op.drop_index("ix_test_matches_map_template_id", table_name="test_matches")
    op.drop_index("ix_test_matches_defense_submission_id", table_name="test_matches")
    op.drop_index("ix_test_matches_attack_submission_id", table_name="test_matches")
    op.drop_index("ix_test_matches_baseline_user_id", table_name="test_matches")
    op.drop_index("ix_test_matches_contestant_user_id", table_name="test_matches")
    op.drop_index("ix_test_matches_test_run_id", table_name="test_matches")
    op.drop_table("test_matches")

    op.drop_index("ix_test_runs_user_id", table_name="test_runs")
    op.drop_index("ix_test_runs_bundle_id", table_name="test_runs")
    op.drop_table("test_runs")

    op.drop_index("ix_submission_bundles_defense_submission_id", table_name="submission_bundles")
    op.drop_index("ix_submission_bundles_attack_submission_id", table_name="submission_bundles")
    op.drop_index("ix_submission_bundles_user_id", table_name="submission_bundles")
    op.drop_table("submission_bundles")
