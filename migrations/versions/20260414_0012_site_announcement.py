"""Add site announcement fields

Revision ID: 20260414_0012
Revises: 20260414_0011
Create Date: 2026-04-14 00:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_0012"
down_revision = "20260414_0011"
branch_labels = None
depends_on = None

DEFAULT_TITLE = "赛事公告"
DEFAULT_BODY = (
    "欢迎来到 Asuri Major。\n"
    "1. 先下载规则、环境和 Baseline，确认本地训练与推理链路可用。\n"
    "2. 保存地图偏好后，再分别上传 T 方与 CT 方模型。\n"
    "3. 测试赛阶段会自动触发测试局；正式赛阶段由系统统一调度并持续更新排行榜。"
)


def upgrade() -> None:
    op.add_column(
        "site_config",
        sa.Column(
            "announcement_title",
            sa.String(length=160),
            nullable=False,
            server_default=DEFAULT_TITLE,
        ),
    )
    op.add_column(
        "site_config",
        sa.Column(
            "announcement_body",
            sa.Text(),
            nullable=False,
            server_default=DEFAULT_BODY,
        ),
    )
    op.add_column(
        "site_config",
        sa.Column("announcement_updated_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE site_config "
            "SET announcement_title = :title, "
            "announcement_body = :body, "
            "announcement_updated_at = updated_at "
            "WHERE announcement_updated_at IS NULL"
        ).bindparams(title=DEFAULT_TITLE, body=DEFAULT_BODY)
    )


def downgrade() -> None:
    op.drop_column("site_config", "announcement_updated_at")
    op.drop_column("site_config", "announcement_body")
    op.drop_column("site_config", "announcement_title")
