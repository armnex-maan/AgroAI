"""Differential diagnosis engine and soil-moisture interpretation."""
from app.ml.agronomy import soil_water
from app.ml.vision import differential
from app.ml.vision.vlm import _parse

# what the vision model reported for the tomato photo with dark lesions near the stalk
TOMATO_AI = {
    "is_plant_image": True,
    "observations": {"organs": ["fruit", "leaf", "stem"], "fruit_location": "stem_end", "texture": "firm_greasy",
                     "colour": "olive_brown_marbled", "shape": "large_irregular", "leaves": "affected",
                     "stems": "affected"},
    "causes": [{"id": "blossom_end_rot", "likelihood": "high", "why": "macchie scure sul frutto"},
               {"id": "water_stress", "likelihood": "medium", "why": "x"}],
}
SIM_SOIL = soil_water.interpret(32.6, "%", "simulation", "loam", "pomodoro")


def _by_id(dx):
    return {c["id"]: c for c in dx["causes"]}


def test_stem_end_lesions_rule_out_blossom_end_rot_even_if_model_says_so():
    dx = differential.diagnose(TOMATO_AI, [], SIM_SOIL, {})
    c = _by_id(dx)
    assert dx["causes"][0]["id"] == "late_blight" and c["late_blight"]["tier"] == "probable"
    assert c["blossom_end_rot"]["tier"] == "unlikely"
    assert any("opposta al picciolo" in e["text"] and e["effect"] == "weakens" for e in c["blossom_end_rot"]["evidence"])
    assert c["heat_sunscald"]["tier"] == "unlikely"


def test_blossom_end_lesions_on_healthy_plant_point_to_blossom_end_rot():
    ai = {"observations": {"organs": ["fruit"], "fruit_location": "blossom_end", "texture": "dry_leathery",
                           "colour": "dark_brown_black", "leaves": "healthy"},
          "causes": [{"id": "blossom_end_rot", "likelihood": "medium", "why": "x"}]}
    c = _by_id(differential.diagnose(ai, [], None, {}))
    assert c["blossom_end_rot"]["tier"] == "probable"
    assert c.get("late_blight", {"tier": "unlikely"})["tier"] != "probable"


def test_single_photo_is_never_certain_and_answers_change_the_ranking():
    ai = {"observations": {"organs": ["fruit"], "colour": "dark_brown_black"},
          "causes": [{"id": "blossom_end_rot", "likelihood": "high", "why": "x"},
                     {"id": "heat_sunscald", "likelihood": "medium", "why": "x"}]}
    dx = differential.diagnose(ai, [], None, {})
    assert max(c["probability"] for c in dx["causes"]) <= differential.CAP_PHOTO
    asked = {q["id"] for q in dx["questions"]}
    assert "fruit_location" in asked  # location decides between these causes and is not visible
    after = differential.diagnose(ai, [], None, {}, {"fruit_location": "stem_end", "leaves": "affected"})
    c = _by_id(after)
    assert c["blossom_end_rot"]["tier"] == "unlikely"
    assert any(e["origin"] == "tua risposta" for e in c["blossom_end_rot"]["evidence"])


def test_sunscald_needs_sun_exposure():
    ai = {"observations": {"organs": ["fruit"], "fruit_location": "sun_side", "texture": "papery_pale",
                           "colour": "pale_white_yellow"},
          "causes": [{"id": "heat_sunscald", "likelihood": "medium", "why": "x"}]}
    assert _by_id(differential.diagnose(ai, [], None, {}))["heat_sunscald"]["tier"] == "probable"
    shaded = differential.diagnose(ai, [], None, {}, {"sun_exposed": "no"})
    assert _by_id(shaded)["heat_sunscald"]["probability"] < _by_id(differential.diagnose(ai, [], None, {}))["heat_sunscald"]["probability"]


