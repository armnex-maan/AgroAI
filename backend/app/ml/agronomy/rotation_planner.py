"""Per-plot, per-section multi-year planner.

Each growing bed (section) has its own history; the planner picks, year after year, the crop that best
respects the rules for that bed, favours the farmer's wishes until the wished area is covered, and
spreads botanical families across the beds of the same year. Choices are 'suggerimenti' of AGROAI:
the rules they respect keep their own level (obbligatoria / disciplinare / buona pratica).
"""
from __future__ import annotations

from app.ml.agronomy import rotation as base

GROWING = {"bed", "greenhouse"}

# Indicative open-field calendar for central-northern Italy (months 1-12). Varies with area and variety.
CALENDAR: dict[str, dict[str, list[int]]] = {
    "tomato": {"semina": [2, 3], "trapianto": [4, 5], "raccolta": [7, 8, 9]},
    "potato": {"semina": [3, 4], "raccolta": [7, 8, 9]},
    "eggplant": {"semina": [2, 3], "trapianto": [5], "raccolta": [7, 8, 9]},
    "pepper": {"semina": [2, 3], "trapianto": [5], "raccolta": [7, 8, 9, 10]},
    "zucchini": {"semina": [4, 5], "trapianto": [5], "raccolta": [6, 7, 8, 9]},
    "cucumber": {"semina": [4, 5], "trapianto": [5], "raccolta": [6, 7, 8]},
    "melon": {"semina": [4], "trapianto": [5], "raccolta": [7, 8]},
    "watermelon": {"semina": [4], "trapianto": [5], "raccolta": [7, 8]},
    "pumpkin": {"semina": [4, 5], "trapianto": [5], "raccolta": [9, 10]},
    "strawberry": {"trapianto": [8, 9], "raccolta": [5, 6]},
    "cabbage": {"semina": [5, 6, 7], "trapianto": [7, 8], "raccolta": [10, 11, 12, 1]},
    "rocket": {"semina": [3, 4, 5, 8, 9], "raccolta": [4, 5, 6, 9, 10]},
    "lettuce": {"semina": [2, 3, 4, 8], "trapianto": [3, 4, 5, 9], "raccolta": [5, 6, 7, 10]},
    "chicory": {"semina": [6, 7], "trapianto": [7, 8], "raccolta": [10, 11, 12]},
    "spinach": {"semina": [2, 3, 9, 10], "raccolta": [4, 5, 11, 12]},
    "chard": {"semina": [3, 4, 8], "raccolta": [6, 7, 8, 10, 11]},
    "basil": {"semina": [3, 4], "trapianto": [5], "raccolta": [6, 7, 8, 9]},
    "celery": {"semina": [2, 3], "trapianto": [5, 6], "raccolta": [9, 10, 11]},
    "parsley": {"semina": [3, 4, 5], "raccolta": [6, 7, 8, 9, 10]},
    "fennel": {"semina": [6, 7], "trapianto": [7, 8], "raccolta": [10, 11, 12]},
    "carrot": {"semina": [3, 4, 5, 6], "raccolta": [6, 7, 8, 9, 10]},
    "radish": {"semina": [3, 4, 5, 9], "raccolta": [4, 5, 6, 10]},
    "turnip": {"semina": [8, 9], "raccolta": [10, 11, 12]},
    "onion": {"semina": [2, 3], "trapianto": [3, 4], "raccolta": [6, 7, 8]},
    "garlic": {"semina": [10, 11, 2], "raccolta": [6, 7]},
    "leek": {"semina": [3, 4], "trapianto": [6, 7], "raccolta": [10, 11, 12, 1, 2]},
    "shallot": {"semina": [10, 11, 2], "raccolta": [6, 7]},
    "asparagus": {"trapianto": [3, 4], "raccolta": [4, 5]},
    "bean": {"semina": [4, 5, 6], "raccolta": [7, 8, 9]},
    "green_bean": {"semina": [4, 5, 6, 7], "raccolta": [6, 7, 8, 9]},
    "pea": {"semina": [10, 11, 2, 3], "raccolta": [5, 6]},
    "faba": {"semina": [10, 11], "raccolta": [5, 6]},
    "chickpea": {"semina": [2, 3], "raccolta": [7]},
    "soybean": {"semina": [4, 5], "raccolta": [9, 10]},
    "alfalfa": {"semina": [3, 4, 8, 9], "raccolta": [5, 6, 7, 8, 9]},
    "wheat": {"semina": [10, 11], "raccolta": [6, 7]},
    "barley": {"semina": [10, 11], "raccolta": [6]},
    "maize": {"semina": [4, 5], "raccolta": [9, 10]},
    "sorghum": {"semina": [5], "raccolta": [9, 10]},
    "sunflower": {"semina": [4], "raccolta": [8, 9]},
    "rapeseed": {"semina": [9, 10], "raccolta": [6]},
    "sugar_beet": {"semina": [3], "raccolta": [8, 9, 10]},
}


