"""Interpret a soil-moisture reading instead of comparing it with one fixed number.

The same volumetric water content means very different things in sand and in clay: 30 % is
saturated sand but a comfortable clay. We convert the reading into the fraction of plant-available
water between wilting point (WP) and field capacity (FC) for the soil texture (FAO-56, Table 19)
and compare it with the crop's depletion fraction p (FAO-56, Table 22): stress starts when less than
(1 - p) of the available water is left. Readings from simulated or uncalibrated sensors are flagged.
"""
from __future__ import annotations

FAO56_TABLE19 = {"title": "FAO-56, Tabella 19 – acqua disponibile per tipo di terreno",
                 "url": "https://www.fao.org/4/x0490e/x0490e0c.htm"}
FAO56_TABLE22 = {"title": "FAO-56, Tabella 22 – quanta acqua può perdere ogni coltura prima dello stress",
                 "url": "https://www.fao.org/4/x0490e/x0490e0e.htm"}

# typical volumetric water content (%) at field capacity and wilting point, FAO-56 Table 19 (mid values);
# "sat" = typical saturation (total porosity), used only to tell "wet" from "waterlogged"
TEXTURES: dict[str, dict] = {
    "sand": {"label": "sabbioso", "fc": 12, "wp": 4, "sat": 38},
    "loamy_sand": {"label": "sabbioso-franco", "fc": 15, "wp": 6, "sat": 40},
    "sandy_loam": {"label": "franco-sabbioso", "fc": 23, "wp": 10, "sat": 41},
    "loam": {"label": "franco (medio impasto)", "fc": 25, "wp": 12, "sat": 43},
    "silt_loam": {"label": "franco-limoso", "fc": 29, "wp": 15, "sat": 45},
    "silt": {"label": "limoso", "fc": 32, "wp": 17, "sat": 46},
    "silty_clay_loam": {"label": "franco-limoso-argilloso", "fc": 34, "wp": 20, "sat": 48},
    "clay_loam": {"label": "franco-argilloso", "fc": 32, "wp": 18, "sat": 46},
    "silty_clay": {"label": "argilloso-limoso", "fc": 36, "wp": 23, "sat": 50},
    "clay": {"label": "argilloso", "fc": 36, "wp": 22, "sat": 50},
}
ALIASES = {
    "sabbioso": "sand", "sabbia": "sand", "sandy": "sand",
    "franco sabbioso": "sandy_loam", "franco-sabbioso": "sandy_loam", "sandy loam": "sandy_loam",
    "medio impasto": "loam", "franco": "loam", "loam": "loam",
    "franco limoso": "silt_loam", "silt loam": "silt_loam", "limoso": "silt",
    "franco argilloso": "clay_loam", "clay loam": "clay_loam",
    "argilloso": "clay", "argilla": "clay", "clay": "clay", "silty clay": "silty_clay",
}
# FAO-56 Table 22 depletion fraction p (share of available water the crop can use before stress)
CROP_P = {"pomodoro": 0.40, "tomato": 0.40, "peperone": 0.30, "pepper": 0.30, "melanzana": 0.45,
          "patata": 0.35, "potato": 0.35, "lattuga": 0.30, "insalata": 0.30, "zucchina": 0.50,
          "mais": 0.55, "maize": 0.55, "frumento": 0.55, "grano": 0.55, "vite": 0.45, "uva": 0.45,
          "olivo": 0.65, "fragola": 0.20, "cipolla": 0.30, "fagiolo": 0.45, "riso": 0.20}
DEFAULT_P = 0.50

STATUS_LABEL = {
    "very_dry": "molto secco (vicino al punto di appassimento)",
    "dry": "secco: la coltura può andare in stress",
    "adequate": "acqua sufficiente",
    "wet": "umido (sopra la capacità di campo)",
    "very_wet": "molto bagnato, possibile ristagno",
    "unknown": "non interpretabile",
}


def normalise_texture(soil_type: str | None) -> str | None:
    if not soil_type:
        return None
    k = soil_type.strip().lower().replace("_", " ")
    if k.replace(" ", "_") in TEXTURES:
        return k.replace(" ", "_")
    return ALIASES.get(k)


