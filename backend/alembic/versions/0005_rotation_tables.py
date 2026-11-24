"""rotation tables: plot conditions, plot problems, planned crops, regulation sources, rotation rules

Moves the questionnaire answers kept in fields.profile and the plans kept in rotation_plans.assignments
into the new tables, and fills the regulation tables from the reviewed rules.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plot_conditions",
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), primary_key=True),
        *[sa.Column(c, sa.String(16), nullable=True) for c in
          ("texture", "fertility", "compaction", "water", "irrigation", "manure", "cover", "soil_state")],
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "plot_problems",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("problem", sa.String(32), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("field_id", "problem", name="uq_plot_problem"),
    )
    op.create_table(
        "planned_crops",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("rotation_plans.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("plot_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("year", sa.Integer, nullable=False, index=True),
        sa.Column("crop", sa.String(64), nullable=False),
        sa.Column("family", sa.String(32), nullable=True),
        sa.Column("area_m2", sa.Float, nullable=True),
        sa.Column("verdict", sa.String(8), nullable=True),
        sa.Column("manual", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "regulation_sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
    )
    op.create_table(
        "rotation_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(32), sa.ForeignKey("regulation_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("region", sa.String(32), nullable=False, index=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("crop", sa.String(64), nullable=False, server_default="*"),
        sa.Column("interval_years", sa.Integer, nullable=True),
        sa.Column("repeat", sa.String(8), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.UniqueConstraint("source_id", "crop", name="uq_rule_source_crop"),
    )
    # data: move JSON answers and plans into the tables, fill the rules
    from app.services import rotation_store
    db = Session(bind=op.get_bind())
    rotation_store.migrate_legacy(db)
    rotation_store.sync_rules(db)


def downgrade() -> None:
    # put the data back where revision 0004 keeps it before dropping the tables
    from app.models import Field, RotationPlan
    from app.services import rotation_store
    db = Session(bind=op.get_bind())
    for f in db.query(Field).all():
        prof = rotation_store.read_profile(db, f)
        if prof:
            f.profile = prof
    for p in db.query(RotationPlan).all():
        f = db.get(Field, p.field_id)
        saved = next((x for x in rotation_store.plans_out(db, f) if x["year"] == p.year), None) if f else None
        if saved and saved["assignments"]:
            p.assignments = saved["assignments"]
    db.flush()
    for t in ("rotation_rules", "regulation_sources", "planned_crops", "plot_problems", "plot_conditions"):
        op.drop_table(t)
