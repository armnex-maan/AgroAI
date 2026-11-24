"""Phase 5 – project save: drawings and plans in one transaction, new parts followed by their plans, areas always
from the part as drawn, saved versions and restore."""
API = "/api/v1/rotation"


def _setup(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna"})
    p = client.post(f"{API}/plots", json={"name": "Orto", "width_m": 20, "length_m": 30}).json()
    secs = client.put(f"{API}/plots/{p['id']}/layout", json={"width_m": 20, "length_m": 30, "sections": [
        {"name": "Aiuola 1", "kind": "bed", "x": 0, "y": 0, "w": 10, "h": 30},
        {"name": "Aiuola 2", "kind": "bed", "x": 10, "y": 0, "w": 10, "h": 30}]}).json()["sections"]
    return p["id"], secs


def _layout(secs):
    return {"width_m": 20, "length_m": 30, "sections": secs}


def _plot(client, pid):
    return next(p for p in client.get(f"{API}/farm").json()["plots"] if p["id"] == pid)


def test_one_save_writes_new_parts_and_their_plans(client):
    pid, (a, b) = _setup(client)
    new = {"id": "tmp-greenhouse", "name": "Serra 1", "kind": "greenhouse", "x": 10, "y": 0, "w": 10, "h": 10}
    b2 = {**b, "y": 10, "h": 20}                                         # resized: 200 m2 instead of 300
    body = {"layouts": {pid: _layout([a, b2, new])}, "plans": {pid: {"2027": [
        {"section_id": "tmp-greenhouse", "section": "Serra 1", "crop": "tomato", "name": "Pomodoro", "family": "Solanacee", "area_m2": 1, "verdict": "ok"},
        {"section_id": b["id"], "section": "Aiuola 2", "crop": "lettuce", "name": "Lattuga", "family": "Asteracee", "area_m2": 300, "verdict": "ok"},
        {"section_id": "gone", "section": "?", "crop": "bean", "name": "Fagiolo", "family": "Fabacee", "area_m2": 5}]}}}
    r = client.put(f"{API}/project", json=body)
    assert r.status_code == 200, r.text
    real = r.json()["ids"]["tmp-greenhouse"]
    assert not real.startswith("tmp-")
    plot = _plot(client, pid)
    assert {s["name"] for s in plot["sections"]} == {"Aiuola 1", "Aiuola 2", "Serra 1"}
    plan = next(x for x in plot["plans"] if x["year"] == 2027)["assignments"]
    tom = next(x for x in plan if x["crop"] == "tomato")
    assert tom["section_id"] == real and tom["area_m2"] == 100               # area from the part, not from the client
    assert next(x for x in plan if x["crop"] == "lettuce")["area_m2"] == 200
    bean = next(x for x in plan if x["crop"] == "bean")
    assert bean["section_id"] is None and bean["verdict"] in ("ok", "care", "no")   # unknown part -> whole plot, checked
    revs = [x["label"] for x in client.get(f"{API}/project/revisions").json()["revisions"]]
    assert revs[0] == "Salvataggio del progetto" and "Situazione prima del primo salvataggio" in revs   # the start is kept


def test_nothing_is_written_when_one_part_is_invalid(client):
    pid, (a, b) = _setup(client)
    before = _plot(client, pid)
    n_revs = len(client.get(f"{API}/project/revisions").json()["revisions"])
    bad = {"layouts": {pid: _layout([{**a, "w": 5}, b])}, "plans": {"no-such-plot": {"2027": []}}}
    assert client.put(f"{API}/project", json=bad).status_code == 404
    bad2 = {"layouts": {pid: _layout([{**a, "w": 5}, {**b, "kind": "castle"}])}}
    assert client.put(f"{API}/project", json=bad2).status_code == 400
    after = _plot(client, pid)
    assert [s["w"] for s in after["sections"]] == [s["w"] for s in before["sections"]]
    assert len(client.get(f"{API}/project/revisions").json()["revisions"]) == n_revs


def test_restore_brings_back_drawing_and_plans(client):
    pid, (a, b) = _setup(client)
    plan = [{"section_id": a["id"], "section": "Aiuola 1", "crop": "tomato", "name": "Pomodoro", "family": "Solanacee", "area_m2": 300, "verdict": "ok"}]
    first = client.put(f"{API}/project", json={"layouts": {pid: _layout([a, b])}, "plans": {pid: {"2027": plan}}}).json()["revision"]
    # later: one bed deleted, the 2027 plan changed, a 2028 plan added
    client.put(f"{API}/project", json={"layouts": {pid: _layout([{**a, "w": 20}])}, "plans": {pid: {
        "2027": [{**plan[0], "crop": "bean", "name": "Fagiolo", "family": "Fabacee"}], "2028": plan}}})
    assert len(_plot(client, pid)["sections"]) == 1
    r = client.post(f"{API}/project/revisions/{first['id']}/restore")
    assert r.status_code == 200, r.text
    plot = _plot(client, pid)
    assert sorted(s["name"] for s in plot["sections"]) == ["Aiuola 1", "Aiuola 2"]
    assert [p["year"] for p in plot["plans"]] == [2027]
    restored = plot["plans"][0]["assignments"][0]
    assert restored["crop"] == "tomato" and restored["section_id"] == a["id"]   # bed 1 kept its id
    assert client.get(f"{API}/project/revisions").json()["revisions"][0]["label"].startswith("Ripristino")
    assert client.post(f"{API}/project/revisions/nope/restore").status_code == 404
