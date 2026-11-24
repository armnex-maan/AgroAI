# API — v1

Base URL: `http://localhost:8000`. OpenAPI docs: `/docs`.

## Meta
- `GET /health` → `{status, version, simulation_enabled, ai_provider}`

## Telemetry
- `POST /api/v1/telemetry` — ingest. `source: device` requires HMAC headers.
- `GET  /api/v1/telemetry/latest` — latest per device.
- `GET  /api/v1/telemetry/history?sensor_id=&from_ts=&to_ts=&limit=`

### Telemetry payload
```json
{
  "device_id": "AGRO-ESP32-001",
  "farm_id": "FARM-001",
  "zone_id": "ZONE-A",
  "timestamp": "2026-11-19T10:30:00Z",
  "source": "device",
  "sensors": {
    "soil_moisture": {"value": 32.5, "unit": "%"},
    "air_temperature": {"value": 27.4, "unit": "C"}
  }
}
```

### Device HMAC
```
X-AGROAI-Timestamp: 1763553000
X-AGROAI-Signature: sha256_hex(secret, "<ts>." + body_bytes)
```

## Devices
- `GET/POST/DELETE /api/v1/devices[/{id}]`
- `POST /api/v1/devices/{id}/sensors` — add sensor
- `PATCH/DELETE /api/v1/sensors/{id}`

## Farms / Fields / Zones
- `GET/POST /api/v1/farms`
- `GET/POST /api/v1/fields?farm_id=`
- `GET/POST /api/v1/zones?field_id=`

## Simulation
- `GET  /api/v1/simulation/scenarios`
- `POST /api/v1/simulation/scenarios/activate` `{name}`

## Intelligence
- `GET  /api/v1/intelligence/assessment?zone_id=`

## Alerts
- `GET  /api/v1/alerts`
- `POST /api/v1/alerts/{id}/ack`

## Live
- `WS /ws/telemetry` — latest-per-device snapshot every ~3s.