def test_soil_moisture_depends_on_texture_sensor_and_source():
    # 32.6 % is not drought in loam: above field capacity
    loam = soil_water.interpret(32.6, "%", "device", "loam", "pomodoro")
    assert loam["status"] in ("wet", "adequate") and loam["usable"] and loam["reliability"] == "bassa"
    # same number, unknown soil: not dry for any texture
    unknown = soil_water.interpret(32.6, "%", "device", None, "pomodoro")
    assert unknown["status"] == "adequate" and unknown["texture_assumed"]
    # 20 % is dry in clay but wet in sand
    assert soil_water.interpret(20, "%", "device", "clay", "pomodoro")["status"] in ("dry", "very_dry")
    assert soil_water.interpret(20, "%", "device", "sand", "pomodoro")["status"] in ("wet", "very_wet")
    # simulated data is never used as evidence
    sim = soil_water.interpret(10, "%", "simulation", "loam", None)
    assert sim["usable"] is False
    dx = differential.diagnose({"causes": [{"id": "water_stress", "likelihood": "medium", "why": "x"}],
                                "observations": {"organs": ["leaf"]}}, [], sim, {})
    ws = _by_id(dx)["water_stress"]
    assert all(e["weight"] == 0 for e in ws["evidence"] if e["origin"] == "sensore")
    # calibrated sensor counts more
    cal = soil_water.interpret(25, "%", "device", "loam", None, {"soil_specific": True})
    assert cal["reliability"] == "alta"
    raw = soil_water.interpret(1830, "raw", "device", "loam", None)
    assert raw["status"] == "unknown" and not raw["usable"]


def test_parse_keeps_only_valid_observations():
    out = _parse('{"observations":{"organs":["fruit","root"],"fruit_location":"stem_end","texture":"crunchy"},'
                 '"causes":[{"id":"late_blight","likelihood":"medium","why":"x"}]}')
    assert out["observations"] == {"organs": ["fruit"], "fruit_location": "stem_end"}


def test_answers_endpoint_recalculates(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (200, 80, 40)).save(buf, "JPEG")
    r = client.post("/api/v1/vision/analyze", files={"file": ("t.jpg", buf.getvalue(), "image/jpeg")},
                    data={"crop": "pomodoro"})
    aid = r.json()["id"]
    r = client.post(f"/api/v1/vision/analyses/{aid}/answers",
                    json={"answers": {"fruit_location": "stem_end", "leaves": "affected", "bogus": "x"}})
    assert r.status_code == 200
    f = r.json()["findings"]
    assert f["answers"] == {"fruit_location": "stem_end", "leaves": "affected"}
    ids = [c["id"] for c in f["causes"]]
    assert "late_blight" in ids and f["engine"] == "differential-v1"
    assert all(c["tier"] in ("probable", "possible", "unlikely") for c in f["causes"])
    assert client.post("/api/v1/vision/analyses/nope/answers", json={"answers": {}}).status_code == 404


def test_missing_hallmark_keeps_cause_at_most_possible():
    ai = dict(TOMATO_AI, causes=[{"id": "early_blight", "likelihood": "high", "why": "x"},
                                 {"id": "late_blight", "likelihood": "medium", "why": "x"}])
    c = _by_id(differential.diagnose(ai, [], None, {}, {"weather": "humid_rainy"}))
    assert c["early_blight"]["tier"] == "possible"  # large irregular patches, no concentric rings
    assert c["late_blight"]["tier"] == "probable"


MODEL = {"applicable": True, "cause_accuracy": 0.7, "real_photo_accuracy": 0.6,
         "by_cause": {"late_blight": 0.8, "early_blight": 0.1, "healthy": 0.02},
         "top": [{"label": "tomato/late_blight", "name": "Pomodoro – peronospora", "cause": "late_blight",
                  "organ": "leaf", "score": 0.8}]}


