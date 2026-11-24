from enum import Enum


class Source(str, Enum):
    SIMULATION = "simulation"
    DEVICE = "device"
    MANUAL = "manual"
    FORECAST = "forecast"

    @classmethod
    def validate(cls, value: str) -> "Source":
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"invalid source {value!r}") from exc
