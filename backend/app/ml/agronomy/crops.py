"""Crop requirement knowledge base.

INDICATIVE ranges compiled from general agronomic references (FAO crop water
needs tables, FAO ECOCROP-style ranges, FAO-56 crop coefficients). They are
screening values for a first suitability pass — local varieties, extension
services and field trials always take precedence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KB_SOURCES = [
    {"title": "FAO – Gestione dell'irrigazione, manuale 3: fabbisogni idrici delle colture",
     "url": "https://www.fao.org/4/s2022e/s2022e00.htm"},
    {"title": "FAO – Evapotraspirazione delle colture, quaderno 56 (coefficienti colturali)",
     "url": "https://www.fao.org/4/x0490e/x0490e00.htm"},
    {"title": "FAO GAEZ – banca dati ECOCROP sulle esigenze delle colture",
     "url": "https://gaez.fao.org/pages/ecocrop"},
]


@dataclass(frozen=True)
class Crop:
    key: str
    name: str
    season: str               # summer | winter | perennial
    base_temp: int            # 0, 5 or 10 °C for growing degree days
    gdd_min: float
    t_opt: tuple[float, float]  # optimal mean temperature over the growing season
    frost_min_c: float | None   # tolerated minimum (winter crops, perennials)
    min_frost_free_days: int | None  # frost-sensitive summer crops
    water_mm: tuple[int, int]   # FAO typical seasonal crop water need
    kc: float                   # approximate season-average crop coefficient
    ph: tuple[float, float]
    texture: dict = field(default_factory=lambda: {"light": 0.8, "medium": 1.0, "heavy": 0.8})
    legume: bool = False
    needs_flooding: bool = False
    family: str = ""
    notes: str = ""


CROPS: list[Crop] = [
    Crop("wheat", "Frumento tenero", "winter", 0, 1900, (5, 15), -18, None, (450, 650), 0.75, (6.0, 7.5),
         {"light": 0.7, "medium": 1.0, "heavy": 0.9}, family="cereale"),
    Crop("durum_wheat", "Frumento duro", "winter", 0, 1900, (7, 16), -10, None, (450, 650), 0.75, (6.0, 8.0),
         {"light": 0.6, "medium": 1.0, "heavy": 0.9}, family="cereale",
         notes="Cereale mediterraneo: la qualità migliora con una maturazione asciutta."),
    Crop("barley", "Orzo", "winter", 0, 1600, (4, 15), -15, None, (450, 650), 0.75, (6.0, 8.0),
         family="cereale", notes="Ciclo breve; tollera terreni un po' salini o alcalini."),
    Crop("rapeseed", "Colza", "winter", 0, 1600, (5, 15), -12, None, (450, 650), 0.75, (5.5, 7.5),
         family="crucifera", notes="Buona coltura da rotazione tra i cereali."),
    Crop("pea", "Pisello proteico", "winter", 0, 1100, (7, 16), -5, None, (350, 500), 0.75, (6.0, 7.5),
         legume=True, family="leguminosa"),
    Crop("chickpea", "Cece", "winter", 0, 1300, (8, 16), -8, None, (300, 500), 0.70, (6.0, 8.5),
         {"light": 0.9, "medium": 1.0, "heavy": 0.6}, legume=True, family="leguminosa",
         notes="Resiste alla siccità; non sopporta i ristagni d'acqua."),
    Crop("maize", "Mais da granella", "summer", 10, 1300, (20, 26), None, 130, (500, 800), 0.85, (5.8, 7.5),
         {"light": 0.7, "medium": 1.0, "heavy": 0.8}, family="cereale"),
    Crop("rice", "Riso", "summer", 10, 1400, (20, 27), None, 140, (450, 700), 1.05, (5.5, 7.0),
         {"light": 0.2, "medium": 0.6, "heavy": 1.0}, needs_flooding=True, family="cereale",
         notes="L'acqua indicata è solo quella consumata dalla pianta: in risaia sommersa se ne perde molta "
               "di più per infiltrazione. Servono terreno poco permeabile e diritti d'acqua sicuri."),
    Crop("soybean", "Soia", "summer", 10, 1200, (20, 26), None, 120, (450, 700), 0.85, (6.0, 7.0),
         legume=True, family="leguminosa"),
    Crop("sunflower", "Girasole", "summer", 5, 1500, (18, 25), None, 110, (600, 1000), 0.80, (6.0, 7.5),
         family="composita", notes="Radici profonde: abbastanza resistente alla siccità."),
    Crop("sorghum", "Sorgo", "summer", 10, 1300, (22, 30), None, 120, (450, 650), 0.80, (5.5, 7.5),
         family="cereale", notes="Resiste a siccità e caldo meglio del mais."),
    Crop("tomato", "Pomodoro da industria", "summer", 10, 1200, (20, 26), None, 130, (400, 800), 0.85, (6.0, 7.0),
         {"light": 0.8, "medium": 1.0, "heavy": 0.7}, family="solanacea"),
    Crop("potato", "Patata", "summer", 5, 1200, (15, 20), None, 100, (500, 700), 0.85, (5.0, 6.5),
         {"light": 1.0, "medium": 0.9, "heavy": 0.4}, family="solanacea",
         notes="Preferisce stagioni fresche; i terreni pesanti ostacolano tuberi e raccolta."),
    Crop("onion", "Cipolla", "summer", 5, 1000, (13, 24), None, 90, (350, 550), 0.80, (6.0, 7.0),
         {"light": 0.9, "medium": 1.0, "heavy": 0.5}, family="liliacea"),
    Crop("sugar_beet", "Barbabietola da zucchero", "summer", 5, 1600, (15, 22), None, 150, (550, 750), 0.90,
         (6.5, 8.0), {"light": 0.6, "medium": 1.0, "heavy": 0.8}, family="chenopodiacea"),
    Crop("alfalfa", "Erba medica", "perennial", 5, 1000, (15, 25), -25, None, (800, 1600), 0.90, (6.5, 7.5),
         {"light": 0.8, "medium": 1.0, "heavy": 0.6}, legume=True, family="leguminosa",
         notes="Fissa l'azoto nel terreno; vuole un terreno ben drenato."),
    Crop("grapevine", "Vite", "perennial", 10, 1000, (17, 24), -15, None, (500, 800), 0.60, (5.5, 8.0),
         {"light": 0.9, "medium": 1.0, "heavy": 0.7}, family="vitacea",
         notes="Investimento a lungo termine: verifica disciplinari e diritti di impianto."),
    Crop("olive", "Olivo", "perennial", 10, 1000, (20, 27), -7, None, (400, 800), 0.60, (6.0, 8.5),
         {"light": 1.0, "medium": 1.0, "heavy": 0.6}, family="oleacea",
         notes="Il gelo sotto i −7 °C danneggia gli alberi; resiste bene alla siccità."),
    Crop("hazelnut", "Nocciolo", "perennial", 10, 900, (18, 24), -15, None, (700, 900), 0.75, (6.0, 7.5),
         family="betulacea"),
]

CROPS_BY_KEY = {c.key: c for c in CROPS}
