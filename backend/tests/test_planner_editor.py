"""Phase 4 – interactive editor: sections moved/resized from the 3D view keep their id and history, rows declared by
the farmer are stored and validated, sprinklers are farm elements."""
API = "/api/v1/rotation"
LON, LAT = 11.71, 44.35


def _plot(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna"})
    p = client.post(f"{API}/plots", json={"name": "Orto", "width_m": 20, "length_m": 30}).json()
    lay = client.put(f"{API}/plots/{p['id']}/layout", json={"width_m": 20, "length_m": 30, "sections": [
        {"name": "Aiuola 1", "kind": "bed", "x": 0, "y": 0, "w": 8, "h": 30},
        {"name": "Aiuola 2", "kind": "bed", "x": 10, "y": 0, "w": 10, "h": 30}]}).json()
    return p["id"], lay["sections"]


def test_rows_are_stored_counted_and_kept_when_the_section_moves(client):
    pid, secs = _plot(client)
    s1, s2 = secs
    client.put(f"{API}/plots/{pid}/history", json={"year": 2026, "status": "crop", "crops": [{"crop": "tomato", "section_id": s1["id"]}]})
    moved = {**s1, "x": 1, "y": 2, "w": 6, "h": 25, "row_spacing_m": 0.8, "plant_spacing_m": 0.4, "row_dir": "y"}
    out = client.put(f"{API}/plots/{pid}/layout", json={"width_m": 20, "length_m": 30, "sections": [moved, s2]})
    assert out.status_code == 200, out.text
    a = next(s for s in out.json()["sections"] if s["id"] == s1["id"])          # same id: history follows the bed
    assert (a["x"], a["y"], a["w"], a["h"]) == (1, 2, 6, 25)
    assert a["row_spacing_m"] == 0.8 and a["plant_spacing_m"] == 0.4 and a["row_dir"] == "y"
    assert a["rows"] == 7                                                        # 6 m across / 0.8 m
    b = next(s for s in out.json()["sections"] if s["id"] == s2["id"])
    assert b["row_spacing_m"] is None and "rows" not in b                        # not declared: never invented
    farm = client.get(f"{API}/farm").json()
    hist = next(p for p in farm["plots"] if p["id"] == pid)["history"]
    assert hist and hist[0]["section_id"] == s1["id"]


def test_sections_are_clamped_inside_the_plot_and_rows_validated(client):
    pid, secs = _plot(client)
    out = client.put(f"{API}/plots/{pid}/layout", json={"width_m": 20, "length_m": 30, "sections": [
        {**secs[0], "x": 15, "y": 28, "w": 10, "h": 10}]}).json()
    s = out["sections"][0]
    assert s["x"] + s["w"] <= 20 and s["y"] + s["h"] <= 30
    for bad in ({"row_spacing_m": 0}, {"row_spacing_m": 50}, {"row_dir": "z"}, {"plant_spacing_m": -1}):
        r = client.put(f"{API}/plots/{pid}/layout", json={"width_m": 20, "length_m": 30, "sections": [{**secs[0], **bad}]})
        assert r.status_code == 422, bad


def test_sprinkler_is_a_farm_element(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna"})
    ok = client.post(f"{API}/features", json={"kind": "sprinkler", "name": "Irrigatore 1", "geometry": {"type": "Point", "coordinates": [LON, LAT]},
                                             "props": {"type": "dinamico", "radius_m": 12}})
    assert ok.status_code == 201 and ok.json()["props"] == {"type": "dinamico", "radius_m": 12}
    assert "flow_l_h" not in ok.json()["props"]                                  # flow not given: stays empty
    moved = client.put(f"{API}/features/{ok.json()['id']}", json={"geometry": {"type": "Point", "coordinates": [LON + 0.0001, LAT]}})
    assert moved.status_code == 200 and moved.json()["geometry"]["coordinates"][0] == LON + 0.0001
    bad = client.post(f"{API}/features", json={"kind": "sprinkler", "name": "x", "geometry": {"type": "Point", "coordinates": [LON, LAT]},
                                              "props": {"radius_m": 500}})
    assert bad.status_code == 400
