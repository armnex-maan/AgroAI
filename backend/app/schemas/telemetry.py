from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import Source, UTCDateTime

SENSOR_TYPES = {
    "soil_moisture", "soil_temperature", "soil_ph", "soil_ec",
    "air_temperature", "air_humidity", "rainfall",
    "light_intensity", "wind_speed", "wind_direction", "leaf_wetness",
    "nitrogen", "phosphorus", "potassium",
    # AgroAI Node v1 (firmware/agroai_node_v1)
    "battery_voltage", "irrigation_water", "irrigation_time",
}


class SensorValue(BaseModel):
    value: float
    unit: str
    quality: float = 1.0


class TelemetryPayload(BaseModel):
    device_id: str
    farm_id: str | None = None
    zone_id: str | None = None
    timestamp: datetime
    source: Source = "device"
    sensors: dict[str, SensorValue]

    @field_validator("sensors")
    @classmethod
    def _check_types(cls, v: dict[str, SensorValue]) -> dict[str, SensorValue]:
        unknown = set(v) - SENSOR_TYPES
        if unknown:
            raise ValueError(f"unknown sensor types: {sorted(unknown)}")
        return v


class TelemetryAck(BaseModel):
    accepted: int
    device_id: str
    timestamp: datetime


class ReadingOut(BaseModel):
    ts: UTCDateTime
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    quality: float
    source: Source


class LatestZoneTelemetry(BaseModel):
    device_id: str
    zone_id: str | None
    source: Source
    status: str
    last_seen: UTCDateTime | None
    values: dict[str, SensorValue]
