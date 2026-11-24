from app.integrations.soilgrids import texture_class, summarize
from app.ml.agronomy import suitability, practices

# Po-valley-like climate, synthetic but plausible.
CLIMATE = {
    "seasons": {"summer": {"t_mean": 21.0, "precip_mm": 420, "et0_mm": 720},
                "winter": {"t_mean": 8.0, "precip_mm": 480, "et0_mm": 330}},
    "gdd": {"summer_base10": 1950, "summer_base5": 2850, "winter_base0": 2200},
    "annual": {"frost_free_days": 210, "mean_annual_min_c": -6.0, "precip_mm": 850, "et0_mm": 1050},
}
CLAY_SOIL = {"ph": 6.3, "ph_source": "test", "texture": "silty clay loam", "soc_g_kg": 9.0}
SANDY_SOIL = {"ph": 6.3, "ph_source": "test", "texture": "loamy sand", "soc_g_kg": 9.0}


def test_texture_triangle():
    assert texture_class(90, 5, 5) == "sand"
    assert texture_class(40, 40, 20) == "loam"
    assert texture_class(10, 30, 60) == "clay"
    assert texture_class(15, 55, 30) == "silty clay loam"


def test_soilgrids_unit_conversion():
    raw = {"properties": {"layers": [
        {"name": "phh2o", "depths": [{"label": d, "values": {"mean": 65}} for d in ("0-5cm", "5-15cm", "15-30cm")]},
        {"name": "clay", "depths": [{"label": d, "values": {"mean": 300}} for d in ("0-5cm", "5-15cm", "15-30cm")]},
        {"name": "sand", "depths": [{"label": d, "values": {"mean": 200}} for d in ("0-5cm", "5-15cm", "15-30cm")]},
        {"name": "silt", "depths": [{"label": d, "values": {"mean": 500}} for d in ("0-5cm", "5-15cm", "15-30cm")]},
    ]}}
    s = summarize(raw)
    assert s["properties"]["phh2o"]["value"] == 6.5
    assert s["properties"]["clay"]["value"] == 30.0
    assert s["texture"] == "silty clay loam"


def test_rice_prefers_heavy_soil_and_needs_water():
    clay = {r["key"]: r for r in suitability.rank(CLIMATE, CLAY_SOIL)}
    sand = {r["key"]: r for r in suitability.rank(CLIMATE, SANDY_SOIL)}
    assert clay["rice"]["score_irrigated"] > sand["rice"]["score_irrigated"]
    assert clay["rice"]["score_rainfed"] < 0.4  # flooded crop is never rainfed-suitable
    assert clay["potato"]["score_irrigated"] < sand["potato"]["score_irrigated"]


def test_perennials_judged_on_worst_winter():
    mild_avg_cold_extreme = {**CLIMATE, "annual": {**CLIMATE["annual"], "mean_annual_min_c": -5.0,
                                                   "absolute_min_c": -11.0}}
    by = {r["key"]: r for r in suitability.rank(mild_avg_cold_extreme, CLAY_SOIL)}
    assert by["olive"]["limiting_key"] == "frost"  # perennial: uses -11
    assert by["durum_wheat"]["limiting_key"] != "frost"  # annual: uses -5


def test_cold_site_rejects_olive():
    cold = {**CLIMATE, "annual": {**CLIMATE["annual"], "mean_annual_min_c": -14.0}}
    olive = next(r for r in suitability.rank(cold, CLAY_SOIL) if r["key"] == "olive")
    assert olive["class_irrigated"] in ("S3", "N")
    assert olive["limiting_key"] == "frost"


def test_every_factor_is_explained():
    for r in suitability.rank(CLIMATE, CLAY_SOIL):
        assert all({"factor", "value", "requirement", "score"} <= set(f) for f in r["factors"])


def test_eu_blocks_crab_and_crayfish():
    it = {s["id"]: s for s in practices.rice_systems("IT", None)["systems"]}
    assert it["rice_crab"]["legal"]["status"] == "prohibited"
    assert it["rice_crayfish"]["legal"]["status"] == "prohibited"
    assert it["rice_duck"]["legal"]["status"] == "allowed_with_conditions"
    cn = {s["id"]: s for s in practices.rice_systems("CN", None)["systems"]}
    assert cn["rice_crab"]["legal"]["status"] == "check_local"


def test_cost_tips_carry_sources():
    tips = practices.cost_tips(CLIMATE, CLAY_SOIL, suitability.rank(CLIMATE, CLAY_SOIL), False)
    ids = {t["id"] for t in tips}
    assert {"sensor_irrigation", "organic_matter", "reduced_tillage", "soil_test"} <= ids
    assert all(t["sources"] and t["sources"][0]["url"].startswith("https://") for t in tips)
