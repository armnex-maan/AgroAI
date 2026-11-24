"""Phase 6 – AI Farm Layout Generator: alternative layouts with equal real areas, reasons, the rotation engine's
plan for each one, nothing written to the database."""
from app.ml.agronomy import layout_generator as lg

API = "/api/v1/rotation"


def test_variants_have_equal_parts_paths_and_reasons():
    vs = lg.variants(None, 20, 40, 800, {"tomato": 0, "lettuce": 0}, greenhouse_m2=120, water_point=True)
    keys = [v["key"] for v in vs]
    assert keys == ["lungo", "corto", "serra"]
    long = vs[0]
    beds = [s for s in long["sections"] if s["kind"] == "bed"]
    assert len(beds) == 4                                           # 2 wanted crops + 2
    assert all(abs(b["h"] - 40) < 1e-6 for b in beds)                # strips run along the long (north-south) side
    assert max(b["w"] for b in beds) - min(b["w"] for b in beds) < 0.05
    assert any("non una norma" in w for w in long["why"]) and any("indicativo" in w for w in long["why"])
    gh = next(s for s in vs[2]["sections"] if s["kind"] == "greenhouse")
    assert gh["y"] == 0 and 5.9 < gh["h"] < 6.1                     # 120 m2 / 20 m, on the north side
    assert any("nord" in w for w in vs[2]["why"])
    assert all(any(s["kind"] == "water" for s in v["sections"]) for v in vs)
    assert all(s["id"].startswith("tmp-") for v in vs for s in v["sections"])


def test_too_narrow_options_are_not_offered():
    assert lg.variants(None, 3, 3, 9, {}, parts=8, path_m=0.6) == []


def test_layout_ai_endpoint_plans_each_variant_and_writes_nothing(client):
    client.put(f"{API}/farm", json={"region": "emilia_romagna"})
    p = client.post(f"{API}/plots", json={"name": "Orto AI", "width_m": 30, "length_m": 50}).json()
    before = client.get(f"{API}/farm").json()
    r = client.post(f"{API}/plots/{p['id']}/layout-ai", json={"goals": {"wanted": {"tomato": 0, "bean": 0}}, "greenhouse_m2": 200})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["variants"]) == 3 and d["variants"][0].get("best")
    assert d["variants"] == sorted(d["variants"], key=lambda v: -v["score"])
    v = d["variants"][0]
    ids = {s["id"] for s in v["sections"]}
    first = v["plan"][0]["assignments"]
    assert first and all(a["section_id"] in ids for a in first)         # the plan uses the proposed parts
    assert all(a["verdict"] in ("ok", "care", "no") for y in v["plan"] for a in y["assignments"])
    m = v["metrics"]
    assert m["growing_m2"] + m["path_m2"] <= 1500.5 and 0 <= m["path_share"] < 0.5
    assert any("non è un dato agronomico" in n for n in d["notes"])
    after = client.get(f"{API}/farm").json()
    plot = next(x for x in after["plots"] if x["id"] == p["id"])
    assert plot["sections"] == [] and plot["plans"] == []               # nothing saved
    assert len(after["plots"]) == len(before["plots"])
    no_dims = client.post(f"{API}/plots", json={"name": "Senza misure"}).json()
    assert client.post(f"{API}/plots/{no_dims['id']}/layout-ai", json={}).status_code == 400
