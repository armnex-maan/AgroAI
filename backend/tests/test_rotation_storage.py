"""Crop rotation planner: questionnaire storage, history, plots, rules, multi-year plans, layout, save/load.
Everything goes through the rotation API and its own tables (no vision code involved)."""
from app.api.v1.rotation import last_season_year
from app.ml.agronomy import rotation as r
from app.ml.agronomy import rotation_rules as rr
from app.models import PlannedCrop, PlotConditions, PlotProblem, RotationRule
from app.services import rotation_store

API = "/api/v1/rotation"
Y = last_season_year()


def _plot(client, name="Orto", w=10, l=20, profile=None):
    body = {"name": name, "width_m": w, "length_m": l, "exposure": "full_sun"}
    if profile is not None:
        body["profile"] = profile
    res = client.post(f"{API}/plots", json=body)
    assert res.status_code == 201
    return res.json()


def _beds(client, pid, n=2, w=10, l=20):
    bw = (w - (n - 1)) / n
    secs, x = [], 0.0
    for i in range(n):
        secs.append({"name": f"Aiuola {i + 1}", "kind": "bed", "x": x, "y": 0, "w": bw, "h": l})
        x += bw
        if i < n - 1:
            secs.append({"name": "Sentiero", "kind": "path", "x": x, "y": 0, "w": 1, "h": l})
            x += 1
    out = client.put(f"{API}/plots/{pid}/layout", json={"width_m": w, "length_m": l, "sections": secs}).json()
    return [s["id"] for s in out["sections"] if s["kind"] == "bed"], out


def _season(client, pid, year, status="crop", crops=()):
    res = client.put(f"{API}/plots/{pid}/history", json={"year": year, "status": status,
                                                         "crops": [c if isinstance(c, dict) else {"crop": c} for c in crops]})
    assert res.status_code == 200, res.text
    return res.json()


def test_questionnaire_answers_go_to_their_tables(client, db):
    client.put(f"{API}/farm", json={"region": "emilia_romagna", "province": "Bologna", "municipality": "Imola"})
    p = _plot(client, profile={"texture": "clay", "fertility": "low", "compaction": "medium", "water": "limited",
                               "irrigation": "drip", "manure": "yearly", "cover": "yes", "problems": ["wilt", "nematodes"],
                               "other_problem": "lumache", "goals": {"wanted": {"zucchini": 0}, "purpose": "family"},
                               "fertility_bad_value": "x"})
    cond = db.get(PlotConditions, p["id"])
    assert (cond.texture, cond.irrigation, cond.soil_state) == ("clay", "drip", "tired")
    probs = {x.problem: x.description for x in db.query(PlotProblem).filter_by(field_id=p["id"])}
    assert set(probs) == {"wilt", "nematodes", "other"} and probs["other"] == "lumache"
    # the UI gets the same profile back, goals included, and only valid answers are kept
    prof = p["profile"]
    assert prof["texture"] == "clay" and set(prof["problems"]) == {"wilt", "nematodes"}
    assert prof["goals"]["wanted"] == {"zucchini": 0} and prof["other_problem"] == "lumache"
    bad = client.put(f"{API}/plots/{p['id']}", json={"name": "Orto", "width_m": 10, "length_m": 20,
                                                     "profile": {"texture": "lava", "problems": ["unicorns"]}}).json()
    assert "texture" not in bad["profile"] and bad["profile"]["problems"] == []
    assert not db.query(PlotProblem).filter_by(field_id=p["id"]).count()


def test_incomplete_history_is_never_filled_in(client):
    p = _plot(client)
    _season(client, p["id"], Y, crops=["tomato"])
    _season(client, p["id"], Y - 1, status="unknown")
    out = client.get(f"{API}/farm").json()
    hist = next(x for x in out["plots"] if x["id"] == p["id"])["history"]
    assert sorted(h["year"] for h in hist) == [Y - 1, Y]  # years not answered have no record at all
    plan = client.post(f"{API}/plots/{p['id']}/plan", json={"integrated": True}).json()
    assert any("meno di 3 anni" in n for n in plan["notes"])
    # an unknown year does not count as a break: tomato needs 2 years of other crops, one unknown is not enough
    j = r.judge(r.BY_KEY["tomato"], [None, ["tomato"]], set(), None, "emilia_romagna", True)
    assert j["verdict"] != "ok"


def test_several_plots_are_kept_apart(client):
    a, b = _plot(client, "Campo A"), _plot(client, "Campo B")
    _season(client, a["id"], Y, crops=["tomato"])
    _season(client, b["id"], Y, crops=["wheat"])
    chk_a = client.post(f"{API}/plots/{a['id']}/check", json={"crop": "pepper", "year": Y + 1, "integrated": True}).json()
    chk_b = client.post(f"{API}/plots/{b['id']}/check", json={"crop": "pepper", "year": Y + 1, "integrated": True}).json()
    assert chk_a["verdict"] == "no" and chk_b["verdict"] != "no"
    plan_b = client.post(f"{API}/plots/{b['id']}/plan", json={}).json()
    assert plan_b["plot_id"] == b["id"]
    assert {x["crop"] for x in plan_b["current"]["assignments"]} == {"wheat"}


