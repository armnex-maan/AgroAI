# AGROAI — Architecture

## Layers

```
Frontend (React+Vite+TS)  ──REST + WS──▶  FastAPI
                                             │
                     ┌───────────────────────┼─────────────────────────┐
                     ▼                       ▼                         ▼
             Sensor service          Intelligence service         Simulation worker
                     │                       │                         │
                     └───────── Postgres + TimescaleDB ◀────────────────┘
                                             │
                                           Redis (RQ)   MQTT broker (Phase 4)
```

## Provenance

Every row that carries measurement-like data has a `source` field drawn from
`Source` in `app.core.provenance`: `simulation | device | manual | forecast`.
This is the only safe way to mix synthetic and real data in the same tables.
The UI renders a badge per row.

## Hardware abstraction

`app.integrations.hardware` exposes `DeviceBackend` with two implementations:
`SimulatedBackend` and `MQTTDeviceStub`. Both produce dicts that conform to
`TelemetryPayload`, so the ingest path is identical.

ESP32 firmware will publish to `agroai/devices/<id>/telemetry` with:
- `X-AGROAI-Timestamp: <unix seconds>`
- `X-AGROAI-Signature: HMAC-SHA256(secret, "<ts>." + body)`

RS485 and LoRa gateways deliver the same payload via a translator service
that becomes a third `DeviceBackend` in Phase 4.

## Continuous learning scaffolding

Three tables carry the long-horizon signal:
- `acoustic_labels` — manual segment labels per recording.
- `verifications` — farmer feedback on any prediction/alert/detection.
- `simulation_scenarios` — versioned scenario configs.

A dataset export job (Phase 2) walks `audio_recordings` + `acoustic_labels` to
produce a versioned CSV/Parquet bundle. No automatic retraining — training is an
offline, human-curated step with documented validation requirements.

## Deliberate limits

- Underground-animal detection returns pattern evidence, never a species ID.
- Acoustic deterrents are simulated and gated behind an explicit authorization.
- Image analyses are visual assessments, not disease diagnoses.
- LLM output never introduces new measurements; it rewrites rules-engine output.
