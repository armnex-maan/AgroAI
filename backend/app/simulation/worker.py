"""Standalone simulation worker.

Reads simulated devices from the DB and pushes telemetry via the ingestion service
on a fixed interval. Exits cleanly when SIMULATION_ENABLED=false.
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from app.config import settings
from app.core.database import session_scope
from app.models import Device, SimulationScenario
from app.integrations.hardware import DeviceDescriptor, SimulatedBackend
from app.simulation.engine import SimulationEngine
from app.services.sensor_service import SensorService
from app.schemas.telemetry import TelemetryPayload, SensorValue

log = logging.getLogger("agroai.sim")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

_running = True


def _stop(*_):
    global _running
    _running = False
    log.info("sim worker stopping")


def _active_scenario(db) -> str:
    row = db.query(SimulationScenario).filter(SimulationScenario.active.is_(True)).first()
    return row.name if row else settings.simulation_default_scenario


def loop() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    log.info("sim worker started; interval=%ss scenario=%s", settings.simulation_interval_seconds, settings.simulation_default_scenario)

    engine = SimulationEngine(scenario=settings.simulation_default_scenario)
    backend = SimulatedBackend(engine)

    while _running:
        if not settings.simulation_enabled:
            log.info("simulation disabled — sleeping")
            time.sleep(settings.simulation_interval_seconds)
            continue
        try:
            with session_scope() as db:
                engine.set_scenario(_active_scenario(db))
                sim_devices = db.query(Device).filter(Device.source == "simulation").all()
                if not sim_devices:
                    log.debug("no simulated devices")
                else:
                    svc = SensorService(db)
                    for d in sim_devices:
                        descriptor = DeviceDescriptor(
                            device_id=d.id, farm_id=d.farm_id, zone_id=d.zone_id,
                            hardware_type=d.hardware_type, source="simulation",
                            sensors=[{"type": s.type, "unit": s.unit} for s in d.sensors],
                        )
                        payload = backend.read(descriptor)
                        ts = datetime.now(timezone.utc)
                        parsed = TelemetryPayload(
                            device_id=payload["device_id"],
                            farm_id=payload["farm_id"],
                            zone_id=payload["zone_id"],
                            timestamp=ts,
                            source="simulation",
                            sensors={k: SensorValue(**v) for k, v in payload["sensors"].items()},
                        )
                        svc.ingest(parsed)
        except Exception:
            log.exception("sim tick failed")
        time.sleep(settings.simulation_interval_seconds)


if __name__ == "__main__":
    loop()