def beds(sections: list[dict], plot_area: float | None) -> list[dict]:
    out = [s for s in sections if s.get("kind", "bed") in GROWING]
    if out:
        for s in out:
            s.setdefault("area_m2", round(float(s.get("w", 0)) * float(s.get("h", 0)), 1))
        return out
    return [{"id": None, "name": "Intero appezzamento", "kind": "bed", "area_m2": plot_area or 0}]


def plan_plot(sections: list[dict], history: dict, plot_history: list, years: list[int], *, problems: set[str],
              soil: str | None, region: str | None, integrated: bool | None, wanted: dict[str, float],
              plot_area: float | None = None, purpose: str = "family") -> dict:
    """sections: [{id, name, kind, w, h}], history: {section_id: [season0, season1, ...]} (season = list of
    crop keys, or None when unknown/rest), plot_history: seasons recorded for the whole plot (used for beds
    without their own history), wanted: {crop_key: desired area m² (0 = any)}."""
    bs = beds([dict(s) for s in sections], plot_area)
    hist = {b["id"]: list(history.get(b["id"]) or plot_history) for b in bs}
    total = sum(b["area_m2"] for b in bs) or 1
    remaining = {k: (a if a > 0 else total / max(1, len(wanted))) for k, a in wanted.items()}
    pool = [c for c in base.CROPS if c.season != "pluriennale"]
    out_years = []
    for y in years:
        year_fams: dict[str, int] = {}
        assignments, unplaced = [], []
        for b in sorted(bs, key=lambda b: -b["area_m2"]):
            best = None
            for c in pool:
                j = base.judge(c, hist[b["id"]], problems, soil, region, integrated)
                if j["verdict"] == "no":
                    continue
                s = j["score"]
                if c.key in remaining and remaining[c.key] > 0:
                    s += 5.0  # a crop the farmer asked for wins over an unrequested one unless it breaks a rule
                elif wanted and purpose == "commercial":
                    s -= 0.5  # commercial plans stick to the crops chosen for sale
                s -= 1.2 * year_fams.get(c.family, 0)  # different families in neighbouring beds
                if c.key in [a["crop"] for a in assignments]:
                    s -= 0.8
                if best is None or s > best[0]:
                    best = (s, c, j)
            if best is None:
                assignments.append({"section_id": b["id"], "section": b["name"], "crop": "cover", "name": "Sovescio",
                                    "family": "", "area_m2": b["area_m2"], "verdict": "ok",
                                    "reasons": [{"effect": "warn", "level": "suggerimento", "rule": False, "source": None,
                                                 "text": "Nessuna coltura rispetta le regole per questa aiuola: semina un sovescio."}]})
                hist[b["id"]].insert(0, None)
                continue
            _, c, j = best
            why = ("È tra le colture che vuoi coltivare e rispetta le regole di questa aiuola."
                   if c.key in remaining and remaining[c.key] > 0 else
                   f"Scelta da AGROAI per variare le famiglie ({c.family}) e rispettare la storia di questa aiuola.")
            remaining[c.key] = remaining.get(c.key, 0) - b["area_m2"]
            year_fams[c.family] = year_fams.get(c.family, 0) + 1
            assignments.append({"section_id": b["id"], "section": b["name"], "crop": c.key, "name": c.name,
                                "family": c.family, "area_m2": round(b["area_m2"], 1), "verdict": j["verdict"],
                                "reasons": [{"effect": "good", "level": "suggerimento", "rule": False, "source": None,
                                             "text": why}] + j["reasons"],
                                "calendar": CALENDAR.get(c.key)})
            hist[b["id"]].insert(0, [c.key])
        for k, left in remaining.items():
            asked = wanted.get(k, 0)
            if left > 0.5 and (asked == 0 or left >= asked * 0.5) and k not in [a["crop"] for a in assignments]:
                best_bed = bs[0]
                j = base.judge(base.BY_KEY[k], hist[best_bed["id"]][1:], problems, soil, region, integrated)
                unplaced.append({"crop": k, "name": base.BY_KEY[k].name,
                                 "why": next((r["text"] for r in j["reasons"] if r["effect"] == "bad"),
                                             "Non c'è un'aiuola libera adatta quest'anno.")})
        area_by_crop: dict[str, float] = {}
        for a in assignments:
            area_by_crop[a["name"]] = round(area_by_crop.get(a["name"], 0) + a["area_m2"], 1)
        out_years.append({"year": y, "assignments": assignments, "unplaced": unplaced, "area_by_crop": area_by_crop})
        # the wish is per season: reset the remaining area for the next year
        remaining = {k: (a if a > 0 else total / max(1, len(wanted))) for k, a in wanted.items()}
    return {"years": out_years, "beds": [{"id": b["id"], "name": b["name"], "area_m2": b["area_m2"]} for b in bs]}
