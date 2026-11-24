# AGROAI — Agricultural Intelligence Platform

Modular AI platform for agricultural monitoring: IoT sensor telemetry, bioacoustic analysis, computer vision, predictive analytics, and decision support. Designed to run **without hardware** via a realistic simulation engine, and ready for ESP32 / MQTT / RS485 / LoRa integration later.

## What works today

- **Acoustic Lab** — upload or generate sounds; waveform, spectrogram, FFT/PSD with comparison, band energy.
  Identification fuses YAMNet (521 AudioSet classes, Apache-2.0), optional BirdNET bird species
  (CC BY-NC-SA, off by default), a **farm model you train on your own labelled recordings** (e.g. confirmed
  mole activity) and an experimental underground-pattern detector. Every result says *probable / possible /
  unknown* with evidence and a verification step; thresholds are shown as uncalibrated.
- **Crop Advisor** — click a field on the satellite map: 5 years of climate (Open-Meteo ERA5) + modelled
  soil (ISRIC SoilGrids) → 19 crops ranked S1–N with the limiting factor, irrigation need, cost-saving
  tips and integrated rice systems (duck, fish, crab, crayfish) with **EU legal status** and sources.
- **ESP32** — add a node, provision a per-device secret, download `config.h`, flash
  [firmware/esp32_agroai](firmware/esp32_agroai/README.md). Telemetry and audio are HMAC-signed.
- Simulator, sensors, alerts, rules-based assessment, optional LLM explanations (Anthropic / Ollama / none).

Quick start without Docker: `.\scripts\dev-up.ps1` (see [docs/DEV.md](docs/DEV.md)).

## Status — Phase 0 + 1

Delivered now:

- Monorepo (backend + frontend + docker-compose)
- PostgreSQL + TimescaleDB schema, Alembic migrations
- FastAPI backend with HMAC-authenticated telemetry ingestion
- Pluggable hardware abstraction layer (Simulated + MQTT stub)
- Sensor simulator with 4 scenarios (healthy, water_stress, underground_activity, bird_activity)
- RQ + Redis worker for background tasks
- WebSocket live telemetry stream
- React + Vite + TS dashboard — Overview, Sensors, Simulation Lab fully wired; remaining pages scaffolded
- Provenance tagging: every record carries `source` (simulation / device / manual / forecast)
- Pytest suite

Later phases (acoustic worker, vision, prediction engine, MQTT ingest, deterrent devices) are documented in [docs/ROADMAP.md](docs/ROADMAP.md).

## Requirements

- Docker + Docker Compose (recommended)
- Or: Python 3.11+, Node 20+, PostgreSQL 15+ with TimescaleDB, Redis 7+

## Quick start (Docker)

```powershell
cp .env.example .env
docker compose up --build
```

Then:

- API: http://localhost:8000/docs
- Frontend: http://localhost:5173
- MQTT (future): localhost:1883

## Local dev (no Docker)

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev

# Worker (new terminal)
cd backend
.venv\Scripts\Activate.ps1
python -m app.simulation.worker
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/API.md](docs/API.md).

## Important disclaimers

- **Underground animal detection** is an experimental signal-analysis module. It never returns species IDs — only pattern evidence. There is no validated per-species frequency signature for European moles in peer-reviewed literature.
- **Acoustic deterrents** are simulated only. Physical sound emission is disabled by default and must be explicitly authorized. Ultrasonic bird deterrence is not supported by evidence.
- **Crop vision** results are preliminary visual assessments, not disease diagnoses.
- **BirdNET** (CC BY-NC-SA 4.0) is an optional module — disabled by default. YAMNet (Apache-2.0) is the default audio classifier.