def crop_p(crop: str | None) -> float:
    if not crop:
        return DEFAULT_P
    c = crop.strip().lower()
    return next((p for name, p in CROP_P.items() if name in c), DEFAULT_P)


def _status(theta: float, t: dict, p: float) -> tuple[str, float]:
    fc, wp, sat = t["fc"], t["wp"], t["sat"]
    f = (theta - wp) / (fc - wp)  # 0 = wilting point, 1 = field capacity
    if f < 0.1:
        return "very_dry", f
    if f < 1 - p:
        return "dry", f
    if theta <= fc * 1.08:
        return "adequate", f
    if theta <= fc + 0.6 * (sat - fc):
        return "wet", f
    return "very_wet", f


def interpret(value: float | None, unit: str | None = "%", source: str | None = None,
              soil_type: str | None = None, crop: str | None = None,
              calibration: dict | None = None) -> dict | None:
    if value is None:
        return None
    cal = calibration or {}
    notes: list[str] = []
    out = {"value": value, "unit": unit, "source": source, "sources": [FAO56_TABLE19, FAO56_TABLE22]}
    if unit not in (None, "%", "%vol", "vwc"):
        return {**out, "status": "unknown", "status_label": STATUS_LABEL["unknown"], "usable": False,
                "reliability": "nessuna", "notes": [f"Il valore è in «{unit}», non in % di volume d'acqua: va prima calibrato."]}

    p = crop_p(crop)
    texture = normalise_texture(soil_type)
    if texture:
        t = TEXTURES[texture]
        status, frac = _status(value, t, p)
        out.update(texture=texture, texture_label=t["label"], texture_assumed=False, fc=t["fc"], wp=t["wp"],
                   available_fraction=round(frac, 2))
        notes.append(f"Per un terreno {t['label']} la capacità di campo è circa {t['fc']}% e il punto di "
                     f"appassimento circa {t['wp']}%.")
    else:
        by_tex = {k: _status(value, t, p)[0] for k, t in TEXTURES.items()}
        statuses = set(by_tex.values())
        out.update(texture=None, texture_assumed=True, by_texture=by_tex)
        if len(statuses) == 1:
            status = statuses.pop()
            notes.append("Il tipo di terreno non è indicato, ma il risultato è lo stesso per tutti i terreni.")
        elif statuses <= {"adequate", "wet", "very_wet"}:
            status = "adequate"
            notes.append("Il tipo di terreno non è indicato: con questo valore non è secco per nessun tipo di terreno.")
        elif statuses <= {"dry", "very_dry"}:
            status = "dry"
            notes.append("Il tipo di terreno non è indicato: con questo valore è secco per tutti i tipi di terreno.")
        else:
            status = "unknown"
            dry = [TEXTURES[k]["label"] for k, v in by_tex.items() if v in ("dry", "very_dry")]
            notes.append("Dipende dal terreno: sarebbe secco solo per terreni " + ", ".join(dry) +
                         ". Indica il tipo di terreno del campo per un giudizio preciso.")

    stype = (cal.get("type") or "").lower()
    if source == "simulation":
        usable, reliability = False, "nessuna"
        notes.insert(0, "È un dato simulato (di prova): non viene usato come prova per la diagnosi.")
    elif cal.get("soil_specific") or cal.get("calibrated_for_soil"):
        usable, reliability = True, "alta"
        notes.append("Sensore calibrato sul terreno del campo.")
    elif cal.get("calibrated") or stype in ("tdr", "fdr"):
        usable, reliability = True, "media"
        notes.append("Sensore con calibrazione generica: errore tipico di 2–3 punti.")
    else:
        usable, reliability = True, "bassa"
        notes.append("Sensore senza calibrazione sul terreno (es. capacitivo economico): può sbagliare di "
                     "3–5 punti o più, quindi conta come indizio debole.")
    notes.append("Una sola lettura non dice se l'irrigazione è stata regolare nei giorni scorsi.")
    out.update(status=status, status_label=STATUS_LABEL[status], usable=usable, reliability=reliability,
               crop_p=p, notes=notes)
    return out
