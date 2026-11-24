import io

from PIL import Image, ImageDraw

from app.ml.vision import color
from app.ml.vision.causes import CAUSES, sensor_checks
from app.ml.vision.vlm import _parse


def _leaf(yellow: bool, brown: bool) -> bytes:
    img = Image.new("RGB", (640, 480), (225, 225, 225))
    d = ImageDraw.Draw(img)
    d.ellipse((60, 40, 580, 440), fill=(55, 145, 50))
    for x in range(140, 520, 70):
        if yellow:
            d.ellipse((x, 120, x + 50, 200), fill=(215, 205, 60))
        if brown:
            d.ellipse((x + 5, 280, x + 40, 315), fill=(120, 75, 30))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def test_colour_healthy_vs_symptoms():
    healthy = color.analyze(color.load(_leaf(False, False)))
    sick = color.analyze(color.load(_leaf(True, True)))
    assert healthy["pattern"] == "looks_healthy"
    assert sick["chlorotic_yellow"] > 0.08 and sick["necrotic_brown"] > 0.02
    assert sick["pattern"] in ("mild_discolouration", "marked_discolouration")


def test_brown_soil_alone_is_not_necrosis():
    img = Image.new("RGB", (400, 300), (120, 80, 40))  # bare soil, no plant
    out = color.analyze(img)
    assert out["necrotic_brown"] == 0.0 and out["pattern"] == "no_plant_detected"


def test_parse_drops_invented_causes():
    text = 'blah {"overall":"mild_symptoms","causes":[{"id":"iron_chlorosis","likelihood":"high","why":"x"},' \
           '{"id":"alien_blight","likelihood":"high"},{"id":"rust","likelihood":"certain"}]} trailing'
    out = _parse(text)
    assert [c["id"] for c in out["causes"]] == ["iron_chlorosis", "rust"]
    assert out["causes"][1]["likelihood"] == "low"


def test_sensor_cross_checks():
    assert sensor_checks("water_stress", {"soil_moisture": 12})[0]["effect"] == "supports"
    assert sensor_checks("iron_chlorosis", {"soil_ph": 6.2})[0]["effect"] == "weakens"
    assert sensor_checks("rust", {}) == []


def test_every_cause_has_tips_and_sources():
    for cid, c in CAUSES.items():
        assert c["fix"] and c["verify"] and c["sources"], cid


def test_natural_remedies_linked_and_sourced(client):
    from app.ml.vision import natural
    assert set(natural.BY_CAUSE) == set(CAUSES)
    for rid, r in natural.REMEDIES.items():
        assert r["sources"] and r["how"] and r["evidence"] in ("provato", "alcuni studi", "tradizionale"), rid
    ids = {r["id"] for r in natural.for_cause("sucking_insects")}
    assert {"ladybirds", "phytoseiulus", "encarsia"} <= ids
    assert "bt" in {r["id"] for r in natural.for_cause("chewing_insects")}
    body = client.get("/api/v1/vision/remedies").json()
    assert len(body["remedies"]) == len(natural.REMEDIES)
    copper = next(r for r in body["remedies"] if r["id"] == "copper")
    assert "28 kg" in copper["how"] and "downy_mildew" in copper["causes"]


def test_analyze_endpoint_without_ai_uses_colour_fallback(client):
    r = client.post("/api/v1/vision/analyze", files={"file": ("leaf.jpg", _leaf(True, False), "image/jpeg")},
                    data={"crop": "tomato"})
    assert r.status_code == 201, r.text
    body = r.json()
    f = body["findings"]
    assert f["ai"] is None and "non configurata" in f["ai_error"]
    assert f["causes"] and all(c["likelihood"] == "low" for c in f["causes"])
    # colour alone is weak evidence: no cure is suggested for poorly matching causes, only how to check
    assert all(c["tier"] == "unlikely" and not c["fix"] and c["verify"] for c in f["causes"])
    assert "non una diagnosi certa" in f["disclaimer"]

    aid = body["id"]
    assert client.get(f"/api/v1/vision/analyses/{aid}/image").status_code == 200
    assert client.get(f"/api/v1/vision/analyses/{aid}/overlay.png").status_code == 200
    v = client.post(f"/api/v1/vision/analyses/{aid}/verify",
                    json={"verdict": "wrong", "actual_cause": "water_stress", "notes": "dry soil"})
    assert v.status_code == 201 and v.json()["verifications"][0]["actual_cause"] == "water_stress"
    assert client.post(f"/api/v1/vision/analyses/{aid}/verify",
                       json={"verdict": "wrong", "actual_cause": "made_up"}).status_code == 400


def test_not_a_plant_gives_no_causes(client, monkeypatch):
    from app.ml.vision import vlm

    async def fake(*_a, **_k):
        return {"is_plant_image": False, "overall": "unclear", "causes": [], "visible_symptoms": [],
                "summary": "Not a plant.", "cannot_tell": "everything"}
    monkeypatch.setattr(vlm, "assess", fake)
    r = client.post("/api/v1/vision/analyze", files={"file": ("x.jpg", _leaf(True, True), "image/jpeg")})
    f = r.json()["findings"]
    assert f["overall"] == "not_a_plant" and f["causes"] == []


def test_rejects_non_image(client):
    r = client.post("/api/v1/vision/analyze", files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400
