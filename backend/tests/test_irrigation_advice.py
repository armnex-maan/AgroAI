"""Irrigation advice: Kc from FAO-56 Table 12, monthly need from the local climate, suggestion vs declared system,
new farm elements (greenhouse, nets, fences, equipment)."""
from app.ml.agronomy import crop_heights, irrigation

API = "/api/v1/rotation"
LON, LAT = 11.71, 44.35


def _climate(et0=150.0, rain=50.0):
    return {"monthly": [{"month": m, "t_mean": 20, "precip_mm": rain, "et0_mm": et0} for m in range(1, 13)],
            "source": "test", "period": "2020-2024"}


def test_kc_table_covers_the_crops_with_a_fao_height():
    missing = [k for k in crop_heights.HEIGHT_M if k not in irrigation.KC]
    assert missing == []
    assert irrigation.KC["tomato"] == (0.6, 1.15, 0.80) and irrigation.KC["pea"][1] == 1.15
    assert irrigation.KC_SOURCE["url"].startswith("https://www.fao.org/")


def test_monthly_need_follows_kc_stages_and_rain():
    cal = {"trapianto": [5], "raccolta": [7, 8, 9]}           # May .. September = 5 months
    a = irrigation.advice("tomato", "Pomodoro", "frutto", "bed", 100, cal, _climate(), "drip")
    assert a["season"] == [5, 6, 7, 8, 9]
    stages = [m["stage"] for m in a["months"]]
    assert stages[0] == "ini" and "mid" in stages and stages[-1] == "end"
    may = a["months"][0]
    assert may["kc"] == 0.6 and may["etc_mm"] == 90.0 and may["net_mm"] == 50.0       # 0.6*150 - 0.8*50
    assert may["liters_week"] == round(50 * 100 / 4.35)
    assert a["peak"]["kc"] == 1.15 and a["efficiency"]["value"] == 0.9
    assert a["system"]["suggested"] == "drip" and a["system"]["level"] == "suggerimento"
    wet = irrigation.advice("tomato", "Pomodoro", "frutto", "bed", 100, cal, _climate(et0=40, rain=200), None)
    assert all(m["net_mm"] == 0 for m in wet["months"]) and wet["peak"] is None       # rain covers the need
    none = irrigation.advice("tomato", "Pomodoro", "frutto", "bed", 100, cal, None, None)
    assert none["kc"] and "net_mm" not in none["months"][0]                            # no climate: Kc only
    assert irrigation.advice("wheat", "Frumento", "cereale", "bed", 100, cal, None, None)["system"]["suggested"] == "none"


def test_endpoint_without_location_gives_kc_and_says_why(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna", "latitude": None, "longitude": None})
    p = client.post(f"{API}/plots", json={"name": "Orto irriguo", "width_m": 10, "length_m": 10}).json()
    r = client.post(f"{API}/plots/{p['id']}/irrigation", json={"year": 2027, "assignments": [
        {"section_id": None, "crop": "pepper", "area_m2": 100}, {"section_id": None, "crop": "nonsense", "area_m2": 5}]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["beds"]) == 1 and d["beds"][0]["kc"] == [0.6, 1.05, 0.9]
    assert len(d["sources"]) == 2 and any("80%" in n for n in d["notes"])


def test_new_farm_elements(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna"})
    sq = [[LON, LAT], [LON + 0.0003, LAT], [LON + 0.0003, LAT - 0.0002], [LON, LAT - 0.0002], [LON, LAT]]
    ok = [
        {"kind": "greenhouse", "name": "Serra", "geometry": {"type": "Polygon", "coordinates": [sq]}, "props": {"type": "tunnel", "height_m": 3}},
        {"kind": "net", "name": "Rete", "geometry": {"type": "Polygon", "coordinates": [sq]}, "props": {"type": "antigrandine"}},
        {"kind": "fence", "name": "Recinto", "geometry": {"type": "LineString", "coordinates": sq[:3]}, "props": {"type": "staccionata"}},
        {"kind": "equipment", "name": "Trattore", "geometry": {"type": "Point", "coordinates": [LON, LAT]}, "props": {"type": "trattore", "model": "x" * 300}},
        {"kind": "beehive", "name": "Arnie", "geometry": {"type": "Point", "coordinates": [LON, LAT]}, "props": {"count": 4}},
        {"kind": "compost", "name": "Compost", "geometry": {"type": "Point", "coordinates": [LON, LAT]}, "props": {}},
        {"kind": "solar", "name": "FV", "geometry": {"type": "Polygon", "coordinates": [sq]}, "props": {"power_kw": 6}},
    ]
    ids = []
    for body in ok:
        r = client.post(f"{API}/features", json=body)
        assert r.status_code == 201, (body["kind"], r.text)
        ids.append(r.json()["id"])
    assert len(client.post(f"{API}/features", json=ok[3]).json()["props"]["model"]) == 120
    assert client.post(f"{API}/features", json={**ok[3], "props": {"type": "astronave"}}).status_code == 400
    for i in ids:
        client.delete(f"{API}/features/{i}")
