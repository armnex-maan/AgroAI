"""End-to-end: label synthetic recordings, train, review metrics, activate, predict."""


def _make(client, profile, seed):
    r = client.post("/api/v1/audio/generate-sample", json={"profile": profile, "duration_s": 3, "seed": seed})
    rid = r.json()["id"]
    assert client.post(f"/api/v1/audio/recordings/{rid}/labels",
                       json={"label": "mole" if profile == "underground" else profile}).status_code == 201
    return rid


def test_train_refuses_with_too_few_examples(client):
    _make(client, "cricket", 900)
    r = client.post("/api/v1/ml/models/train", json={})
    assert r.status_code == 400


def test_train_validate_activate_predict(client):
    for s in range(6):
        _make(client, "underground", 100 + s)
        _make(client, "machinery", 200 + s)

    r = client.post("/api/v1/ml/models/train", json={"notes": "synthetic test"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["status"] == "trained"  # never auto-activated
    assert set(m["labels"]) >= {"mole", "machinery"}
    assert "esclusi dall'addestramento" in m["metrics"]["validation"]
    assert m["metrics"]["contains_simulated_data"] is True
    assert len(m["metrics"]["confusion_matrix"]) == len(m["labels"])
    assert m["metrics"]["can_activate"] is True

    r = client.post(f"/api/v1/ml/models/{m['id']}/activate")
    assert r.status_code == 200 and r.json()["status"] == "active"
    eng = client.get("/api/v1/audio/engines").json()
    assert eng["farm_model"]["active"] is True

    rid = client.post("/api/v1/audio/generate-sample",
                      json={"profile": "underground", "duration_s": 3, "seed": 999}).json()["id"]
    body = client.post(f"/api/v1/audio/recordings/{rid}/analyze").json()
    fm = next(d for d in body["detections"] if d["model"] == "farm-model")
    assert fm["category"] in ("mole", "unknown")
    assert fm["evidence"]["ranking"][0]["label"] == "mole"

    # white noise looks like nothing the model was trained on
    rid = client.post("/api/v1/audio/generate-sample",
                      json={"profile": "noise", "duration_s": 3, "seed": 5}).json()["id"]
    body = client.post(f"/api/v1/audio/recordings/{rid}/analyze").json()
    fm = next(d for d in body["detections"] if d["model"] == "farm-model")
    assert fm["category"] == "unknown"

    client.post(f"/api/v1/ml/models/{m['id']}/deactivate")
