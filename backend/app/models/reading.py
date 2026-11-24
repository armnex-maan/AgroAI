from datetime import datetime
import uuid
from sqlalchemy import String, Float, ForeignKey, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    quality: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(32), index=True)

    __table_args__ = (
        Index("ix_sensor_readings_sensor_ts", "sensor_id", "ts"),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    kind: Mapped[str] = mapped_column(String(16))  # forecast | observation
    provider: Mapped[str] = mapped_column(String(64), default="open-meteo")
    payload: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(32), default="forecast")
