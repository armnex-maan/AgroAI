from datetime import date

from app.ml.agronomy import rotation as r


def _j(key, history, problems=(), soil=None):
    return r.judge(r.BY_KEY[key], history, set(problems), soil)


def test_official_intervals_and_family_rules():
    # carrot needs 3 years of other crops (Emilia-Romagna DPI 2023)
    assert _j("carrot", ["wheat", "carrot"])["verdict"] == "no"
    assert _j("carrot", ["wheat", "maize", "bean", "carrot"])["verdict"] != "no"
    # no solanaceae right after another solanaceae
    assert _j("pepper", ["tomato"])["verdict"] == "no"
    # tomato: one repeat allowed, a second one is not
    assert _j("tomato", ["tomato", "wheat"])["verdict"] in ("care", "ok")
    assert _j("tomato", ["tomato", "tomato"])["verdict"] == "no"
    # Sclerotinia: bean must not follow soybean; asparagus not after potato
    assert _j("bean", ["soybean"])["verdict"] == "no"
    assert _j("asparagus", ["potato"])["verdict"] == "no"


def test_legume_before_demanding_crop_is_rewarded():
    after_bean = _j("tomato", ["bean", "wheat", "maize"])
    after_maize = _j("tomato", ["maize", "wheat", "bean"])
    assert after_bean["score"] > after_maize["score"]
    assert any("azoto" in x["text"] for x in after_bean["reasons"])


def test_soil_problems_extend_waiting_time():
    assert _j("cabbage", ["wheat", "bean", "cabbage"])["verdict"] != "no"
    assert _j("cabbage", ["wheat", "bean", "cabbage"], ["clubroot"])["verdict"] == "no"
    assert _j("melon", ["wheat", "bean"], ["nematodes"])["verdict"] == "care"  # sensitive family, not grown here


def test_plan_spreads_families_and_respects_rules():
    p = r.plan(["tomato", "wheat"], ["tomato"], set(), None)
    keys = [x["key"] for x in p]
    fams = [r.BY_KEY[k].family for k in keys if k in r.BY_KEY]
    assert len(set(fams)) >= 3
    assert keys[0] != "tomato" and r.BY_KEY[keys[0]].family != "solanacee"


def test_find_names():
    assert r.find("Pomodoro San Marzano").key == "tomato"
    assert r.find("cavolfiore").key == "cabbage"
    assert r.find("cocomero").key == "watermelon"
    assert r.find("kiwi") is None


def test_api_flow_saves_history(client):
    from app.api.v1.rotation import last_season_year
    setup = client.get("/api/v1/rotation/setup").json()
    assert [q["id"] for q in setup["questions"]][:3] == ["last", "before", "wanted"]
    f = client.post("/api/v1/farms", json={"name": "Test", "owner": "t", "latitude": 44.5, "longitude": 11.3,
                                          "timezone": "Europe/Rome"}).json()
    field = client.post("/api/v1/fields", json={"farm_id": f["id"], "name": "Campo 1"}).json()
    body = {"field_id": field["id"], "last": "tomato", "before": "wheat", "wanted": ["pepper", "bean"],
            "problems": ["wilt"], "soil": "normal", "manure": "some", "cover": "yes", "save": True}
    out = client.post("/api/v1/rotation/advise", json=body).json()
    verdicts = {w["key"]: w["verdict"] for w in out["wished"]}
    assert verdicts["pepper"] == "no" and verdicts["bean"] == "ok"
    assert out["saved"] and len(out["plan"]) == 4 and out["cover_crop"]
    hist = client.get(f"/api/v1/rotation/history?field_id={field['id']}").json()
    y = last_season_year()
    assert {(h["year"], h["crop"]) for h in hist} == {(y, "tomato"), (y - 1, "wheat")}
    assert last_season_year(date(2026, 3, 1)) == 2025 and last_season_year(date(2026, 10, 1)) == 2026
