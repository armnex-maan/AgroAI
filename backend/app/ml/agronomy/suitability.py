"""Deterministic crop suitability screening.

Each factor gets a 0..1 score. The overall score is sqrt(min × mean), so a
single limiting factor pulls the result down hard (Liebig-style) while the
others still count. Classes follow the FAO land-evaluation naming
(S1/S2/S3/N); the numeric cut-offs are this platform's convention.
"""
from __future__ import annotations

import math

from app.ml.agronomy.crops import CROPS, Crop
from app.integrations.soilgrids import TEXTURE_GROUP, TEXTURE_IT, GROUP_IT

EFFECTIVE_RAIN_FRACTION = 0.8


def _range_score(v: float, lo: float, hi: float, falloff: float) -> float:
    if lo <= v <= hi:
        return 1.0
    d = lo - v if v < lo else v - hi
    return max(0.0, 1.0 - d / falloff)


def _centred_score(v: float, lo: float, hi: float, falloff: float) -> float:
    """1.0 at the centre of the optimum, 0.85 at its edges, then linear fall-off.
    Separates 'fits' from 'fits best' so the ranking is informative."""
    if lo <= v <= hi:
        half = (hi - lo) / 2 or 1.0
        return 1.0 - 0.15 * ((v - (lo + hi) / 2) / half) ** 2
    return 0.85 * _range_score(v, lo, hi, falloff)


def _class(score: float) -> str:
    return "S1" if score >= 0.8 else "S2" if score >= 0.6 else "S3" if score >= 0.4 else "N"


def _combine(scores: list[float]) -> float:
    return round(math.sqrt(min(scores) * (sum(scores) / len(scores))), 3)


def _fmt(v: float, digits: int = 0) -> str:
    return f"{v:.{digits}f}".replace(".", ",")


def evaluate(crop: Crop, climate: dict, soil: dict) -> dict:
    seasons, gdd, annual = climate["seasons"], climate["gdd"], climate["annual"]
    season = seasons["winter"] if crop.season == "winter" else seasons["summer"]
    factors: list[dict] = []

    def add(key, label, value, requirement, score, note=None):
        factors.append({"key": key, "factor": label, "value": value, "requirement": requirement,
                        "score": round(score, 2), "note": note})

    t = season["t_mean"]
    s_t = _centred_score(t, *crop.t_opt, falloff=6.0)
    add("temperature", "Temperatura della stagione", f"{_fmt(t, 1)} °C",
        f"{_fmt(crop.t_opt[0])}–{_fmt(crop.t_opt[1])} °C", s_t)

    if crop.season == "winter":
        heat, base = gdd["winter_base0"], 0
    elif crop.base_temp == 10:
        heat, base = gdd["summer_base10"], 10
    else:
        heat, base = gdd["summer_base5"], 5
    s_h = min(1.0, heat / crop.gdd_min)
    add("heat", f"Calore accumulato (gradi-giorno base {base})", _fmt(heat), f"almeno {_fmt(crop.gdd_min)}", s_h)

    if crop.min_frost_free_days:
        ff = annual["frost_free_days"]
        s_f = min(1.0, ff / crop.min_frost_free_days)
        add("frost", "Giorni senza gelo", str(ff), f"almeno {crop.min_frost_free_days}", s_f)
    else:
        # A perennial is killed by the worst winter, an annual only loses one season.
        if crop.season == "perennial" and annual.get("absolute_min_c") is not None:
            amin, what = annual["absolute_min_c"], f"notte più fredda {climate.get('period', '')}"
        else:
            amin, what = annual["mean_annual_min_c"], "minima media annuale"
        s_f = 1.0 if amin >= crop.frost_min_c else max(0.0, 1.0 - (crop.frost_min_c - amin) / 5.0)
        add("frost", "Freddo invernale", f"{_fmt(amin, 1)} °C ({what})", f"non sotto {_fmt(crop.frost_min_c)} °C", s_f)

    et0 = season["et0_mm"]
    need = crop.kc * et0
    rain_mm = annual["precip_mm"] if crop.season == "perennial" else season["precip_mm"]
    eff_rain = EFFECTIVE_RAIN_FRACTION * rain_mm
    deficit = max(0.0, need - eff_rain)
    s_w = 0.15 if crop.needs_flooding else min(1.0, eff_rain / max(1.0, need))
    add("water", "Acqua dalla pioggia (senza irrigare)", f"{_fmt(eff_rain)} mm di pioggia utile",
        f"circa {_fmt(need)} mm", s_w, "serve sommersione/irrigazione" if crop.needs_flooding else None)

    soil_scores = []
    ph = soil.get("ph")
    if ph is not None:
        s_ph = _centred_score(ph, *crop.ph, falloff=1.5)
        soil_scores.append(s_ph)
        add("ph", "pH del terreno", f"{_fmt(ph, 1)} ({soil.get('ph_source')})",
            f"{_fmt(crop.ph[0], 1)}–{_fmt(crop.ph[1], 1)}", s_ph)
    texture = soil.get("texture")
    if texture:
        group = TEXTURE_GROUP.get(texture, "medium")
        s_tx = crop.texture.get(group, 0.8)
        soil_scores.append(s_tx)
        add("texture", "Tipo di terreno", f"{TEXTURE_IT.get(texture, texture)} ({GROUP_IT[group]})",
            ", ".join(f"{GROUP_IT[k]} {round(v * 100)}%" for k, v in crop.texture.items()), s_tx)

    base_scores = [s_t, s_h, s_f] + soil_scores
    rainfed = _combine(base_scores + [s_w])
    irrigated = _combine(base_scores)
    limiting = min((f for f in factors if f["key"] != "water"), key=lambda f: f["score"])
    return {
        "key": crop.key, "name": crop.name, "season": crop.season,
        "score_irrigated": irrigated, "class_irrigated": _class(irrigated),
        "score_rainfed": rainfed, "class_rainfed": _class(rainfed),
        "irrigation_need_mm": round(deficit if not crop.needs_flooding else need, 0),
        "fao_water_range_mm": list(crop.water_mm),
        "limiting_factor": limiting["factor"] if limiting["score"] < 0.8 else None,
        "limiting_key": limiting["key"] if limiting["score"] < 0.8 else None,
        "factors": factors,
        "legume": crop.legume,
        "family": crop.family,
        "notes": crop.notes,
    }


def rank(climate: dict, soil: dict) -> list[dict]:
    results = [evaluate(c, climate, soil) for c in CROPS]
    return sorted(results, key=lambda r: (r["score_irrigated"], r["score_rainfed"]), reverse=True)
