from datetime import datetime, timezone


def test_create_device_and_ingest_simulation(client):
    r = client.post("/api/v1/devices", json={
        "id": "TEST-SIM-1",
        "name": "Test sim",
        "source": "simulation",
        "sensors": [
            {"type": "soil_moisture", "unit": "%"},
            {"type": "air_temperature", "unit": "C"},
        ],
    })
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "TEST-SIM-1"

    r = client.post("/api/v1/telemetry", json={
        "device_id": "TEST-SIM-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "simulation",
        "sensors": {
            "soil_moisture": {"value": 27.5, "unit": "%", "quality": 1.0},
            "air_temperature": {"value": 22.0, "unit": "C", "quality": 1.0},
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 2

    r = client.get("/api/v1/telemetry/latest")
    assert r.status_code == 200
    rows = r.json()
    assert any(row["device_id"] == "TEST-SIM-1" for row in rows)


def test_telemetry_rejects_unknown_sensor_type(client):
    r = client.post("/api/v1/devices", json={"id": "TEST-SIM-2", "name": "x", "source": "simulation", "sensors": []})
    assert r.status_code == 201
    r = client.post("/api/v1/telemetry", json={
        "device_id": "TEST-SIM-2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "simulation",
        "sensors": {"radioactivity": {"value": 1.0, "unit": "mSv"}},
    })
    assert r.status_code == 422


def test_device_source_requires_hmac(client):
    r = client.post("/api/v1/devices", json={"id": "TEST-DEV-1", "name": "d", "source": "device", "sensors": []})
    assert r.status_code == 201
    r = client.post("/api/v1/telemetry", json={
        "device_id": "TEST-DEV-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "device",
        "sensors": {"air_temperature": {"value": 20.0, "unit": "C"}},
    })
    assert r.status_code == 401
