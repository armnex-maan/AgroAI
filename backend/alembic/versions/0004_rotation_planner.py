"""rotation planner: farm location, plot geometry, sections, detailed history, plans

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("region", "province"):
        op.add_column("farms", sa.Column(col, sa.String(64), nullable=True))
    op.add_column("farms", sa.Column("municipality", sa.String(128), nullable=True))
    op.add_column("fields", sa.Column("area_m2", sa.Float, nullable=True))
    op.add_column("fields", sa.Column("shape", sa.String(16), nullable=True))
    op.add_column("fields", sa.Column("width_m", sa.Float, nullable=True))
    op.add_column("fields", sa.Column("length_m", sa.Float, nullable=True))
    op.add_column("fields", sa.Column("orientation_deg", sa.Float, nullable=True))
    op.add_column("fields", sa.Column("exposure", sa.String(16), nullable=True))
    op.add_column("fields", sa.Column("outline", sa.JSON, nullable=True))
    op.add_column("fields", sa.Column("profile", sa.JSON, nullable=True))
    op.create_table(
        "plot_sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="bed"),
        sa.Column("x", sa.Float, nullable=False, server_default="0"),
        sa.Column("y", sa.Float, nullable=False, server_default="0"),
        sa.Column("w", sa.Float, nullable=False, server_default="1"),
        sa.Column("h", sa.Float, nullable=False, server_default="1"),
        sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column("crop_history", sa.Column("status", sa.String(16), nullable=False, server_default="crop"))
    op.add_column("crop_history", sa.Column("section_id", sa.String(36),
                                            sa.ForeignKey("plot_sections.id", ondelete="SET NULL"), nullable=True))
    op.add_column("crop_history", sa.Column("area_m2", sa.Float, nullable=True))
    op.add_column("crop_history", sa.Column("diseases", sa.String(255), nullable=True))
    op.add_column("crop_history", sa.Column("treatments", sa.String(255), nullable=True))
    op.create_table(
        "rotation_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("year", sa.Integer, nullable=False, index=True),
        sa.Column("assignments", sa.JSON, nullable=False),
        sa.Column("goals", sa.JSON, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="saved"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rotation_plans")
    for col in ("treatments", "diseases", "area_m2", "section_id", "status"):
        op.drop_column("crop_history", col)
    op.drop_table("plot_sections")
    for col in ("profile", "outline", "exposure", "orientation_deg", "length_m", "width_m", "shape", "area_m2"):
        op.drop_column("fields", col)
    for col in ("municipality", "province", "region"):
        op.drop_column("farms", col)
