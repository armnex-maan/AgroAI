"""Crop-rotation tables (independent from vision): soil conditions, soil problems, planned crops,
regulation sources and rotation rules. Every farm record hangs off a plot (fields.id)."""
from datetime import datetime
import uuid

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PlotConditions(Base):
    """Agronomic conditions of one plot, as answered in the questionnaire (one row per plot)."""
    __tablename__ = "plot_conditions"
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), primary_key=True)
    texture: Mapped[str | None] = mapped_column(String(16), nullable=True)      # sandy | clay | silty | mixed
    fertility: Mapped[str | None] = mapped_column(String(16), nullable=True)    # high | medium | low
    compaction: Mapped[str | None] = mapped_column(String(16), nullable=True)   # low | medium | high
    water: Mapped[str | None] = mapped_column(String(16), nullable=True)        # plenty | limited | none
    irrigation: Mapped[str | None] = mapped_column(String(16), nullable=True)   # drip | sprinkler | furrow | manual | none
    manure: Mapped[str | None] = mapped_column(String(16), nullable=True)       # yearly | sometimes | no
    cover: Mapped[str | None] = mapped_column(String(16), nullable=True)        # yes | maybe | no (cover crop possible)
    soil_state: Mapped[str | None] = mapped_column(String(16), nullable=True)   # derived: good | normal | tired | hard
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PlotProblem(Base):
    """A soil problem seen on a plot (nematodes, wilts, root rots...). 'other' keeps the farmer's words."""
    __tablename__ = "plot_problems"
    __table_args__ = (UniqueConstraint("field_id", "problem", name="uq_plot_problem"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    problem: Mapped[str] = mapped_column(String(32))          # rotation.PROBLEMS key, or "other"
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PlannedCrop(Base):
    """One crop of a saved rotation plan: which crop, in which section of which plot, in which year."""
    __tablename__ = "planned_crops"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plan_id: Mapped[str] = mapped_column(ForeignKey("rotation_plans.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[str | None] = mapped_column(ForeignKey("plot_sections.id", ondelete="SET NULL"), nullable=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    crop: Mapped[str] = mapped_column(String(64))
    family: Mapped[str | None] = mapped_column(String(32), nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(8), nullable=True)       # ok | care | no at save time
    manual: Mapped[bool] = mapped_column(Boolean, default=False)                # changed by hand by the farmer


class RegulationSource(Base):
    """A document actually read to encode rotation rules (regional guideline, EU regulation, FAO)."""
    __tablename__ = "regulation_sources"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)               # e.g. er_2023, eu_gaec7
    region: Mapped[str] = mapped_column(String(32))                             # region key, or "*" for the EU
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)            # none for undated web pages
    type: Mapped[str] = mapped_column(String(16))                               # obbligatoria | disciplinare | buona_pratica
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(512))


class RotationRule(Base):
    """A rotation rule with its source, region, year, crop and interval. Mirror of the rules encoded in
    app.ml.agronomy.rotation_rules (synced at start-up), so they can be listed and audited."""
    __tablename__ = "rotation_rules"
    __table_args__ = (UniqueConstraint("source_id", "crop", name="uq_rule_source_crop"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("regulation_sources.id", ondelete="CASCADE"), index=True)
    region: Mapped[str] = mapped_column(String(32), index=True)
    year: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(16))                              # obbligatoria | disciplinare
    crop: Mapped[str] = mapped_column(String(64), default="*")                  # crop key, "*" = general rule
    interval_years: Mapped[int | None] = mapped_column(Integer, nullable=True)  # years of other crops before return
    repeat: Mapped[str | None] = mapped_column(String(8), nullable=True)        # once | no | allowed
    text: Mapped[str] = mapped_column(Text)


class PlannerRevision(Base):
    """A saved version of the planner project: drawing (sections) and plans of every plot at save time.
    Lets the farmer go back to an earlier version; crop history is never part of it (it is a record, not a plan)."""
    __tablename__ = "planner_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(128))
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FarmFeature(Base):
    """A farm element drawn in the Visual Farm Planner: building, tank, well, road, irrigation main, hedge,
    orchard, vineyard, pond. Geometry is GeoJSON in WGS84 lon/lat (Point, LineString or Polygon)."""
    __tablename__ = "farm_features"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(128))
    geometry: Mapped[dict] = mapped_column(JSON)
    props: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