def test_same_family_is_not_repeated():
    for prev, nxt in (("tomato", "eggplant"), ("cabbage", "rocket"), ("zucchini", "melon")):
        if prev in r.BY_KEY and nxt in r.BY_KEY and r.BY_KEY[prev].family == r.BY_KEY[nxt].family:
            j = r.judge(r.BY_KEY[nxt], [[prev]], set(), None, "emilia_romagna", True)
            assert j["verdict"] != "ok", (prev, nxt)
            assert any(r.BY_KEY[prev].family in x["text"] for x in j["reasons"])


def test_return_intervals_follow_the_regional_value():
    carrot = r.BY_KEY["carrot"]
    gap = rr.er_rule(carrot)["gap"]
    assert gap == 3
    other = [["lettuce"], ["bean"], ["onion"]]
    too_soon = r.judge(carrot, other[: gap - 1] + [["carrot"]], set(), None, "emilia_romagna", True)
    in_time = r.judge(carrot, other[:gap] + [["carrot"]], set(), None, "emilia_romagna", True)
    assert too_soon["verdict"] == "no" and in_time["verdict"] != "no"


def test_persistent_soil_diseases_weigh_on_sensitive_families(client):
    sick = _plot(client, "Malato", profile={"problems": ["wilt"]})
    sane = _plot(client, "Sano", profile={"problems": []})
    for p in (sick, sane):
        _season(client, p["id"], Y, crops=["wheat"])
    a = client.post(f"{API}/plots/{sick['id']}/check", json={"crop": "zucchini", "year": Y + 1}).json()
    b = client.post(f"{API}/plots/{sane['id']}/check", json={"crop": "zucchini", "year": Y + 1}).json()
    assert a["score"] < b["score"]
    assert any("appassiscono" in x["text"] for x in a["reasons"])
    # a soil problem is good practice, never presented as a legal obligation
    assert all(x["level"] != "obbligatoria" for x in a["reasons"])


def test_regional_rules_and_sources_are_stored_with_their_origin(client, db):
    rotation_store.sync_rules(db)
    res = client.get(f"{API}/sources", params={"region": "piemonte"}).json()
    assert res["rules"] and all(x["region"] in ("piemonte", "*") for x in res["rules"])
    tomato = next(x for x in res["rules"] if x["crop"] == "tomato")
    assert tomato["source"]["id"] == "pie_2020_schede" and tomato["year"] == 2020 and tomato["source"]["url"].startswith("http")
    assert any(x["level"] == "obbligatoria" and x["region"] == "*" for x in res["rules"])
    # only documents actually read: no rule for a region without documents
    assert not db.query(RotationRule).filter(RotationRule.region == "sicilia").count()
    # every stored rule has source, region, year and level; only the EU rule is "obbligatoria"
    for row in db.query(RotationRule):
        assert row.source_id and row.region and row.year and row.text
        assert (row.level == "obbligatoria") == (row.source_id == "eu_gaec7")
    # sync is idempotent
    n = db.query(RotationRule).count()
    rotation_store.sync_rules(db)
    assert db.query(RotationRule).count() == n


def test_multi_year_plan_rotates_families_in_each_bed(client):
    p = _plot(client)
    beds, _ = _beds(client, p["id"], n=3)
    _season(client, p["id"], Y, crops=[{"crop": "tomato", "section_id": beds[0]}, {"crop": "bean", "section_id": beds[1]},
                                       {"crop": "lettuce", "section_id": beds[2]}])
    plan = client.post(f"{API}/plots/{p['id']}/plan", json={"years": 4, "integrated": True,
                                                            "wanted": {"zucchini": 0, "onion": 0}}).json()
    assert [y["year"] for y in plan["years"]] == [Y + 1, Y + 2, Y + 3, Y + 4]
    last = {beds[0]: "solanacee", beds[1]: "leguminose", beds[2]: "composite"}
    for y in plan["years"]:
        assert {a["section_id"] for a in y["assignments"]} == set(beds)
        for a in y["assignments"]:
            assert a["verdict"] != "no"
            if a["family"]:
                assert a["family"] != last[a["section_id"]]
            last[a["section_id"]] = a["family"] or last[a["section_id"]]
            assert a["reasons"][0]["level"] == "suggerimento"  # AGROAI's choice is labelled as a suggestion


