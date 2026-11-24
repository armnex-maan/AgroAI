from datetime import datetime
import uuid
from sqlalchemy import String, ForeignKey, DateTime, JSON, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    farm_id: Mapped[str | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    hardware_type: Mapped[str] = mapped_column(String(64), default="esp32")
    firmware: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="simulation", index=True)
    status: Mapped[str] = mapped_column(String(32), default="offline", index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Per-device HMAC key, returned once at provisioning. Encrypt at rest in production.
    api_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sensors: Mapped[list["Sensor"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class Sensor(Base):
    __tablename__ = "sensors"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)  # soil_moisture, air_temperature, ...
    unit: Mapped[str] = mapped_column(String(16))
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    device: Mapped[Device] = relationship(back_populates="sensors")
