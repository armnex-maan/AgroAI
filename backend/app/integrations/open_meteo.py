"""Open-Meteo: forecast + multi-year climate summary from the ERA5-based archive API.
Data: CC BY 4.0, https://open-meteo.com — forecast/reanalysis, never sensor measurements."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import httpx
from app.config import settings

HOURLY = ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m",
          "soil_temperature_0cm", "soil_moisture_0_to_1cm", "evapotranspiration"]
DAILY_CLIMATE = ["temperature_2m_mean", "temperature_2m_min", "temperature_2m_max",
                 "precipitation_sum", "et0_fao_evapotranspiration"]


async def fetch_forecast(lat: float, lon: float) -> dict:
    params = {"latitude": lat, "longitude": lon, "hourly": ",".join(HOURLY), "forecast_days": 3}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{settings.open_meteo_base_url}/forecast", params=params)
        r.raise_for_status()
        return r.json()


async def fetch_daily_climate(lat: float, lon: float, years: int = 5) -> dict:
    end_year = date.today().year - 1
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{end_year - years + 1}-01-01", "end_date": f"{end_year}-12-31",
        "daily": ",".join(DAILY_CLIMATE), "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(settings.open_meteo_archive_url, params=params)
        r.raise_for_status()
        return r.json()


def summarize_climate(raw: dict) -> dict:
    d = raw["daily"]
    days = d["time"]
    tmean, tmin, tmax = d["temperature_2m_mean"], d["temperature_2m_min"], d["temperature_2m_max"]
    prec, et0 = d["precipitation_sum"], d["et0_fao_evapotranspiration"]
    south = raw.get("latitude", 0) < 0

    monthly = defaultdict(lambda: {"t": [], "p": 0.0, "e": 0.0})
    years = sorted({x[:4] for x in days})
    per_year_min: dict[str, float] = {}
    frost_free: list[int] = []
    rows_by_year: dict[str, list[tuple[int, float | None]]] = defaultdict(list)

    for i, day in enumerate(days):
        y, m = day[:4], int(day[5:7])
        if tmean[i] is not None:
            monthly[m]["t"].append(tmean[i])
        monthly[m]["p"] += prec[i] or 0.0
        monthly[m]["e"] += et0[i] or 0.0
        if tmin[i] is not None:
            per_year_min[y] = min(per_year_min.get(y, 99.0), tmin[i])
        rows_by_year[y].append((i, tmin[i]))

    for y, rows in rows_by_year.items():
        # frost-free period: last frost before mid-year to first frost after it
        mid = len(rows) // 2
        last_spring = max((k for k, (_, t) in enumerate(rows[:mid]) if t is not None and t <= 0.0), default=-1)
        first_autumn = min((k for k, (_, t) in enumerate(rows[mid:], start=mid) if t is not None and t <= 0.0),
                           default=len(rows))
        frost_free.append(first_autumn - last_spring - 1)

    n_years = max(1, len(years))
    months = []
    for m in range(1, 13):
        v = monthly[m]
        months.append({
            "month": m,
            "t_mean": round(sum(v["t"]) / len(v["t"]), 1) if v["t"] else None,
            "precip_mm": round(v["p"] / n_years, 1),
            "et0_mm": round(v["e"] / n_years, 1),
        })

    def window(ms: list[int]) -> dict:
        sel = [months[m - 1] for m in ms]
        temps = [s["t_mean"] for s in sel if s["t_mean"] is not None]
        return {"months": ms,
                "t_mean": round(sum(temps) / len(temps), 1) if temps else None,
                "precip_mm": round(sum(s["precip_mm"] for s in sel), 0),
                "et0_mm": round(sum(s["et0_mm"] for s in sel), 0)}

    def gdd(base: float, ms: list[int]) -> float:
        total = 0.0
        for i, day in enumerate(days):
            if int(day[5:7]) in ms and tmean[i] is not None:
                total += max(0.0, tmean[i] - base)
        return round(total / n_years, 0)

    summer = [10, 11, 12, 1, 2, 3] if south else [4, 5, 6, 7, 8, 9]
    winter = [4, 5, 6, 7, 8, 9, 10, 11, 12] if south else [10, 11, 12, 1, 2, 3, 4, 5, 6]

    return {
        "source": "Open-Meteo historical weather API (ERA5 reanalysis), CC BY 4.0",
        "kind": "reanalysis",
        "period": f"{years[0]}–{years[-1]}" if years else None,
        "years": n_years,
        "hemisphere": "south" if south else "north",
        "annual": {
            "t_mean": round(sum(x for x in tmean if x is not None) / max(1, sum(1 for x in tmean if x is not None)), 1),
            "precip_mm": round(sum(p or 0 for p in prec) / n_years, 0),
            "et0_mm": round(sum(e or 0 for e in et0) / n_years, 0),
            "mean_annual_min_c": round(sum(per_year_min.values()) / max(1, len(per_year_min)), 1),
            "absolute_min_c": round(min(per_year_min.values()), 1) if per_year_min else None,
            "frost_free_days": int(sum(frost_free) / max(1, len(frost_free))),
        },
        "monthly": months,
        "seasons": {"summer": window(summer), "winter": window(winter)},
        "gdd": {
            "summer_base10": gdd(10.0, summer),
            "summer_base5": gdd(5.0, summer),
            "winter_base0": gdd(0.0, winter),
        },
    }
