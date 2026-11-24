"""model registry + per-device secrets

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("api_secret", sa.String(128), nullable=True))
    op.add_column("devices", sa.Column("ip_address", sa.String(64), nullable=True))
    op.create_table(
        "ml_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("feature_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="trained"),
        sa.Column("labels", sa.JSON, nullable=False),
        sa.Column("class_counts", sa.JSON, nullable=False),
        sa.Column("n_samples", sa.Integer, server_default="0"),
        sa.Column("metrics", sa.JSON, nullable=False),
        sa.Column("dataset_manifest", sa.JSON, nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_ml_models_kind", "ml_models", ["kind"])
    op.create_index("ix_ml_models_status", "ml_models", ["status"])


def downgrade() -> None:
    op.drop_table("ml_models")
    op.drop_column("devices", "ip_address")
    op.drop_column("devices", "api_secret")
