def test_home_summary_without_data(client, monkeypatch):
    from app.api.v1 import home

    async def no_weather(lat, lon):
        return None
    monkeypatch.setattr(home, "weather_today", no_weather)
    body = client.get("/api/v1/home").json()
    assert set(body) >= {"soil_moisture", "air_temperature", "soil_ph", "weather", "tip", "alerts", "demo"}
    assert body["tip"]["title"]


def test_tip_uses_rain_forecast():
    from app.api.v1.home import _tip
    soil = {"status": "Secco", "tone": "warn"}
    assert "pioggia" in _tip(soil, None, {"rain_mm": 8, "rain_prob": 90})["title"]
    assert _tip(soil, None, {"rain_mm": 0, "rain_prob": 0})["title"] == "Il terreno è secco."
    assert "Collega" in _tip(None, None, None)["title"]
