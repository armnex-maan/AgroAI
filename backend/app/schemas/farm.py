from pydantic import BaseModel, ConfigDict


class FarmCreate(BaseModel):
    name: str
    owner: str = ""
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "UTC"


class FarmOut(BaseModel):
    id: str
    name: str
    owner: str
    latitude: float | None
    longitude: float | None
    timezone: str

    model_config = ConfigDict(from_attributes=True)


class FieldCreate(BaseModel):
    farm_id: str
    name: str
    area_ha: float | None = None
    soil_type: str | None = None
    polygon: dict | None = None


class FieldOut(BaseModel):
    id: str
    farm_id: str
    name: str
    area_ha: float | None
    soil_type: str | None
    polygon: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class ZoneCreate(BaseModel):
    field_id: str
    name: str
    polygon: dict | None = None


class ZoneOut(BaseModel):
    id: str
    field_id: str
    name: str
    polygon: dict | None = None

    model_config = ConfigDict(from_attributes=True)
