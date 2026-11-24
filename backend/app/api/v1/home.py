"""Home screen summary for the mobile app: field values already interpreted, today's weather, one tip."""
from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml.agronomy import soil_water
from app.models import Alert, Crop, Farm, Field, Zone
from app.services.sensor_service import SensorService

router = APIRouter()
_WEATHER: dict[tuple, tuple[float, dict]] = {}
WEATHER_TTL = 30 * 60

# WMO weather codes used by Open-Meteo -> (Italian label, icon)
WMO = {0: ("Sereno", "sun"), 1: ("Poco nuvoloso", "sun"), 2: ("Parzialmente nuvoloso", "cloud-sun"),
       3: ("Coperto", "cloud"), 45: ("Nebbia", "cloud"), 48: ("Nebbia", "cloud"),
       51: ("Pioviggine", "rain"), 53: ("Pioviggine", "rain"), 55: ("Pioviggine", "rain"),
       61: ("Pioggia debole", "rain"), 63: ("Pioggia", "rain"), 65: ("Pioggia forte", "rain"),
       71: ("Neve", "snow"), 73: ("Neve", "snow"), 75: ("Neve", "snow"),
       80: ("Rovesci", "rain"), 81: ("Rovesci", "rain"), 82: ("Rovesci forti", "rain"),
       95: ("Temporale", "storm"), 96: ("Temporale con grandine", "storm"), 99: ("Temporale con grandine", "storm")}

SOIL_TONE = {"very_dry": ("Molto secco", "bad"), "dry": ("Secco", "warn"), "adequate": ("Ottimale", "ok"),
             "wet": ("Umido", "info"), "very_wet": ("Troppo bagnato", "warn"), "unknown": ("Da verificare", "neutral")}


async def weather_today(lat: float, lon: float) -> dict | None:
    key = (round(lat, 2), round(lon, 2))
    hit = _WEATHER.get(key)
    if hit and time.time() - hit[0] < WEATHER_TTL:
        return hit[1]
    params = {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
              "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation",
              "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"}
    d = None
    for _ in range(2):  # one retry: name resolution on rural connections can fail once
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.open-meteo.com/v1/forecast", params=params)
                r.raise_for_status()
                d = r.json()
                break
        except (httpx.HTTPError, ValueError):
            continue
    if d is None:
        return hit[1] if hit else None  # a stale forecast is better than none
    cur, day = d.get("current", {}), d.get("daily", {})
    label, icon = WMO.get(cur.get("weather_code"), ("—", "sun"))
    out = {"temperature": cur.get("temperature_2m"), "humidity": cur.get("relative_humidity_2m"),
           "wind_kmh": cur.get("wind_speed_10m"), "label": label, "icon": icon,
           "t_max": (day.get("temperature_2m_max") or [None])[0], "t_min": (day.get("temperature_2m_min") or [None])[0],
           "rain_mm": (day.get("precipitation_sum") or [None])[0],
           "rain_prob": (day.get("precipitation_probability_max") or [None])[0],
           "source": "Open-Meteo (previsione)"}
    _WEATHER[key] = (time.time(), out)
    return out


def _temp_status(t: float | None) -> tuple[str, str]:
    if t is None:
        return "—", "neutral"
    if t < 5:
        return "Freddo", "info"
    if t < 12:
        return "Fresco", "info"
    if t <= 30:
        return "Ideale", "ok"
    if t <= 35:
        return "Caldo", "warn"
    return "Troppo caldo", "bad"


def _ph_status(ph: float | None) -> tuple[str, str]:
    if ph is None:
        return "—", "neutral"
    if 6.0 <= ph <= 7.5:
        return "Buono", "ok"
    if 5.5 <= ph < 6.0 or 7.5 < ph <= 8.0:
        return "Da controllare", "warn"
    return "Fuori norma", "bad"


