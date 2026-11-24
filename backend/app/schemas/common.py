from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import AfterValidator, BaseModel

Source = Literal["simulation", "device", "manual", "forecast"]
Severity = Literal["info", "low", "medium", "high"]


def as_utc(v: datetime | None) -> datetime | None:
    """DB columns are naive UTC; make that explicit so clients don't read them as local time."""
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


def iso_utc(v: datetime) -> str:
    return as_utc(v).isoformat()


UTCDateTime = Annotated[datetime, AfterValidator(as_utc)]


class Health(BaseModel):
    status: str
    version: str
    simulation_enabled: bool
    ai_provider: str