def test_trained_model_adds_weighted_evidence_only_when_applicable():
    ai = {"observations": {"organs": ["leaf"]}, "causes": [{"id": "early_blight", "likelihood": "medium", "why": "x"}]}
    with_model = _by_id(differential.diagnose(ai, [], None, {}, None, MODEL))
    without = _by_id(differential.diagnose(ai, [], None, {}))
    assert "late_blight" in with_model and "late_blight" not in without  # the model proposes a cause
    assert any(e["origin"] == "modello addestrato" for e in with_model["late_blight"]["evidence"])
    off = _by_id(differential.diagnose(ai, [], None, {}, None, {**MODEL, "applicable": False}))
    assert "late_blight" not in off


def test_model_endpoint_without_trained_model(client):
    body = client.get("/api/v1/vision/model").json()
    assert body["active"] is None and body["versions"] == []
    assert client.post("/api/v1/vision/model/activate", json={"version": "v99"}).status_code == 404


def test_unsure_model_does_not_weaken_causes():
    unsure = {**MODEL, "by_cause": {"early_blight": 0.3, "late_blight": 0.01},
              "top": [{"label": "tomato/early_blight", "name": "x", "cause": "early_blight", "organ": "leaf", "score": 0.3}]}
    ai = {"observations": {"organs": ["leaf"]}, "causes": [{"id": "late_blight", "likelihood": "medium", "why": "x"}]}
    lb = _by_id(differential.diagnose(ai, [], None, {}, None, unsure))["late_blight"]
    assert not any(e["origin"] == "modello addestrato" for e in lb["evidence"])


def test_reanalyze_keeps_previous_ai_answer_when_ai_unreachable(client, monkeypatch):
    import asyncio, io
    from PIL import Image
    from app.core.database import SessionLocal
    from app.models import ImageAnalysis
    from app.services import vision_service
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (60, 140, 50)).save(buf, "JPEG")
    aid = client.post("/api/v1/vision/analyze", files={"file": ("t.jpg", buf.getvalue(), "image/jpeg")},
                      data={"crop": "pomodoro"}).json()["id"]
    db = SessionLocal()
    row = db.get(ImageAnalysis, aid)
    row.findings = {**row.findings, "ai": TOMATO_AI}
    db.commit()
    from app.ml.vision import vlm
    from app.services.llm_service import LLMUnavailable

    async def boom(*a, **k):
        raise LLMUnavailable("getaddrinfo failed")
    monkeypatch.setattr(vlm, "assess", boom)
    out = asyncio.run(vision_service.reanalyze(db, aid)).findings
    assert out["ai"] == TOMATO_AI and "tenuta l'analisi" in out["ai_error"]
    assert out["causes"][0]["id"] == "late_blight"


def test_crop_names_map_to_dataset_crops():
    from app.ml.vision.plant_labels import crop_key
    assert crop_key("Melograno") == "pomegranate" and crop_key("mela golden") == "apple"
    assert crop_key("Pere Abate") == "pear" and crop_key("cavolfiore") == "cauliflower"
    assert crop_key("cime di rapa") == "broccoli" and crop_key("Pomodoro San Marzano") == "tomato"
    assert crop_key("kiwi") is None


def test_model_cannot_rule_out_fruit_diseases_it_never_learnt():
    # model trained on tomato fruit only for healthy / rotten / grey mould: it calls a late-blight fruit "grey mould"
    model = {"applicable": True, "cause_accuracy": 0.9, "known_causes": ["grey_mould", "healthy"],
             "organs_used": ["fruit"], "by_cause": {"grey_mould": 0.84, "late_blight": 0.01, "healthy": 0.02},
             "top": [{"label": "tomato/grey_mould_fruit", "name": "Pomodoro – muffa grigia sul frutto",
                      "cause": "grey_mould", "organ": "fruit", "score": 0.84}]}
    c = _by_id(differential.diagnose(TOMATO_AI, [], None, {}, None, model))
    assert c["late_blight"]["tier"] == "probable"
    assert not any(e["origin"] == "modello addestrato" for e in c["late_blight"]["evidence"])
    gm = [e for e in c["grey_mould"]["evidence"] if e["origin"] == "modello addestrato"][0]
    assert gm["weight"] <= 0.8 and "non conosce ancora" in gm["text"]
