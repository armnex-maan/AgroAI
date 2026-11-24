"""AGROAI Core — rules-based assessment. LLM layer wraps this, never replaces it."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models import Prediction, SensorReading, Sensor, Device
from app.schemas.common import iso_utc

DEFAULT_THRESHOLDS = {
    "soil_moisture": {"low": 20.0, "critical_low": 12.0, "unit": "%"},
    "air_temperature": {"high": 32.0, "critical_high": 38.0, "unit": "C"},
    "air_humidity": {"low": 25.0, "unit": "%"},
    "soil_ph": {"low": 5.5, "high": 8.0, "unit": "pH"},
    "soil_ec": {"high": 3.0, "unit": "mS/cm"},
}


def _latest_by_type(db: Session, zone_id: str | None) -> dict[str, SensorReading]:
    q = (
        select(SensorReading, Sensor, Device)
        .join(Sensor, SensorReading.sensor_id == Sensor.id)
        .join(Device, SensorReading.device_id == Device.id)
        .order_by(desc(SensorReading.ts))
    )
    if zone_id:
        q = q.where(Device.zone_id == zone_id)
    latest: dict[str, SensorReading] = {}
    for reading, sensor, _device in db.execute(q.limit(500)).all():
        if sensor.type not in latest:
            latest[sensor.type] = reading
    return latest


def assess_zone(db: Session, zone_id: str | None) -> dict:
    latest = _latest_by_type(db, zone_id)
    findings: list[str] = []
    recommendations: list[str] = []
    predictions: list[Prediction] = []
    sources_used: set[str] = set()

    def _pred(kind: str, severity: str, summary: str, supporting: list[dict], conf: float, verification: str) -> None:
        p = Prediction(
            zone_id=zone_id,
            ts=datetime.now(timezone.utc),
            kind=kind,
            severity=severity,
            summary=summary,
            supporting=supporting,
            confidence=conf,
            model="rules-v1",
            explanation=f"{summary}. Per verificare: {verification}.",
        )
        db.add(p)
        predictions.append(p)

    sm = latest.get("soil_moisture")
    if sm:
        sources_used.add(sm.source)
        thr = DEFAULT_THRESHOLDS["soil_moisture"]
        if sm.value <= thr["critical_low"]:
            findings.append(f"Il terreno è molto secco (umidità {sm.value:.1f}%).".replace(".", ",", 1))
            recommendations.append("Irriga la zona il prima possibile.")
            _pred("irrigation", "high", "Terreno molto secco",
                  [{"metric": "soil_moisture", "value": sm.value, "unit": sm.unit, "source": sm.source, "ts": iso_utc(sm.ts)}],
                  0.9, "controlla il sensore e guarda il terreno nella zona")
        elif sm.value <= thr["low"]:
            findings.append(f"Il terreno si sta asciugando (umidità {sm.value:.1f}%).".replace(".", ",", 1))
            recommendations.append("Programma un'irrigazione entro 24 ore.")
            _pred("irrigation", "medium", "Terreno asciutto",
                  [{"metric": "soil_moisture", "value": sm.value, "unit": sm.unit, "source": sm.source, "ts": iso_utc(sm.ts)}],
                  0.7, "guarda il terreno nella zona")

    at = latest.get("air_temperature")
    if at:
        sources_used.add(at.source)
        thr = DEFAULT_THRESHOLDS["air_temperature"]
        if at.value >= thr["critical_high"]:
            findings.append(f"Fa molto caldo ({at.value:.1f} °C).".replace(".", ",", 1))
            recommendations.append("Rischio stress da calore: valuta ombreggiatura o irrigazione serale.")
            _pred("heat_stress", "high", "Caldo eccessivo",
                  [{"metric": "air_temperature", "value": at.value, "unit": at.unit, "source": at.source, "ts": iso_utc(at.ts)}],
                  0.8, "confronta con le previsioni del tempo")
        elif at.value >= thr["high"]:
            findings.append(f"Fa caldo ({at.value:.1f} °C).".replace(".", ",", 1))

    ph = latest.get("soil_ph")
    if ph:
        sources_used.add(ph.source)
        thr = DEFAULT_THRESHOLDS["soil_ph"]
        if ph.value < thr["low"] or ph.value > thr["high"]:
            findings.append(f"Il pH del terreno è fuori dai valori normali ({ph.value:.1f}).".replace(".", ",", 1))
            recommendations.append("Ripeti la misura del pH per conferma.")
            _pred("soil_ph", "medium", "pH del terreno anomalo",
                  [{"metric": "soil_ph", "value": ph.value, "unit": ph.unit, "source": ph.source, "ts": iso_utc(ph.ts)}],
                  0.6, "preleva un campione di terreno per un'analisi di laboratorio")

    if not findings:
        status = "nominal"
        findings.append("Tutti i valori misurati sono nella norma.")
    else:
        high = any(p.severity == "high" for p in predictions)
        status = "attention" if high else "watch"

    db.flush()

    return {
        "zone_id": zone_id,
        "status": status,
        "findings": findings,
        "recommendations": recommendations,
        "predictions": predictions,
        "alerts": [],
        "sources": sorted(sources_used),
        "generated_at": datetime.now(timezone.utc),
    }
