from datetime import datetime, timezone
from typing import Iterable
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models import Device, Sensor, SensorReading
from app.schemas.telemetry import TelemetryPayload, SensorValue

STALE_SECONDS = 600


class SensorService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_sensor(self, device: Device, sensor_type: str, unit: str) -> Sensor:
        for s in device.sensors:
            if s.type == sensor_type:
                if s.unit != unit:
                    raise ValueError(f"unit mismatch for {sensor_type}: stored={s.unit}, got={unit}")
                return s
        sensor = Sensor(device_id=device.id, type=sensor_type, unit=unit, enabled=True)
        self.db.add(sensor)
        self.db.flush()
        device.sensors.append(sensor)
        return sensor

    def ingest(self, payload: TelemetryPayload) -> int:
        device = self.db.get(Device, payload.device_id)
        if device is None:
            device = Device(
                id=payload.device_id,
                name=payload.device_id,
                farm_id=payload.farm_id,
                zone_id=payload.zone_id,
                source=payload.source,
                status="online",
                last_seen=payload.timestamp,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(device)
            self.db.flush()
        else:
            device.status = "online"
            device.last_seen = payload.timestamp

        accepted = 0
        for stype, sval in payload.sensors.items():
            sensor = self.ensure_sensor(device, stype, sval.unit)
            if not sensor.enabled:
                continue
            if sensor.min_value is not None and sval.value < sensor.min_value:
                continue
            if sensor.max_value is not None and sval.value > sensor.max_value:
                continue
            self.db.add(SensorReading(
                sensor_id=sensor.id,
                device_id=device.id,
                ts=payload.timestamp,
                value=sval.value,
                unit=sval.unit,
                quality=sval.quality,
                source=payload.source,
            ))
            accepted += 1
        self.db.commit()
        return accepted

    def latest_per_device(self) -> list[dict]:
        devices = self.db.execute(select(Device)).scalars().all()
        out = []
        now = datetime.now(timezone.utc)
        for d in devices:
            values: dict[str, dict] = {}
            for s in d.sensors:
                row = self.db.execute(
                    select(SensorReading).where(SensorReading.sensor_id == s.id).order_by(desc(SensorReading.ts)).limit(1)
                ).scalar_one_or_none()
                if row is not None:
                    values[s.type] = {"value": row.value, "unit": row.unit, "quality": row.quality}
            stale = False
            if d.last_seen is not None:
                last = d.last_seen if d.last_seen.tzinfo else d.last_seen.replace(tzinfo=timezone.utc)
                stale = (now - last).total_seconds() > STALE_SECONDS
            out.append({
                "device_id": d.id,
                "zone_id": d.zone_id,
                "source": d.source,
                "status": "stale" if stale else d.status,
                "last_seen": d.last_seen,
                "values": values,
            })
        return out

    def history(self, sensor_id: str, from_ts: datetime | None, to_ts: datetime | None, limit: int = 500) -> Iterable[SensorReading]:
        q = select(SensorReading).where(SensorReading.sensor_id == sensor_id)
        if from_ts:
            q = q.where(SensorReading.ts >= from_ts)
        if to_ts:
            q = q.where(SensorReading.ts <= to_ts)
        q = q.order_by(desc(SensorReading.ts)).limit(limit)
        return list(self.db.execute(q).scalars().all())
