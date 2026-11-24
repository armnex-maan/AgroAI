"""Live telemetry stream over WebSocket.

Subscribers receive the latest-per-device payload every ~3s. Not a replacement
for a proper pub/sub; good enough for Phase 1 dashboards.
"""
import asyncio
import json
from datetime import datetime

from app.schemas.common import iso_utc
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.database import SessionLocal
from app.services.sensor_service import SensorService

router = APIRouter()


def _serialize(rows: list[dict]) -> str:
    def default(o):
        if isinstance(o, datetime):
            return iso_utc(o)
        return str(o)
    return json.dumps(rows, default=default)


@router.websocket("/ws/telemetry")
async def telemetry_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            db = SessionLocal()
            try:
                rows = SensorService(db).latest_per_device()
            finally:
                db.close()
            await ws.send_text(_serialize(rows))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        return