@router.get("/home")
async def home(db: Session = Depends(get_db)):
    farm = db.query(Farm).first()
    field = db.query(Field).filter(Field.farm_id == farm.id).first() if farm else None
    zone = db.query(Zone).filter(Zone.field_id == field.id).first() if field else None
    crop = db.query(Crop).filter(Crop.zone_id == zone.id).first() if zone else None

    rows = sorted(SensorService(db).latest_per_device(), key=lambda r: r["source"] != "device")
    values: dict = {}
    for r in rows:
        for t, v in r["values"].items():
            values.setdefault(t, {**v, "source": r["source"], "device_id": r["device_id"]})

    def metric(t: str):
        v = values.get(t)
        return None if v is None else {"value": v["value"], "unit": v["unit"], "source": v["source"],
                                       "device_id": v["device_id"]}

    soil = None
    if (sm := metric("soil_moisture")) is not None:
        interp = soil_water.interpret(sm["value"], sm["unit"] or "%", sm["source"],
                                      field.soil_type if field else None, crop.species if crop else None)
        label, tone = SOIL_TONE.get(interp["status"], SOIL_TONE["unknown"])
        soil = {**sm, "status": label, "tone": tone, "detail": interp["status_label"],
                "texture": interp.get("texture_label")}
    temp = metric("air_temperature")
    if temp:
        temp["status"], temp["tone"] = _temp_status(temp["value"])
    ph = metric("soil_ph")
    if ph:
        ph["status"], ph["tone"] = _ph_status(ph["value"])
    hum = metric("air_humidity")

    weather = await weather_today(farm.latitude, farm.longitude) if farm and farm.latitude is not None else None

    tip = _tip(soil, temp, weather)
    alerts = (db.query(Alert).filter(Alert.acknowledged.is_(False)).order_by(Alert.ts.desc()).limit(5).all())
    return {
        "farm": {"name": farm.name if farm else None, "owner": farm.owner if farm else None},
        "crop": crop.species if crop else None,
        "soil_moisture": soil, "air_temperature": temp, "soil_ph": ph, "air_humidity": hum,
        "weather": weather, "tip": tip,
        "alerts": [{"id": a.id, "ts": a.ts.isoformat() + ("" if a.ts.tzinfo else "Z"), "severity": a.severity,
                    "category": a.category, "message": a.message} for a in alerts],
        "alerts_open": db.query(Alert).filter(Alert.acknowledged.is_(False)).count(),
        "demo": any(v.get("source") == "simulation" for v in values.values()),
    }


def _tip(soil: dict | None, temp: dict | None, weather: dict | None) -> dict:
    """One short, data-driven tip for the home screen (rules, not the LLM: instant and verifiable)."""
    rain = (weather or {}).get("rain_mm") or 0
    prob = (weather or {}).get("rain_prob") or 0
    if soil and soil["tone"] in ("warn", "bad") and soil["status"] in ("Secco", "Molto secco"):
        if rain >= 5 or prob >= 70:
            return {"title": "Il terreno è secco, ma oggi è prevista pioggia.",
                    "text": f"Aspetta la pioggia ({rain:.0f} mm previsti) prima di irrigare.", "to": "/sensors"}
        return {"title": "Il terreno è secco.", "text": "Irriga al mattino presto e controlla i gocciolatori.",
                "to": "/sensors"}
    if soil and soil["status"] == "Troppo bagnato":
        return {"title": "Il terreno è molto bagnato.", "text": "Sospendi l'irrigazione e controlla il drenaggio.",
                "to": "/sensors"}
    if weather and (weather.get("t_max") or 0) >= 33:
        return {"title": "Oggi farà molto caldo.", "text": "Irriga presto al mattino e proteggi i frutti più esposti.",
                "to": "/sensors"}
    if weather and weather.get("humidity") and weather["humidity"] >= 85 and rain >= 2:
        return {"title": "Tempo umido: rischio di malattie fungine.",
                "text": "Controlla foglie e frutti nei prossimi giorni, soprattutto al mattino.", "to": "/vision"}
    if soil:
        phrase = {"Ottimale": "L'umidità del suolo è ideale.", "Umido": "Il terreno è umido: non serve irrigare."}
        return {"title": phrase.get(soil["status"], f"Terreno: {soil['status'].lower()}."),
                "text": "Mantieni il monitoraggio per i prossimi giorni.", "to": "/sensors"}
    return {"title": "Collega un sensore per consigli sul tuo campo.",
            "text": "Intanto puoi controllare le piante con una foto.", "to": "/vision"}
