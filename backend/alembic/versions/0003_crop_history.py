"""crop history per field (crop rotation)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crop_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("crop", sa.String(64), nullable=False),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_crop_history_field_id", "crop_history", ["field_id"])
    op.create_index("ix_crop_history_year", "crop_history", ["year"])


def downgrade() -> None:
    op.drop_index("ix_crop_history_year", table_name="crop_history")
    op.drop_index("ix_crop_history_field_id", table_name="crop_history")
    op.drop_table("crop_history")
