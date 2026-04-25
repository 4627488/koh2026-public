"""Add managed map templates and round map template references

Revision ID: 20260413_0005
Revises: 20260412_0004
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260413_0005"
down_revision = "20260412_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "map_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("layout_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_map_templates_slug", "map_templates", ["slug"], unique=True)
    op.create_index(
        "ix_map_templates_created_by_user_id",
        "map_templates",
        ["created_by_user_id"],
        unique=False,
    )

    op.add_column("maps", sa.Column("template_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_maps_template_id_map_templates",
        "maps",
        "map_templates",
        ["template_id"],
        ["id"],
    )
    op.create_index("ix_maps_template_id", "maps", ["template_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_maps_template_id", table_name="maps")
    op.drop_constraint("fk_maps_template_id_map_templates", "maps", type_="foreignkey")
    op.drop_column("maps", "template_id")

    op.drop_index(
        "ix_map_templates_created_by_user_id", table_name="map_templates"
    )
    op.drop_index("ix_map_templates_slug", table_name="map_templates")
    op.drop_table("map_templates")
