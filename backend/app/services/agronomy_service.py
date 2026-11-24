"""Site assessment: location → climate + soil → crop ranking, cost tips, rice systems."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.integrations import open_meteo, soilgrids
from app.ml.agronomy import suitability, practices
from app.ml.agronomy.crops import KB_SOURCES
from app.models import Device, Sensor, SensorReading

_CACHE: dict[tuple, tuple[float, dict]] = {}
_TTL = 6 * 3600


async def _cached(key: tuple, fn):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    val = await fn()
    _CACHE[key] = (time.time(), val)
    return val


def _measured_ph(db: Session, farm_id: str | None) -> float | None:
    q = (db.query(SensorReading)
         .join(Sensor, SensorReading.sensor_id == Sensor.id)
         .join(Device, SensorReading.device_id == Device.id)
         .filter(Sensor.type == "soil_ph", SensorReading.source == "device"))
    if farm_id:
        q = q.filter(Device.farm_id == farm_id)
    rows = q.order_by(desc(SensorReading.ts)).limit(50).all()
    return round(sum(r.value for r in rows) / len(rows), 2) if rows else None


def _has_moisture_sensors(db: Session) -> bool:
    return (db.query(Sensor).join(Device, Sensor.device_id == Device.id)
            .filter(Sensor.type == "soil_moisture", Device.source == "device").first()) is not None


async def assess(db: Session, lat: float, lon: float, country_code: str | None,
                 farm_id: str | None = None, ph_override: float | None = None,
                 texture_override: str | None = None) -> dict:
    key = (round(lat, 3), round(lon, 3))
    warnings: list[str] = []

    raw_climate = await _cached(("climate",) + key, lambda: open_meteo.fetch_daily_climate(lat, lon))
    climate = open_meteo.summarize_climate(raw_climate)

    soil_info: dict = {"properties": {}, "texture": None, "source": None}
    try:
        raw_soil = await _cached(("soil",) + key, lambda: soilgrids.fetch(lat, lon))
        soil_info = soilgrids.summarize(raw_soil)
    except ValueError as exc:
        warnings.append(f"Mappa dei suoli: {exc}. Puoi inserire pH e tipo di terreno a mano.")
    except Exception:
        warnings.append("La mappa dei suoli non risponde in questo momento. Puoi inserire pH e tipo di terreno a mano.")

    props = soil_info.get("properties", {})
    measured_ph = _measured_ph(db, farm_id)
    if ph_override is not None:
        ph, ph_source = ph_override, "inserito da te"
    elif measured_ph is not None:
        ph, ph_source = measured_ph, "misurato dai sensori AGROAI"
    elif "phh2o" in props:
        ph, ph_source = props["phh2o"]["value"], "stima da mappa"
    else:
        ph, ph_source = None, None
    texture = texture_override or soil_info.get("texture")
    soil = {
        "ph": ph, "ph_source": ph_source,
        "texture": texture, "texture_source": "inserito da te" if texture_override else soil_info.get("source"),
        "soc_g_kg": props.get("soc", {}).get("value"),
        "properties": props,
        "source": soil_info.get("source"),
    }

    ranked = suitability.rank(climate, soil)
    rice = next((r for r in ranked if r["key"] == "rice"), None)
    return {
        "location": {"lat": lat, "lon": lon, "country": (country_code or "").upper() or None},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "climate": climate,
        "soil": soil,
        "crops": ranked,
        "cost_tips": practices.cost_tips(climate, soil, ranked, _has_moisture_sensors(db)),
        "rice": practices.rice_systems(country_code, rice),
        "warnings": warnings,
        "method": {
            "Come si calcola": "Ogni fattore (temperatura, calore, gelo, acqua, pH, terreno) riceve un punteggio da 0 "
                               "a 1; il voto finale pesa di più il fattore peggiore. Classi: S1 molto adatta (≥ 0,8), "
                               "S2 adatta (≥ 0,6), S3 poco adatta (≥ 0,4), N non adatta.",
            "Acqua": "Fabbisogno della coltura ≈ coefficiente colturale × evapotraspirazione; pioggia utile ≈ 80% della "
                     "pioggia (stima semplificata).",
            "Limiti": "È una prima selezione: non considera pendenza, salinità, drenaggio, mercato e diritti d'acqua. "
                      "Confrontati con un tecnico di zona e fai un'analisi del terreno.",
        },
        "sources": KB_SOURCES + [
            {"title": "Open-Meteo – dati climatici storici (rianalisi ERA5)",
             "url": "https://open-meteo.com/en/docs/historical-weather-api"},
            {"title": "ISRIC SoilGrids 2.0 – mappa mondiale dei suoli", "url": "https://soilgrids.org"},
        ],
    }
