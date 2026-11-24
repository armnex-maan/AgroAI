"""ISRIC SoilGrids 2.0 point query (CC BY 4.0). 250 m modelled soil maps —
an estimate for the area, not a soil test of a specific field."""
from __future__ import annotations

import httpx
from app.config import settings

PROPS = ["phh2o", "clay", "sand", "silt", "soc", "nitrogen", "cec", "bdod"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
WEIGHTS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
# SoilGrids stores integers; divide by these factors to get conventional units.
CONVERSION = {
    "phh2o": (10, "pH"), "clay": (10, "%"), "sand": (10, "%"), "silt": (10, "%"),
    "soc": (10, "g/kg"), "nitrogen": (100, "g/kg"), "cec": (10, "cmol(c)/kg"), "bdod": (100, "kg/dm³"),
}


async def fetch(lat: float, lon: float) -> dict:
    params = [("lon", lon), ("lat", lat)]
    params += [("property", p) for p in PROPS]
    params += [("depth", d) for d in DEPTHS]
    params += [("value", "mean")]
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.get(settings.soilgrids_url, params=params)
        r.raise_for_status()
        return r.json()


def summarize(raw: dict) -> dict:
    out: dict[str, dict] = {}
    for layer in raw.get("properties", {}).get("layers", []):
        name = layer["name"]
        if name not in CONVERSION:
            continue
        factor, unit = CONVERSION[name]
        acc, wsum = 0.0, 0
        for d in layer.get("depths", []):
            v = d.get("values", {}).get("mean")
            w = WEIGHTS.get(d.get("label"))
            if v is None or w is None:
                continue
            acc += (v / factor) * w
            wsum += w
        if wsum:
            out[name] = {"value": round(acc / wsum, 2), "unit": unit, "depth": "0-30 cm weighted"}
    if not out:
        raise ValueError("nessun dato sul terreno in questo punto (acqua, zona urbana o fuori copertura)")
    clay, sand, silt = (out.get(k, {}).get("value") for k in ("clay", "sand", "silt"))
    texture = texture_class(sand, silt, clay) if None not in (clay, sand, silt) else None
    return {
        "source": "mappa ISRIC SoilGrids 2.0 (250 m)",
        "kind": "modelled",
        "properties": out,
        "texture": texture,
    }


def texture_class(sand: float, silt: float, clay: float) -> str:
    """USDA soil texture triangle."""
    total = sand + silt + clay
    if total <= 0:
        return "unknown"
    sand, silt, clay = (100 * v / total for v in (sand, silt, clay))
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    if clay >= 40 and sand <= 45 and silt < 40:
        return "clay"
    return "loam"


TEXTURE_IT = {
    "sand": "sabbioso", "loamy sand": "sabbioso-franco", "sandy loam": "franco-sabbioso", "loam": "franco (medio impasto)",
    "silt loam": "franco-limoso", "silt": "limoso", "sandy clay loam": "franco-sabbioso-argilloso",
    "clay loam": "franco-argilloso", "silty clay loam": "franco-limoso-argilloso", "sandy clay": "argilloso-sabbioso",
    "silty clay": "argilloso-limoso", "clay": "argilloso",
}
GROUP_IT = {"light": "leggero", "medium": "medio", "heavy": "pesante"}

TEXTURE_GROUP = {
    "sand": "light", "loamy sand": "light", "sandy loam": "light",
    "loam": "medium", "silt loam": "medium", "silt": "medium", "sandy clay loam": "medium",
    "clay loam": "heavy", "silty clay loam": "heavy", "sandy clay": "heavy",
    "silty clay": "heavy", "clay": "heavy",
}
