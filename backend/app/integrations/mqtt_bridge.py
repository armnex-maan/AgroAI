"""MQTT → AGROAI ingest bridge (optional; HTTP ingest works without it).

Topic:   agroai/<farm_id>/<device_id>/telemetry
Payload: {"ts": "<unix seconds>", "sig": "<hex hmac>", "body": "<telemetry JSON as a string>"}
The signature is HMAC-SHA256(device_secret, ts + "." + body), identical to the HTTP contract,
and the body is kept as a string so the exact signed bytes are preserved.

Run: python -m app.integrations.mqtt_bridge
"""
from __future__ import annotations

import json
import logging

from fastapi import HTTPException

from app.config import settings
from app.core.database import session_scope
from app.core.security import verify_device_hmac
from app.models import Device
from app.schemas.telemetry import TelemetryPayload
from app.services.sensor_service import SensorService

log = logging.getLogger("agroai.mqtt")
TOPIC = "agroai/+/+/telemetry"


def handle(topic: str, raw: bytes) -> int:
    parts = topic.split("/")
    if len(parts) != 4:
        raise ValueError(f"bad topic {topic}")
    device_id = parts[2]
    envelope = json.loads(raw)
    body: str = envelope["body"]
    with session_scope() as db:
        dev = db.get(Device, device_id)
        if dev is None:
            raise ValueError(f"unknown device {device_id}")
        verify_device_hmac(body.encode(), str(envelope["ts"]), envelope["sig"], dev.api_secret)
        payload = TelemetryPayload.model_validate_json(body)
        if payload.device_id != device_id:
            raise ValueError("device_id in body does not match topic")
        if payload.source != "device":
            raise ValueError("MQTT bridge accepts only source=device")
        return SensorService(db).ingest(payload)


def main() -> None:
    import paho.mqtt.client as mqtt

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    def on_connect(client, _userdata, _flags, rc, _props=None):
        log.info("connected to %s:%s rc=%s", settings.mqtt_broker_host, settings.mqtt_broker_port, rc)
        client.subscribe(TOPIC, qos=1)

    def on_message(_client, _userdata, msg):
        try:
            n = handle(msg.topic, msg.payload)
            log.info("%s: %d readings", msg.topic, n)
        except (ValueError, KeyError, HTTPException) as exc:
            log.warning("rejected %s: %s", msg.topic, getattr(exc, "detail", exc))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="agroai-bridge")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
