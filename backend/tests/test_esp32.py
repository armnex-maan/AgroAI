import json
import time
from datetime import datetime, timezone

from app.core.security import compute_hmac


def _signed_post(client, body: dict, secret: str, ts: int | None = None):
    raw = json.dumps(body).encode()
    ts = str(ts or int(time.time()))
    return client.post("/api/v1/telemetry", content=raw, headers={
        "Content-Type": "application/json",
        "X-AGROAI-Timestamp": ts,
        "X-AGROAI-Signature": compute_hmac(raw, ts, secret),
    })


def _payload(device_id: str) -> dict:
    return {"device_id": device_id, "timestamp": datetime.now(timezone.utc).isoformat(), "source": "device",
            "sensors": {"soil_moisture": {"value": 23.5, "unit": "%"}}}


def test_provision_and_signed_telemetry(client):
    r = client.post("/api/v1/devices", json={"id": "ESP-T1", "name": "node", "source": "device",
                                             "sensors": [{"type": "soil_moisture", "unit": "%"}]})
    assert r.status_code == 201
    p = client.post("/api/v1/devices/ESP-T1/provision").json()
    secret = p["secret"]
    assert len(secret) == 64
    assert f'#define DEVICE_SECRET    "{secret}"' in p["config_h"]
    assert "#define USE_SOIL_MOISTURE   1" in p["config_h"]

    assert _signed_post(client, _payload("ESP-T1"), secret).status_code == 200
    assert _signed_post(client, _payload("ESP-T1"), "wrong-secret").status_code == 401
    old = int(time.time()) - 3600
    assert _signed_post(client, _payload("ESP-T1"), secret, ts=old).status_code == 401

    dev = client.get("/api/v1/devices/ESP-T1").json()
    assert dev["provisioned"] is True and dev["status"] == "online"

    # rotating the secret invalidates the old one
    new_secret = client.post("/api/v1/devices/ESP-T1/provision").json()["secret"]
    assert _signed_post(client, _payload("ESP-T1"), secret).status_code == 401
    assert _signed_post(client, _payload("ESP-T1"), new_secret).status_code == 200


def test_unknown_device_rejected(client):
    assert _signed_post(client, _payload("NOPE"), "x").status_code == 401


def test_simulated_device_cannot_be_provisioned(client):
    client.post("/api/v1/devices", json={"id": "SIM-T1", "name": "s", "source": "simulation", "sensors": []})
    assert client.post("/api/v1/devices/SIM-T1/provision").status_code == 400


def test_mqtt_bridge_handles_signed_envelope(client):
    from app.integrations import mqtt_bridge
    client.post("/api/v1/devices", json={"id": "ESP-M1", "name": "m", "source": "device", "sensors": []})
    secret = client.post("/api/v1/devices/ESP-M1/provision").json()["secret"]
    body = json.dumps(_payload("ESP-M1"))
    ts = str(int(time.time()))
    env = json.dumps({"ts": ts, "sig": compute_hmac(body.encode(), ts, secret), "body": body}).encode()
    assert mqtt_bridge.handle("agroai/farm/ESP-M1/telemetry", env) == 1


def test_node_v1_config_and_firmware_shaped_payload(client):
    r = client.post("/api/v1/devices", json={
        "id": "NODE-V1-T1", "name": "nodo", "source": "device", "hardware_type": "agroai-node-v1",
        "config": {"transport": "lora"},
        "sensors": [{"type": t, "unit": u} for t, u in [
            ("soil_moisture", "%"), ("air_temperature", "C"), ("air_humidity", "%"), ("light_intensity", "lx"),
            ("battery_voltage", "V"), ("irrigation_water", "L"), ("irrigation_time", "min")]]})
    assert r.status_code == 201
    p = client.post("/api/v1/devices/NODE-V1-T1/provision").json()
    cfg = p["config_h"]
    assert "AgroAI Node v1" in cfg
    assert "#define TRANSPORT        TRANSPORT_LORA" in cfg
    assert "#define USE_SHT40           1" in cfg and "#define USE_BH1750          1" in cfg
    assert "#define USE_FLOW_METER      1" in cfg and "#define VALVE_COUNT         1" in cfg
    assert "#define USE_DS18B20         0" in cfg
    assert "#define VALVE_AUTO          0" in cfg  # never waters by itself out of the box

    # Exactly the bytes buildTelemetryJson() (agroai_protocol.h) produces: String(value, 2), fixed order.
    ts = int(time.time())
    iso = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = ('{"device_id":"NODE-V1-T1","timestamp":"' + iso + '","source":"device","sensors":{'
           '"soil_moisture":{"value":27.40,"unit":"%"},"air_temperature":{"value":18.25,"unit":"C"},'
           '"air_humidity":{"value":63.10,"unit":"%"},"light_intensity":{"value":5120.83,"unit":"lx"},'
           '"battery_voltage":{"value":3.98,"unit":"V"},"irrigation_water":{"value":41.20,"unit":"L"},'
           '"irrigation_time":{"value":10.00,"unit":"min"}}}').encode()
    r = client.post("/api/v1/telemetry", content=raw, headers={
        "Content-Type": "application/json", "X-AGROAI-Timestamp": str(ts),
        "X-AGROAI-Signature": compute_hmac(raw, str(ts), p["secret"])})
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 7


def test_generic_esp32_config_unchanged(client):
    client.post("/api/v1/devices", json={"id": "ESP-G1", "name": "g", "source": "device",
                                         "sensors": [{"type": "air_temperature", "unit": "C"}]})
    cfg = client.post("/api/v1/devices/ESP-G1/provision").json()["config_h"]
    assert "#define USE_DHT22           1" in cfg and "TRANSPORT" not in cfg
