"""Scenario definitions — parameter sets that drive the simulator."""

SCENARIOS: dict[str, dict] = {
    "healthy": {
        "title": "Campo in salute",
        "description": "Umidità del terreno stabile e temperature miti: tutto nella norma.",
        "soil_moisture_base": 38.0, "soil_moisture_amp": 2.0, "soil_moisture_drift": 0.0,
        "air_temp_base": 22.0, "air_temp_amp": 4.0,
        "air_humidity_base": 60.0, "air_humidity_amp": 6.0,
        "soil_ph_base": 6.8, "soil_ec_base": 1.2,
        "rainfall_prob": 0.05,
        "acoustic_events": [],
    },
    "water_stress": {
        "title": "Siccità e caldo",
        "description": "La temperatura sale, il terreno si asciuga e non è prevista pioggia.",
        "soil_moisture_base": 22.0, "soil_moisture_amp": 1.5, "soil_moisture_drift": -0.20,
        "air_temp_base": 33.0, "air_temp_amp": 5.0,
        "air_humidity_base": 30.0, "air_humidity_amp": 5.0,
        "soil_ph_base": 7.0, "soil_ec_base": 1.5,
        "rainfall_prob": 0.0,
        "acoustic_events": [],
    },
    "underground_activity": {
        "title": "Animali nel sottosuolo",
        "description": "Possibile attività sotto terra: vibrazioni ripetute a bassa frequenza.",
        "soil_moisture_base": 34.0, "soil_moisture_amp": 2.0, "soil_moisture_drift": 0.0,
        "air_temp_base": 20.0, "air_temp_amp": 3.0,
        "air_humidity_base": 65.0, "air_humidity_amp": 4.0,
        "soil_ph_base": 6.7, "soil_ec_base": 1.1,
        "rainfall_prob": 0.05,
        "acoustic_events": [
            {"category": "repetitive_low_freq_pattern", "confidence_range": [0.55, 0.78],
             "evidence": {"band_hz": [60, 180], "periodicity_s": 1.2, "note": "solo un andamento, non una specie"}},
        ],
    },
    "bird_activity": {
        "title": "Uccelli sulle colture",
        "description": "Canti di uccelli ripetuti durante il giorno vicino al campo.",
        "soil_moisture_base": 36.0, "soil_moisture_amp": 2.5, "soil_moisture_drift": 0.0,
        "air_temp_base": 24.0, "air_temp_amp": 5.0,
        "air_humidity_base": 55.0, "air_humidity_amp": 7.0,
        "soil_ph_base": 6.8, "soil_ec_base": 1.2,
        "rainfall_prob": 0.03,
        "acoustic_events": [
            {"category": "bird_vocalization", "confidence_range": [0.6, 0.9],
             "evidence": {"band_hz": [2000, 8000], "note": "uccello generico; per la specie serve BirdNET"}},
        ],
    },
}


def list_scenarios() -> list[dict]:
    return [{"name": k, "title": v["title"], "description": v["description"]} for k, v in SCENARIOS.items()]


def get_scenario(name: str) -> dict:
    return SCENARIOS.get(name, SCENARIOS["healthy"])
