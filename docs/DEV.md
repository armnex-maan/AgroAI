# Dev guide

## First run

```powershell
Copy-Item .env.example .env
docker compose up --build
# in another terminal, seed data:
docker compose exec api python -m app.simulation.seed
```

Open:
- http://localhost:5173 — dashboard
- http://localhost:8000/docs — OpenAPI

## Tests

```powershell
docker compose exec api pytest -q
```

Tests run on an in-memory SQLite; TimescaleDB is only required at runtime for
the hypertable optimization.

## Simulating a device-signed telemetry POST

```powershell
$body = @'
{"device_id":"AGRO-DEV-1","timestamp":"2026-11-19T10:30:00Z","source":"device","sensors":{"soil_moisture":{"value":24.0,"unit":"%"}}}
'@
$ts = [int][double]::Parse((Get-Date -UFormat %s))
$key = "device-shared-secret-change-me"
$msg = "$ts.$body"
$hmac = New-Object System.Security.Cryptography.HMACSHA256
$hmac.Key = [Text.Encoding]::UTF8.GetBytes($key)
$sig = -join ($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($msg)) | ForEach-Object { $_.ToString('x2') })
curl.exe -X POST http://localhost:8000/api/v1/telemetry -H "Content-Type: application/json" -H "X-AGROAI-Timestamp: $ts" -H "X-AGROAI-Signature: $sig" --data $body
```
