from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_device_hmac
from app.schemas.telemetry import TelemetryPayload, TelemetryAck, ReadingOut, LatestZoneTelemetry
from app.services.sensor_service import SensorService
from app.models import Sensor, Device

router = APIRouter()


@router.post("/telemetry", response_model=TelemetryAck)
async def ingest_telemetry(
    payload: TelemetryPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    if payload.source == "device":
        device = db.get(Device, payload.device_id)
        if device is None:
            raise HTTPException(401, "unknown device — provision it first")
        body = await request.body()
        ts = request.headers.get("x-agroai-timestamp", "")
        sig = request.headers.get("x-agroai-signature", "")
        verify_device_hmac(body, ts, sig, device.api_secret)
        if request.client:
            device.ip_address = request.client.host
    elif payload.source not in ("simulation", "manual", "forecast"):
        raise HTTPException(400, "invalid source")

    svc = SensorService(db)
    try:
        accepted = svc.ingest(payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return TelemetryAck(accepted=accepted, device_id=payload.device_id, timestamp=payload.timestamp)


@router.get("/telemetry/latest", response_model=list[LatestZoneTelemetry])
def latest(db: Session = Depends(get_db)):
    svc = SensorService(db)
    return svc.latest_per_device()


@router.get("/telemetry/history", response_model=list[ReadingOut])
def history(
    sensor_id: str = Query(...),
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    sensor = db.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(404, "sensor not found")
    rows = SensorService(db).history(sensor_id, from_ts, to_ts, limit)
    return [
        ReadingOut(
            ts=r.ts, sensor_id=r.sensor_id, sensor_type=sensor.type,
            value=r.value, unit=r.unit, quality=r.quality, source=r.source,
        ) for r in rows
    ]
