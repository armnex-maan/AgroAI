from datetime import datetime
import uuid
from sqlalchemy import String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str] = mapped_column(String(255), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    # location used by crop rotation to pick the regional rules (never guessed from coordinates)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    fields: Mapped[list["Field"]] = relationship(back_populates="farm", cascade="all, delete-orphan")


class Field(Base):
    __tablename__ = "fields"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    polygon: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # plot description for the rotation planner (real metres, x to the east, y to the south)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    shape: Mapped[str | None] = mapped_column(String(16), nullable=True)        # rectangle | square | irregular
    width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    orientation_deg: Mapped[float | None] = mapped_column(Float, nullable=True)  # where north points, 0 = up
    exposure: Mapped[str | None] = mapped_column(String(16), nullable=True)      # full_sun | part_shade | shade
    outline: Mapped[list | None] = mapped_column(JSON, nullable=True)            # [[x, y], ...] in metres
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)            # soil, water, manure, problems...

    farm: Mapped[Farm] = relationship(back_populates="fields")
    zones: Mapped[list["Zone"]] = relationship(back_populates="field", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    polygon: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    field: Mapped[Field] = relationship(back_populates="zones")
    crops: Mapped[list["Crop"]] = relationship(back_populates="zone", cascade="all, delete-orphan")


class Crop(Base):
    __tablename__ = "crops"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"), index=True)
    species: Mapped[str] = mapped_column(String(128))
    variety: Mapped[str | None] = mapped_column(String(128), nullable=True)
    planted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    growth_stage: Mapped[str] = mapped_column(String(64), default="unknown")
    thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    zone: Mapped[Zone] = relationship(back_populates="crops")


class CropHistory(Base):
    """What was grown on a field in a given season: the basis for crop-rotation advice."""
    __tablename__ = "crop_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    crop: Mapped[str] = mapped_column(String(64))          # rotation crop key, or "rest"
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # detailed history (several crops per season are allowed): what, where, how much, what went wrong
    status: Mapped[str] = mapped_column(String(16), default="crop")  # crop | rest | cover | unknown
    section_id: Mapped[str | None] = mapped_column(ForeignKey("plot_sections.id", ondelete="SET NULL"), nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    diseases: Mapped[str | None] = mapped_column(String(255), nullable=True)
    treatments: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class PlotSection(Base):
    """A part of a plot drawn in the visual planner: a growing bed or a path, access, irrigation point,
    uncultivable zone. Geometry in metres inside the plot (x to the east, y to the south)."""
    __tablename__ = "plot_sections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="bed")   # bed | path | access | water | no_crop | shade
    x: Mapped[float] = mapped_column(Float, default=0)
    y: Mapped[float] = mapped_column(Float, default=0)
    w: Mapped[float] = mapped_column(Float, default=1)
    h: Mapped[float] = mapped_column(Float, default=1)
    sort: Mapped[int] = mapped_column(default=0)
    # rows as declared by the farmer (empty = not declared: the 3D view then draws an indicative layout)
    row_spacing_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    plant_spacing_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    row_dir: Mapped[str | None] = mapped_column(String(1), nullable=True)   # "x" rows run east-west, "y" north-south


class RotationPlan(Base):
    """A saved crop plan for one plot and one season: which crop goes in which section."""
    __tablename__ = "rotation_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    assignments: Mapped[list] = mapped_column(JSON, default=list)   # [{section_id, crop, area_m2, verdict, reasons}]
    goals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="saved")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
