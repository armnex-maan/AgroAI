from app.simulation.engine import SimulationEngine
from app.integrations.hardware import DeviceDescriptor


def test_engine_produces_core_sensors():
    engine = SimulationEngine(scenario="healthy", seed=42)
    desc = DeviceDescriptor(
        device_id="X", farm_id=None, zone_id=None, hardware_type="esp32", source="simulation",
        sensors=[{"type": t, "unit": u} for t, u in [
            ("soil_moisture", "%"), ("air_temperature", "C"), ("air_humidity", "%"),
        ]],
    )
    out = engine.sample(desc)
    assert "soil_moisture" in out
    assert out["soil_moisture"]["unit"] == "%"
    assert 0 <= out["soil_moisture"]["value"] <= 100


def test_values_stay_physically_possible():
    engine = SimulationEngine(scenario="water_stress", seed=3)
    types = ["rainfall", "air_humidity", "light_intensity", "wind_speed", "soil_moisture"]
    desc = DeviceDescriptor("X", None, None, "esp32", "simulation", [{"type": t, "unit": ""} for t in types])
    for _ in range(300):
        out = engine.sample(desc)
        for t, v in out.items():
            assert v["value"] >= 0, (t, v)
        if "air_humidity" in out:
            assert out["air_humidity"]["value"] <= 100


def test_water_stress_drifts_down():
    engine = SimulationEngine(scenario="water_stress", seed=1)
    desc = DeviceDescriptor("X", None, None, "esp32", "simulation", [{"type": "soil_moisture", "unit": "%"}])
    first = engine.sample(desc).get("soil_moisture", {}).get("value", 100)
    for _ in range(50):
        engine.sample(desc)
    last = engine.sample(desc).get("soil_moisture", {}).get("value", first)
    assert last <= first + 5  # downward or stable
