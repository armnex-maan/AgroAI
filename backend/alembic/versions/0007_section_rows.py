"""rows of a plot section declared by the farmer (row spacing, plant spacing, row direction)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plot_sections", sa.Column("row_spacing_m", sa.Float, nullable=True))
    op.add_column("plot_sections", sa.Column("plant_spacing_m", sa.Float, nullable=True))
    op.add_column("plot_sections", sa.Column("row_dir", sa.String(1), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plot_sections") as b:
        b.drop_column("row_dir")
        b.drop_column("plant_spacing_m")
        b.drop_column("row_spacing_m")
