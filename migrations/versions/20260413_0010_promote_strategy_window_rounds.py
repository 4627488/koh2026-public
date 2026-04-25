"""Promote any lingering strategy_window rounds to running

strategy_window is no longer a valid status; rounds are settlement snapshots
that go directly to running. Any rounds left in strategy_window were created
before the refactor and should be treated as running so the reconciler picks
them up.

Revision ID: 20260413_0010
Revises: 20260413_0009
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from alembic import op

revision = "20260413_0010"
down_revision = "20260413_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE rounds SET status = 'running' WHERE status = 'strategy_window'"
    )


def downgrade() -> None:
    # Cannot safely revert — we don't know which rounds were strategy_window
    pass
