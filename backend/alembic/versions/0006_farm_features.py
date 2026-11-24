"""farm features of the Visual Farm Planner (buildings, tanks, roads, mains, hedges, orchards, vineyards, ponds)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "farm_features",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("farm_id", sa.String(36), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("geometry", sa.JSON, nullable=False),
        sa.Column("props", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("farm_features")