def test_layout_split_clamps_and_keeps_history_of_removed_beds(client):
    p = _plot(client, w=10, l=20)
    out = client.put(f"{API}/plots/{p['id']}/layout", json={"width_m": 10, "length_m": 20, "sections": [
        {"name": "Troppo larga", "kind": "bed", "x": 8, "y": 0, "w": 10, "h": 30},
        {"name": "Acqua", "kind": "water", "x": 1, "y": 1, "w": 1, "h": 1}]}).json()
    big = out["sections"][0]
    assert big["w"] == 2 and big["h"] == 20  # clamped inside the plot
    assert client.put(f"{API}/plots/{p['id']}/layout", json={"width_m": 10, "length_m": 20, "sections": [
        {"name": "X", "kind": "lava", "x": 0, "y": 0, "w": 1, "h": 1}]}).status_code == 400
    _season(client, p["id"], Y, crops=[{"crop": "tomato", "section_id": big["id"]}])
    plan = client.post(f"{API}/plots/{p['id']}/plan", json={}).json()
    assert {a["section_id"] for a in plan["years"][0]["assignments"]} == {big["id"]}  # water point is not planted
    beds, out2 = _beds(client, p["id"], n=2)  # redraw: the old bed disappears
    hist = out2["history"]
    assert hist and all(h["section_id"] is None for h in hist)  # its history now belongs to the whole plot
    irr = client.put(f"{API}/plots/{p['id']}/layout", json={"width_m": 10, "length_m": 10, "shape": "irregular",
                                                            "outline": [[0, 0], [10, 0], [0, 10]], "sections": []}).json()
    assert irr["area_m2"] == 50


def test_save_and_load_plan(client, db):
    p = _plot(client)
    beds, _ = _beds(client, p["id"], n=2)
    plan = client.post(f"{API}/plots/{p['id']}/plan", json={"years": 2}).json()
    ass = plan["years"][0]["assignments"]
    ass[0] = {**ass[0], "crop": "bean", "manual": True}
    saved = client.put(f"{API}/plots/{p['id']}/plans/{Y + 1}", json={"assignments": ass, "goals": {"years": 2}}).json()
    rows = db.query(PlannedCrop).filter_by(field_id=p["id"]).all()
    assert len(rows) == 2 and {x.section_id for x in rows} == set(beds) and all(x.year == Y + 1 for x in rows)
    loaded = next(x for x in client.get(f"{API}/farm").json()["plots"] if x["id"] == p["id"])
    assert loaded["plans"] == saved["plans"]
    got = {a["section_id"]: a for a in loaded["plans"][0]["assignments"]}
    assert got[ass[0]["section_id"]]["crop"] == "bean" and got[ass[0]["section_id"]]["manual"] is True
    assert got[ass[1]["section_id"]]["manual"] is False
    # saving again replaces, never duplicates
    client.put(f"{API}/plots/{p['id']}/plans/{Y + 1}", json={"assignments": ass})
    assert db.query(PlannedCrop).filter_by(field_id=p["id"]).count() == 2
    assert client.delete(f"{API}/plots/{p['id']}/plans/{Y + 1}").status_code == 204
    assert not db.query(PlannedCrop).filter_by(field_id=p["id"]).count()
    assert client.delete(f"{API}/plots/{p['id']}").status_code == 204
    assert db.get(PlotConditions, p["id"]) is None


def test_manual_change_is_checked_against_earlier_planned_years(client):
    p = _plot(client)
    _season(client, p["id"], Y, crops=["wheat"])
    free = client.post(f"{API}/plots/{p['id']}/check", json={"crop": "pepper", "year": Y + 2, "integrated": True}).json()
    after_tomato = client.post(f"{API}/plots/{p['id']}/check", json={
        "crop": "pepper", "year": Y + 2, "integrated": True, "planned": {str(Y + 1): "tomato"}}).json()
    assert free["verdict"] != "no" and after_tomato["verdict"] == "no"
    assert client.post(f"{API}/plots/{p['id']}/check", json={"crop": "mandragora", "year": Y + 1}).status_code == 400


def test_legacy_json_is_moved_to_tables(db):
    from app.models import Farm, Field, RotationPlan
    farm = Farm(name="Vecchia", owner="", timezone="UTC")
    db.add(farm)
    db.flush()
    f = Field(farm_id=farm.id, name="Vecchio", profile={"texture": "sandy", "problems": ["wilt"], "goals": {"x": 1}})
    db.add(f)
    db.flush()
    db.add(RotationPlan(field_id=f.id, year=Y + 1, assignments=[{"section_id": None, "crop": "bean", "verdict": "ok"}]))
    db.commit()
    rotation_store.migrate_legacy(db)
    assert db.get(PlotConditions, f.id).texture == "sandy"
    assert db.query(PlannedCrop).filter_by(field_id=f.id).one().crop == "bean"
    assert f.profile == {"goals": {"x": 1}}
    assert rotation_store.migrate_legacy(db) == {"profiles": 0, "plans": 0}  # idempotent


def test_saved_crop_without_verdict_is_checked_by_the_server(client):
    p = _plot(client)
    beds, _ = _beds(client, p["id"], n=1)
    _season(client, p["id"], Y, crops=[{"crop": "tomato", "section_id": beds[0]}])
    out = client.put(f"{API}/plots/{p['id']}/plans/{Y + 1}", json={"assignments": [
        {"section_id": beds[0], "crop": "eggplant", "manual": True}], "goals": {"integrated": True}}).json()
    a = out["plans"][0]["assignments"][0]
    assert a["verdict"] == "no" and a["area_m2"] > 0 and a["manual"] is True
