"""Replace user-based baseline with model-based Baseline table

Revision ID: 20260416_0015
Revises: 20260414_0014
Create Date: 2026-04-16

Data migration:
  - For every is_baseline=True user, find their latest attack + defense
    submissions and create a Baseline record (display_name = username).
  - Populate test_matches.baseline_id from the new baselines table.
  - Drop test_matches.baseline_user_id and users.is_baseline.
  - Make test_matches.team_b_id nullable (baseline is no longer a user).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "20260416_0015"
down_revision = "20260414_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create baselines table ──────────────────────────────
    op.create_table(
        "baselines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False, unique=True),
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_baselines_is_active", "baselines", ["is_active"])

    # ── 2. Migrate existing baseline users → baselines rows ────
    conn = op.get_bind()

    # Fetch all is_baseline=True active users
    bl_users = conn.execute(
        text(
            "SELECT id, username FROM users WHERE is_baseline = TRUE AND is_active = TRUE"
        )
    ).fetchall()

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")

    # Map old user_id → new baseline_id (for populating test_matches later)
    user_id_to_baseline_id: dict[int, int] = {}

    for user_id, username in bl_users:
        # Latest attack submission
        atk = conn.execute(
            text(
                "SELECT id FROM submissions "
                "WHERE user_id = :uid AND role = 'attack' "
                "ORDER BY uploaded_at DESC LIMIT 1"
            ),
            {"uid": user_id},
        ).fetchone()
        # Latest defense submission
        dfn = conn.execute(
            text(
                "SELECT id FROM submissions "
                "WHERE user_id = :uid AND role = 'defense' "
                "ORDER BY uploaded_at DESC LIMIT 1"
            ),
            {"uid": user_id},
        ).fetchone()
        if atk is None or dfn is None:
            # Baseline user without both submissions — skip migration of this user
            continue

        result = conn.execute(
            text(
                "INSERT INTO baselines "
                "(display_name, attack_submission_id, defense_submission_id, "
                " is_active, sort_order, created_at, updated_at) "
                "VALUES (:name, :atk, :dfn, TRUE, 0, :now, :now) "
                "RETURNING id"
            ),
            {"name": username, "atk": atk[0], "dfn": dfn[0], "now": now},
        )
        baseline_id = result.fetchone()[0]
        user_id_to_baseline_id[user_id] = baseline_id

    # ── 3. Add baseline_id to test_matches ────────────────────
    op.add_column(
        "test_matches",
        sa.Column(
            "baseline_id",
            sa.Integer(),
            sa.ForeignKey("baselines.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_test_matches_baseline_id", "test_matches", ["baseline_id"])

    # ── 4. Back-fill baseline_id on existing test_matches ─────
    for old_user_id, new_baseline_id in user_id_to_baseline_id.items():
        conn.execute(
            text(
                "UPDATE test_matches SET baseline_id = :bid "
                "WHERE baseline_user_id = :uid"
            ),
            {"bid": new_baseline_id, "uid": old_user_id},
        )

    # ── 5. Drop old baseline_user_id column ───────────────────
    # Drop FK constraint first (PostgreSQL names it automatically)
    op.drop_index("ix_test_matches_baseline_user_id", table_name="test_matches")
    with op.batch_alter_table("test_matches") as batch_op:
        batch_op.drop_column("baseline_user_id")

    # ── 6. Make team_b_id nullable ────────────────────────────
    with op.batch_alter_table("test_matches") as batch_op:
        batch_op.alter_column(
            "team_b_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    # ── 7. Drop is_baseline from users ────────────────────────
    op.drop_column("users", "is_baseline")


def downgrade() -> None:
    # Restore is_baseline column (all false)
    op.add_column(
        "users",
        sa.Column(
            "is_baseline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Restore team_b_id as NOT NULL (fill NULLs with 0 first as placeholder)
    conn = op.get_bind()
    conn.execute(text("UPDATE test_matches SET team_b_id = 0 WHERE team_b_id IS NULL"))
    with op.batch_alter_table("test_matches") as batch_op:
        batch_op.alter_column(
            "team_b_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    # Restore baseline_user_id (fill 0 as placeholder for old baseline_id rows)
    op.add_column(
        "test_matches",
        sa.Column(
            "baseline_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_test_matches_baseline_user_id", "test_matches", ["baseline_user_id"]
    )

    # Drop baseline_id
    op.drop_index("ix_test_matches_baseline_id", table_name="test_matches")
    with op.batch_alter_table("test_matches") as batch_op:
        batch_op.drop_column("baseline_id")

    # Drop baselines table
    op.drop_index("ix_baselines_is_active", table_name="baselines")
    op.drop_table("baselines")
