"""Plot traced on the satellite map, and ecosystem suggestions (independent from vision)."""
import math

from app.ml.agronomy import ecosystems, geo

API = "/api/v1/rotation"


def _square(lat=44.35, lon=11.71, side=100.0):
    dlat = side / (math.pi * geo.R / 180)
    dlon = dlat / math.cos(math.radians(lat))
    return [[lon, lat], [lon + dlon, lat], [lon + dlon, lat - dlat], [lon, lat - dlat]]


def test_area_and_local_outline_of_a_traced_plot():
    ring = _square()
    assert abs(geo.area_m2(ring) - 10000) < 50          # 1 ha within 0.5%
    loc = geo.to_local(ring)
    assert abs(loc["width_m"] - 100) < 0.5 and abs(loc["length_m"] - 100) < 0.5
    back = geo.from_local(loc["outline"], loc["origin"], loc["k"])
    assert all(abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6 for a, b in zip(back, ring))
    assert abs(geo.perimeter_m(ring) - 400) < 2
    tri = ring[:3]
    assert abs(geo.area_m2(tri) - 5000) < 30
    for bad in ([[0, 0], [1, 1]], [[0, 0], [200, 0], [0, 1]]):
        try:
            geo.area_m2(bad)
            assert False
        except ValueError:
            pass


def test_boundary_api_sets_area_shape_and_follows_editor_changes(client):
    p = client.post(f"{API}/plots", json={"name": "Dalla mappa"}).json()
    res = client.put(f"{API}/plots/{p['id']}/boundary", json={"ring": _square(side=50) + [_square(side=50)[0]]})
    assert res.status_code == 200, res.text
    out = res.json()
    assert abs(out["area_m2"] - 2500) < 15 and out["shape"] == "irregular" and len(out["outline"]) == 4
    assert out["polygon"]["type"] == "Polygon" and abs(out["perimeter_m"] - 200) < 2
    # the editor cuts the plot in half: the map polygon and the area follow
    half = client.put(f"{API}/plots/{p['id']}/layout", json={
        "width_m": out["width_m"], "length_m": out["length_m"], "shape": "irregular",
        "outline": [[0, 0], [out["width_m"], 0], [0, out["length_m"]]], "sections": []}).json()
    assert abs(half["area_m2"] - 1250) < 10 and len(half["polygon"]["coordinates"][0]) == 4
    assert client.put(f"{API}/plots/{p['id']}/boundary", json={"ring": [[0, 0], [0, 0], [0, 0]]}).status_code == 400
    assert client.put(f"{API}/plots/{p['id']}/boundary", json={"ring": [[500, 0], [1, 1], [2, 2]]}).status_code == 400


def test_ecosystems_follow_the_answers_and_cite_sources(client):
    p = client.post(f"{API}/plots", json={"name": "Orto eco", "width_m": 10, "length_m": 10,
                                          "profile": {"water": "none", "manure": "no",
                                                      "goals": {"wanted": {"zucchini": 0}}}}).json()
    items = {x["key"]: x for x in client.get(f"{API}/plots/{p['id']}/ecosystems").json()["items"]}
    assert not items["aquaponics"]["fit"]                     # no water -> no fish
    assert items["hedges"]["fit"] and any("impollinatori" in w for w in items["hedges"]["why"])
    assert not items["rice_fish"]["fit"]                      # rice is not in the rotation yet: information only
    assert any("pesci" in t and "NON" in t for t in items["pond"]["pairs"])  # fish and amphibians do not mix
    for x in items.values():
        assert x["sources"] and all(s["url"].startswith("https://") for s in x["sources"])
        assert x["level"] == "buona_pratica"
    assert any("ASL" in c for c in items["animals"]["cautions"])


