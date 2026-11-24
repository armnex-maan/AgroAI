from app.ml.agronomy import rotation as r
from app.ml.agronomy import rotation_planner as planner
from app.ml.agronomy import rotation_rules as rr


def _j(key, history, region, integrated=None, problems=()):
    return r.judge(r.BY_KEY[key], history, set(problems), None, region, integrated)


def test_rules_are_regional_and_never_borrowed_silently():
    # Emilia-Romagna: carrot needs 3 years -> binding
    er = _j("carrot", [["carrot"]], "emilia_romagna")
    assert er["verdict"] == "no" and any(x["level"] == "disciplinare" and x["source"]["id"] == "er_2023" for x in er["reasons"])
    # Puglia: no document read -> the Emilia-Romagna value is only a non-binding reference
    pu = _j("carrot", [["carrot"]], "puglia")
    assert pu["verdict"] != "no"
    ref = [x for x in pu["reasons"] if x["source"] and x["source"]["id"] == "er_2023"]
    assert ref and all(x["level"] == "buona_pratica" for x in ref) and "non vincolante" in ref[0]["text"]
    # Piemonte has its own tomato rule (no ristoppio) from its 2020 crop sheets
    pie = _j("tomato", [["tomato"], ["wheat"]], "piemonte")
    assert pie["verdict"] == "no" and any(x["source"] and x["source"]["id"] == "pie_2020_schede" for x in pie["reasons"])
    # Marche 2026 allows one tomato ristoppio
    assert _j("tomato", [["tomato"], ["wheat"]], "marche")["verdict"] != "no"


def test_guidelines_bind_only_farms_in_the_scheme():
    assert _j("carrot", [["carrot"]], "emilia_romagna", integrated=True)["verdict"] == "no"
    free = _j("carrot", [["carrot"]], "emilia_romagna", integrated=False)
    assert free["verdict"] != "no" and any("solo per chi aderisce" in x["text"] for x in free["reasons"])


def test_several_crops_in_one_season_are_all_checked():
    j = _j("pepper", [["lettuce", "tomato"]], "emilia_romagna")
    assert j["verdict"] == "no"  # tomato was there too, even if lettuce was the first crop listed


def test_coverage_and_rule_sources():
    assert rr.coverage("emilia_romagna")["level"] == "crops"
    assert rr.coverage("lazio")["level"] == "general"
    assert rr.coverage("sicilia")["level"] == "none"
    rules = rr.all_rules("piemonte")
    assert rules[0]["type"] == "obbligatoria" and "BCAA 7" in rules[0]["text"]
    for x in rules:
        assert x["source"]["url"].startswith("http") and "year" in x


def test_planner_assigns_each_bed_and_respects_history():
    secs = [{"id": "a", "name": "Aiuola 1", "kind": "bed", "w": 4, "h": 10},
            {"id": "b", "name": "Aiuola 2", "kind": "bed", "w": 4, "h": 10},
            {"id": "p", "name": "Sentiero", "kind": "path", "w": 1, "h": 10}]
    hist = {"a": [["tomato"], ["bean"]], "b": [["lettuce"], ["onion"]]}
    out = planner.plan_plot(secs, hist, [], [2027, 2028, 2029, 2030], problems=set(), soil=None,
                            region="emilia_romagna", integrated=True, wanted={"tomato": 40, "bean": 0})
    y1 = out["years"][0]["assignments"]
    assert {a["section_id"] for a in y1} == {"a", "b"}  # paths are not planted
    bed_a = next(a for a in y1 if a["section_id"] == "a")
    assert r.BY_KEY[bed_a["crop"]].family != "solanacee"
    assert any(a["crop"] == "tomato" for a in y1 if a["section_id"] == "b")  # the wish goes where it is allowed
    for year in out["years"]:  # never the same family twice in a row in a bed
        for a in year["assignments"]:
            assert a["verdict"] != "no"
    assert out["years"][0]["area_by_crop"]


def test_api_full_flow(client):
    assert client.put("/api/v1/rotation/farm", json={"region": "emilia_romagna", "province": "Bologna",
                                                    "municipality": "Bologna"}).status_code == 200
    assert client.put("/api/v1/rotation/farm", json={"region": "atlantide"}).status_code == 400
    p = client.post("/api/v1/rotation/plots", json={"name": "Orto", "width_m": 10, "length_m": 20,
                                                   "exposure": "full_sun",
                                                   "profile": {"texture": "mixed", "problems": ["wilt"]}}).json()
    assert p["area_m2"] == 200
    lay = client.put(f"/api/v1/rotation/plots/{p['id']}/layout", json={
        "width_m": 10, "length_m": 20, "orientation_deg": 0, "sections": [
            {"name": "A", "kind": "bed", "x": 0, "y": 0, "w": 4.5, "h": 20},
            {"name": "Sentiero", "kind": "path", "x": 4.5, "y": 0, "w": 1, "h": 20},
            {"name": "B", "kind": "bed", "x": 5.5, "y": 0, "w": 4.5, "h": 20}]}).json()
    a, b = [s["id"] for s in lay["sections"] if s["kind"] == "bed"]
    from app.api.v1.rotation import last_season_year
    y = last_season_year()
    client.put(f"/api/v1/rotation/plots/{p['id']}/history", json={"year": y, "status": "crop", "crops": [
        {"crop": "tomato", "section_id": a, "area_m2": 90, "diseases": "avvizzimento"},
        {"crop": "lettuce", "section_id": b}]})
    r2 = client.put(f"/api/v1/rotation/plots/{p['id']}/history", json={"year": y - 1, "status": "unknown"}).json()
    assert {h["status"] for h in r2["history"]} == {"crop", "unknown"}
    assert client.put(f"/api/v1/rotation/plots/{p['id']}/history",
                      json={"year": y - 2, "status": "crop", "crops": []}).status_code == 400
    plan = client.post(f"/api/v1/rotation/plots/{p['id']}/plan", json={"wanted": {"pepper": 0, "bean": 0},
                                                                        "integrated": True}).json()
    assert [yy["year"] for yy in plan["years"]] == [y + 1, y + 2, y + 3, y + 4]
    first = {x["section_id"]: x for x in plan["years"][0]["assignments"]}
    assert first[a]["crop"] != "pepper"  # tomato + wilt in bed A
    assert any("meno di 3 anni" in n for n in plan["notes"])
    chk = client.post(f"/api/v1/rotation/plots/{p['id']}/check",
                      json={"section_id": a, "crop": "eggplant", "year": y + 1}).json()
    assert chk["verdict"] == "no"
    saved = client.put(f"/api/v1/rotation/plots/{p['id']}/plans/{y + 1}",
                       json={"assignments": plan["years"][0]["assignments"]}).json()
    assert saved["plans"][0]["year"] == y + 1
    assert len(client.get("/api/v1/rotation/regions").json()) == 20
    assert client.get("/api/v1/rotation/calendar").json()["crops"]["tomato"]["trapianto"]
    assert client.delete(f"/api/v1/rotation/plots/{p['id']}").status_code == 204
