"""Irrigation advice for the Visual Farm Planner: how much water a planned crop needs month by month and which
system suits it. Pure functions (the API passes the local climate).

Data:
- Kc (crop coefficients) at the initial, mid-season and late stage: FAO Irrigation and Drainage Paper 56
  (Allen et al. 1998), Table 12 – the same table used for plant heights. Where the table gives a range, the middle
  value is used and noted.
- ET0 and rain: Open-Meteo ERA5 reanalysis, multi-year monthly means for the farm location (CC BY 4.0).
- Field application efficiency: FAO Irrigation Water Management Training Manual 4 (Irrigation Scheduling), typical
  values: surface 60 %, sprinkler 75 %, drip 90 %.
Simplifications, stated to the farmer: growth stages split from the indicative sowing/harvest calendar; useful rain
estimated as 80 % of the mean rain.
"""
from __future__ import annotations

KC_SOURCE = {"id": "fao56_t12_kc", "title": "FAO (1998) – Irrigation and Drainage Paper 56, Table 12 (coefficienti colturali Kc)",
             "year": 1998, "url": "https://www.fao.org/4/x0490e/x0490e0b.htm"}
EFF_SOURCE = {"id": "fao_tm4", "title": "FAO – Irrigation Water Management, Training Manual 4: Irrigation Scheduling (efficienze tipiche)",
              "year": 1989, "url": "https://www.fao.org/4/t7202e/t7202e00.htm"}

# crop -> (Kc ini, Kc mid, Kc end); comment = row of Table 12 when the name differs / ranges
KC: dict[str, tuple[float, float, float]] = {
    "tomato": (0.6, 1.15, 0.80),        # end 0.70-0.90
    "pepper": (0.6, 1.05, 0.90),        # Sweet Peppers (bell)
    "eggplant": (0.6, 1.05, 0.90),
    "potato": (0.5, 1.15, 0.75),
    "zucchini": (0.5, 0.95, 0.75),      # Squash, Zucchini
    "pumpkin": (0.5, 1.00, 0.80),       # Pumpkin, Winter Squash
    "cucumber": (0.6, 1.00, 0.75),      # Cucumber, fresh market
    "melon": (0.5, 1.05, 0.75),         # Sweet Melons
    "watermelon": (0.4, 1.00, 0.75),
    "lettuce": (0.7, 1.00, 0.95), "cabbage": (0.7, 1.05, 0.95), "spinach": (0.7, 1.00, 0.95),
    "carrot": (0.7, 1.05, 0.95), "celery": (0.7, 1.05, 1.00), "radish": (0.7, 0.90, 0.85),
    "onion": (0.7, 1.05, 0.75),         # Onions, dry
    "garlic": (0.7, 1.00, 0.70),
    "turnip": (0.5, 1.10, 0.95),
    "bean": (0.4, 1.15, 0.35),          # Beans, dry
    "green_bean": (0.5, 1.05, 0.90),    # Beans, green
    "pea": (0.5, 1.15, 1.10),           # Peas, fresh
    "chickpea": (0.4, 1.00, 0.35), "soybean": (0.4, 1.15, 0.50),
    "faba": (0.5, 1.15, 1.10),          # Faba bean, fresh
    "strawberry": (0.4, 0.85, 0.75), "asparagus": (0.5, 0.95, 0.30),
    "sugar_beet": (0.35, 1.20, 0.70), "sunflower": (0.35, 1.08, 0.35),   # mid 1.0-1.15
    "rapeseed": (0.35, 1.08, 0.35),     # Rapeseed, canola: mid 1.0-1.15
    "wheat": (0.4, 1.15, 0.33),         # Winter Wheat: end 0.25-0.4
    "barley": (0.3, 1.15, 0.25), "maize": (0.3, 1.20, 0.48),           # Maize grain: end 0.60-0.35
    "sorghum": (0.3, 1.05, 0.55),       # Sorghum grain: mid 1.00-1.10
    "alfalfa": (0.4, 0.95, 0.90),       # Alfalfa hay, averaged cutting effects
}

