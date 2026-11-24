"""Realistic sensor simulator.

Models diurnal cycles, drift under water stress, rain events, occasional dropouts.
All output carries source='simulation' upstream.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Dict

from app.simulation.scenarios import get_scenario

PHYSICAL_RANGE = {
    "soil_moisture": (0.0, 100.0), "air_humidity": (0.0, 100.0), "rainfall": (0.0, None),
    "light_intensity": (0.0, None), "wind_speed": (0.0, None), "soil_ec": (0.0, None), "soil_ph": (0.0, 14.0),
}


class SimulationEngine:
    def __init__(self, scenario: str = "healthy", seed: int | None = None):
        self.scenario_name = scenario
        self.scenario = get_scenario(scenario)
        self.rng = random.Random(seed)
        self._drift_state: dict[str, float] = {}

    def set_scenario(self, name: str) -> None:
        self.scenario_name = name
        self.scenario = get_scenario(name)
        self._drift_state.clear()

    def _diurnal(self, base: float, amp: float, now: datetime) -> float:
        hour = now.hour + now.minute / 60.0
        return base + amp * math.sin((hour - 6) / 24.0 * 2 * math.pi)

    def _drift(self, key: str, per_step: float) -> float:
        cur = self._drift_state.get(key, 0.0) + per_step
        self._drift_state[key] = cur
        return cur

    def sample(self, descriptor) -> Dict[str, dict]:
        s = self.scenario
        now = datetime.now(timezone.utc)

        values: Dict[str, dict] = {}
        requested_types = {sp["type"] for sp in descriptor.sensors} if descriptor.sensors else set()

        def _add(stype: str, value: float, unit: str) -> None:
            if requested_types and stype not in requested_types:
                return
            # occasional dropout (1%)
            if self.rng.random() < 0.01:
                return
            # add light noise, but never produce physically impossible values (negative rain, humidity > 100%)
            if value != 0.0:
                value += self.rng.gauss(0, max(0.02 * abs(value), 0.1))
            lo, hi = PHYSICAL_RANGE.get(stype, (None, None))
            if lo is not None:
                value = max(lo, value)
            if hi is not None:
                value = min(hi, value)
            values[stype] = {"value": round(value, 2), "unit": unit, "quality": 1.0}

        sm = self._diurnal(s["soil_moisture_base"], s["soil_moisture_amp"], now)
        sm += self._drift("soil_moisture", s["soil_moisture_drift"])
        sm = max(1.0, min(100.0, sm))
        _add("soil_moisture", sm, "%")

        _add("soil_temperature", self._diurnal(s["air_temp_base"] - 3, 2.0, now), "C")
        _add("air_temperature", self._diurnal(s["air_temp_base"], s["air_temp_amp"], now), "C")
        _add("air_humidity", self._diurnal(s["air_humidity_base"], s["air_humidity_amp"], now), "%")
        _add("soil_ph", s["soil_ph_base"] + self.rng.gauss(0, 0.05), "pH")
        _add("soil_ec", s["soil_ec_base"] + self.rng.gauss(0, 0.05), "mS/cm")

        if self.rng.random() < s["rainfall_prob"]:
            _add("rainfall", self.rng.uniform(0.2, 3.0), "mm")
        else:
            _add("rainfall", 0.0, "mm")

        _add("light_intensity", max(0.0, self._diurnal(40000, 40000, now)), "lux")
        _add("wind_speed", max(0.0, self.rng.gauss(2.5, 1.0)), "m/s")

        return values
