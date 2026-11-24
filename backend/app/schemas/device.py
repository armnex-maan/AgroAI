from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.common import Source, UTCDateTime


class SensorSpec(BaseModel):
    id: str | None = None
    type: str
    unit: str
    min_value: float | None = None
    max_value: float | None = None
    enabled: bool = True


class DeviceCreate(BaseModel):
    id: str
    name: str
    farm_id: str | None = None
    zone_id: str | None = None
    hardware_type: str = "esp32"
    firmware: str | None = None
    source: Source = "simulation"
    sensors: list[SensorSpec] = []
    config: dict | None = None


class DeviceOut(BaseModel):
    id: str
    name: str
    farm_id: str | None
    zone_id: str | None
    hardware_type: str
    firmware: str | None
    source: Source
    status: str
    last_seen: UTCDateTime | None
    provisioned: bool = False
    ip_address: str | None = None
    sensors: list[SensorSpec] = []

    model_config = ConfigDict(from_attributes=True)


class SensorConfigUpdate(BaseModel):
    enabled: bool | None = None
    min_value: float | None = None
    max_value: float | None = None
    calibration: dict | None = None