EFFICIENCY = {"drip": 0.90, "sprinkler": 0.75, "furrow": 0.60}
SYSTEM_NAME = {"drip": "a goccia", "sprinkler": "a pioggia", "furrow": "a scorrimento / solchi", "manual": "a mano", "none": "nessuna"}
STAGE_NAME = {"ini": "iniziale", "dev": "sviluppo", "mid": "piena crescita", "end": "maturazione"}


def season_months(cal: dict | None) -> list[int]:
    """Months in the field, from transplant (or sowing) to the end of harvest (indicative calendar)."""
    if not cal or not cal.get("raccolta"):
        return []
    start = (cal.get("trapianto") or cal.get("semina") or [None])[0]
    if not start:
        return []
    end = cal["raccolta"][-1]
    n = (end - start) % 12 + 1
    return [((start - 1 + i) % 12) + 1 for i in range(n)]


def stage_kc(kc: tuple[float, float, float], i: int, n: int) -> tuple[str, float]:
    """Kc of month i of n: first quarter initial, second quarter development (linear), then mid-season, last
    month(s) late stage (FAO-56 curve with stage lengths split evenly – an indicative split)."""
    ini, mid, end = kc
    t = (i + 0.5) / n
    if t < 0.25:
        return "ini", ini
    if t < 0.5:
        return "dev", round(ini + (mid - ini) * (t - 0.25) / 0.25, 2)
    if t < 0.85 or n < 3:
        return "mid", mid
    return "end", end


def suggest_system(group: str, kind: str) -> tuple[str, str]:
    """AgroAI suggestion (not a rule) with its reason."""
    if kind == "greenhouse":
        return "drip", "In serra l'acqua arriva solo dall'impianto: la goccia bagna il terreno vicino alle radici e tiene asciutte foglie e aria, con meno malattie fungine."
    if group == "cereale":
        return "none", "I cereali in pieno campo di solito crescono con la pioggia; si irriga solo in soccorso, a pioggia, nelle annate secche."
    if group == "foglia":
        return "drip", "Le colture da foglia sono a file fitte: la goccia (o una manichetta) dà acqua regolare senza bagnare le foglie che raccogli."
    return "drip", "Coltura a file: la goccia porta l'acqua al piede delle piante, perde meno acqua per evaporazione e non bagna le foglie (meno malattie)."


def advice(crop_key: str, crop_name: str, group: str, kind: str, area_m2: float, cal: dict | None, climate: dict | None,
           declared: str | None) -> dict:
    kc = KC.get(crop_key)
    months = season_months(cal)
    sys_key, why = suggest_system(group, kind)
    system = {"suggested": sys_key, "suggested_name": SYSTEM_NAME[sys_key], "why": why, "level": "suggerimento",
              "declared": declared, "declared_name": SYSTEM_NAME.get(declared or "", None)}
    out = {"crop": crop_key, "name": crop_name, "area_m2": round(area_m2, 1), "kc": list(kc) if kc else None,
           "season": months, "months": [], "peak": None, "system": system}
    if not kc or not months:
        return out
    eff_key = declared if declared in EFFICIENCY else (sys_key if sys_key in EFFICIENCY else None)
    eff = EFFICIENCY.get(eff_key) if eff_key else None
    for i, m in enumerate(months):
        stage, k = stage_kc(kc, i, len(months))
        row = {"month": m, "stage": stage, "stage_name": STAGE_NAME[stage], "kc": k}
        if climate:
            cm = climate["monthly"][m - 1]
            etc = k * cm["et0_mm"]
            rain = 0.8 * cm["precip_mm"]
            net = max(0.0, etc - rain)
            row.update({"et0_mm": cm["et0_mm"], "etc_mm": round(etc, 1), "rain_eff_mm": round(rain, 1), "net_mm": round(net, 1),
                        "liters_week": round(net * area_m2 / 4.35), "gross_liters_week": round(net * area_m2 / 4.35 / eff) if eff else None})
        out["months"].append(row)
    if climate:
        peak = max(out["months"], key=lambda r: r["net_mm"])
        out["peak"] = peak if peak["net_mm"] > 0 else None
        out["season_net_mm"] = round(sum(r["net_mm"] for r in out["months"]), 0)
        out["efficiency"] = {"system": eff_key, "value": eff} if eff else None
    return out
