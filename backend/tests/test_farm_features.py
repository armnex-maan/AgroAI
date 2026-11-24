"""Farm elements of the Visual Farm Planner: validation, measures, FAO heights, update, delete."""
API = "/api/v1/rotation"
LON, LAT = 11.71, 44.35


def _sq(d=0.0005):
    return [[LON, LAT], [LON + d, LAT], [LON + d, LAT - d], [LON, LAT - d], [LON, LAT]]


def test_features_crud_and_measures(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna"})
    b = client.post(f"{API}/features", json={"kind": "building", "name": "Casale", "geometry": {"type": "Point", "coordinates": [LON, LAT]},
                                            "props": {"type": "casale", "width_m": 12, "length_m": 18, "floors": 2, "unknown": 5}})
    assert b.status_code == 201, b.text
    assert b.json()["props"] == {"type": "casale", "width_m": 12, "length_m": 18, "floors": 2}   # unknown keys dropped
    road = client.post(f"{API}/features", json={"kind": "road", "name": "Strada", "geometry": {"type": "LineString",
                       "coordinates": [[LON, LAT], [LON + 0.001, LAT]]}, "props": {"width_m": 4, "surface": "ghiaia"}}).json()
    assert 70 < road["length_m"] < 90                                    # 0.001 deg of longitude at 44.35 N ~ 79.6 m
    orch = client.post(f"{API}/features", json={"kind": "orchard", "name": "Meleto", "geometry": {"type": "Polygon", "coordinates": [_sq()]},
                       "props": {"species": "apple"}}).json()
    assert orch["height_m"] == [4, 4] and orch["species_name"] == "Melo" and orch["area_m2"] > 2000
    assert "row_spacing_m" not in orch["props"]                            # spacing not given: never invented
    listed = client.get(f"{API}/features").json()
    assert {f["kind"] for f in listed["features"]} >= {"building", "road", "orchard"}
    assert listed["trees"]["olive"]["height_m"] == [3, 5] and listed["height_source"]["url"].startswith("https://www.fao.org/")
    up = client.put(f"{API}/features/{orch['id']}", json={"props": {"species": "apple", "row_spacing_m": 4, "tree_spacing_m": 1.5}}).json()
    assert up["props"]["row_spacing_m"] == 4
    assert client.delete(f"{API}/features/{b.json()['id']}").status_code == 204
    assert client.put(f"{API}/features/{b.json()['id']}", json={"name": "x"}).status_code == 404


def test_feature_validation(client):
    bad = [
        {"kind": "castle", "name": "x", "geometry": {"type": "Point", "coordinates": [LON, LAT]}},
        {"kind": "building", "name": "x", "geometry": {"type": "LineString", "coordinates": [[LON, LAT], [LON, LAT]]}},
        {"kind": "road", "name": "x", "geometry": {"type": "LineString", "coordinates": [[LON, LAT]]}},
        {"kind": "tank", "name": "x", "geometry": {"type": "Point", "coordinates": [500, LAT]}},
        {"kind": "tank", "name": "x", "geometry": {"type": "Point", "coordinates": [LON, LAT]}, "props": {"diameter_m": 300}},
        {"kind": "orchard", "name": "x", "geometry": {"type": "Polygon", "coordinates": [_sq()]}, "props": {"species": "grape_wine"}},
        {"kind": "pond", "name": "x", "geometry": {"type": "Polygon", "coordinates": [[[LON, LAT], [LON, LAT]]]}},
    ]
    for body in bad:
        assert client.post(f"{API}/features", json=body).status_code == 400, body
