"""Hardware abstraction layer.

Two concrete device backends emit the same telemetry contract:
- SimulatedDevice: driven by the simulation engine.
- MQTTDeviceStub: Phase 4 — subscribes to `agroai/devices/<id>/telemetry`.

Both produce dicts conforming to app.schemas.telemetry.TelemetryPayload.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass
class DeviceDescriptor:
    device_id: str
    farm_id: str | None
    zone_id: str | None
    hardware_type: str
    source: str
    sensors: list[dict]


class DeviceBackend(ABC):
    @abstractmethod
    def read(self, descriptor: DeviceDescriptor) -> dict:
        """Return a telemetry payload dict."""


class SimulatedBackend(DeviceBackend):
    def __init__(self, engine):
        self.engine = engine

    def read(self, descriptor: DeviceDescriptor) -> dict:
        values = self.engine.sample(descriptor)
        return {
            "device_id": descriptor.device_id,
            "farm_id": descriptor.farm_id,
            "zone_id": descriptor.zone_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "simulation",
            "sensors": values,
        }


class MQTTDeviceStub(DeviceBackend):
    """Placeholder. Phase 4 will subscribe to MQTT topics and cache the latest
    payload per device id; read() returns that cache."""

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def read(self, descriptor: DeviceDescriptor) -> dict | None:
        return self._cache.get(descriptor.device_id)

    def on_message(self, device_id: str, payload: dict) -> None:
        self._cache[device_id] = payload


def iter_backends() -> Iterable[str]:
    return ("simulation", "mqtt")
