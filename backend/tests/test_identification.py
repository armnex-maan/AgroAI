from app.ml.audio.identification import fuse
from app.ml.audio.yamnet import group_for

UG_NONE = {"category": "noise", "confidence": 0.1, "evidence": {}}


def _yam(*groups):
    return {"available": True, "groups": [
        {"group": g, "kind": k, "score": s, "best_class": c} for g, k, s, c in groups]}


def test_group_mapping():
    assert group_for("Bird vocalization, bird call, bird song")[0] == "bird"
    assert group_for("Crowing, cock-a-doodle-doo")[0] == "poultry_waterfowl"
    assert group_for("Cricket")[0] == "insect"
    assert group_for("Tractor")[0] == "machinery_vehicle"
    assert group_for("Rain on surface")[0] == "water_irrigation"


def test_unknown_when_nothing_above_threshold():
    out = fuse(_yam(("bird", "animal", 0.05, "Bird")), None, None, UG_NONE, 0.5, 0.2)
    assert out["verdict"] == "unknown" and out["candidates"] == []


def test_probable_bird_drops_generic_animal_class():
    out = fuse(_yam(("bird", "animal", 0.9, "Bird"), ("wild_animal", "animal", 0.85, "Wild animals")),
               None, None, UG_NONE, 0.5, 0.2)
    assert out["verdict"] == "probable"
    assert [c["group"] for c in out["candidates"]] == ["bird"]


def test_underground_capped_and_penalised_by_irrigation_context():
    ug = {"category": "repetitive_low_freq_pattern", "confidence": 0.8,
          "evidence": {"envelope_peaks": 6, "periodicity": {"period_s": 0.6}}}
    clean = fuse(_yam(), None, None, ug, 0.5, 0.2)
    assert clean["candidates"][0]["level"] == "possible"
    noisy = fuse(_yam(("water_irrigation", "context", 0.7, "Water")), None, None, ug, 0.5, 0.2)
    c = noisy["candidates"][0]
    assert c["score"] == 0.4 and "dimezzata" in c["evidence"]
    assert noisy["context"][0]["group"] == "water_irrigation"


def test_farm_model_unknown_is_not_a_candidate():
    out = fuse(_yam(), None, {"label": "unknown", "confidence": 0.9, "version": 1}, UG_NONE, 0.5, 0.2)
    assert out["verdict"] == "unknown"