def test_aquaponics_sizing_matches_the_fao_example(client):
    # FAO 2014: 4 m2 of leafy greens ~ 200 g feed/day ~ 10-20 kg of fish, at most 20 kg per 1000 L
    a = ecosystems.aquaponics(4)
    assert a["feed_g_day"] == [160, 200] and a["fish_kg"][1] == 20 and a["water_l_min"] == 1000
    assert ecosystems.aquaponics(4, fruiting=True)["feed_g_day"] == [200, 320]
    assert client.get(f"{API}/aquaponics", params={"bed_m2": 0}).status_code == 400
    assert {f["key"] for f in client.get(f"{API}/aquaponics", params={"bed_m2": 2}).json()["fish"]} == {"carp", "trout", "tilapia"}


def test_auto_layout_gives_equal_real_areas_on_an_irregular_plot(client):
    p = client.post(f"{API}/plots", json={"name": "Irregolare", "profile": {"goals": {"wanted": {"zucchini": 0, "bean": 0}}}}).json()
    ring = _square(side=200)
    ring[2] = [ring[2][0], (ring[1][1] + ring[2][1]) / 2]          # east side shorter: a trapezoid
    client.put(f"{API}/plots/{p['id']}/boundary", json={"ring": ring})
    out = client.post(f"{API}/plots/{p['id']}/auto-layout", json={}).json()
    beds = [s for s in out["sections"] if s["kind"] == "bed"]
    paths = [s for s in out["sections"] if s["kind"] == "path"]
    assert len(beds) == 4 and len(paths) == 3 and out["auto"]["path_m"] == 3.0   # 2 wanted crops + 2, field paths
    areas = [b["area_m2"] for b in beds]
    assert max(areas) - min(areas) < 0.02 * max(areas)            # same real area...
    assert len({round(b["w"]) for b in beds}) > 1                # ...with different widths
    assert abs(sum(areas) + sum(x["area_m2"] for x in paths) - out["area_m2"]) < 0.01 * out["area_m2"]
    plan = client.post(f"{API}/plots/{p['id']}/plan", json={"wanted": {"zucchini": 0, "bean": 0}}).json()
    assert {a["section_id"] for a in plan["years"][0]["assignments"]} == {b["id"] for b in beds}
    small = client.post(f"{API}/plots", json={"name": "Orto", "width_m": 6, "length_m": 10}).json()
    o2 = client.post(f"{API}/plots/{small['id']}/auto-layout", json={"parts": 3}).json()
    assert o2["auto"]["path_m"] == 0.6 and [s["name"] for s in o2["sections"] if s["kind"] == "bed"] == ["Aiuola 1", "Aiuola 2", "Aiuola 3"]



def test_crop_heights_come_from_fao56_and_are_never_invented(client):
    from app.ml.agronomy import crop_heights, rotation
    farm = client.get(f"{API}/farm").json()
    by = {c["key"]: c for c in farm["crops"]}
    assert by["maize"]["height_m"] == [2.0, 2.0] and by["tomato"]["height_m"] == [0.6, 0.6]
    assert by["rocket"]["height_m"] is None            # not in FAO-56 Table 12: no made-up value
    assert farm["height_source"]["url"].startswith("https://www.fao.org/")
    assert set(crop_heights.HEIGHT_M) <= set(rotation.BY_KEY)


def test_greenhouse_is_a_growing_section(client):
    p = client.post(f"{API}/plots", json={"name": "Con serra", "width_m": 20, "length_m": 20}).json()
    out = client.put(f"{API}/plots/{p['id']}/layout", json={"width_m": 20, "length_m": 20, "sections": [
        {"name": "Serra 1", "kind": "greenhouse", "x": 0, "y": 0, "w": 8, "h": 20},
        {"name": "Aiuola 1", "kind": "bed", "x": 10, "y": 0, "w": 8, "h": 20}]}).json()
    plan = client.post(f"{API}/plots/{p['id']}/plan", json={}).json()
    assert {a["section"] for a in plan["years"][0]["assignments"]} == {"Serra 1", "Aiuola 1"}
    assert len(out["sections"]) == 2
