def test_list_and_activate_scenarios(client):
    r = client.get("/api/v1/simulation/scenarios")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert {"healthy", "water_stress", "underground_activity", "bird_activity"} <= names

    r = client.post("/api/v1/simulation/scenarios/activate", json={"name": "water_stress"})
    assert r.status_code == 200
    body = r.json()
    assert any(s["name"] == "water_stress" and s["active"] for s in body)
