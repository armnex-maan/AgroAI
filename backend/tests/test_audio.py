import io
import math

import numpy as np
import soundfile as sf


def _wav(x: np.ndarray, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, x.astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _upload(client, x, name="x.wav"):
    r = client.post("/api/v1/audio/upload", files={"file": (name, _wav(x), "audio/wav")}, data={"source": "manual"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_analyze_tone_finds_dominant_frequency(client):
    t = np.arange(32000) / 16000
    rec = _upload(client, 0.3 * np.sin(2 * math.pi * 120.0 * t))
    r = client.post(f"/api/v1/audio/recordings/{rec}/analyze")
    assert r.status_code == 200, r.text
    body = r.json()
    dets = {d["model"]: d for d in body["detections"]}
    assert {"identification", "spectral", "underground-experimental", "yamnet"} <= set(dets)
    peaks = dets["spectral"]["evidence"]["dominant_frequencies"]
    assert abs(peaks[0]["frequency_hz"] - 120.0) < 5.0
    assert dets["yamnet"]["category"] == "unavailable"
    assert body["identification"]["engines"]["yamnet"] is False


def test_reanalyze_replaces_detections(client):
    rec = _upload(client, 0.01 * np.random.default_rng(1).standard_normal(16000))
    client.post(f"/api/v1/audio/recordings/{rec}/analyze")
    client.post(f"/api/v1/audio/recordings/{rec}/analyze")
    dets = client.get(f"/api/v1/audio/recordings/{rec}/detections").json()
    assert len([d for d in dets if d["model"] == "identification"]) == 1


def test_underground_pattern_is_never_a_species(client):
    r = client.post("/api/v1/audio/generate-sample", json={"profile": "underground", "duration_s": 5, "seed": 3})
    rec = r.json()["id"]
    body = client.post(f"/api/v1/audio/recordings/{rec}/analyze").json()
    ug = next(d for d in body["detections"] if d["model"] == "underground-experimental")
    assert ug["category"] in ("repetitive_low_freq_pattern", "transient_low_freq")
    assert "non riconosce la specie" in ug["evidence"]["note"]
    for c in body["identification"]["candidates"]:
        if c["source"] == "underground-experimental":
            assert c["level"] == "possible"  # capped, never "probable"


def test_label_validation_and_export(client):
    rec = _upload(client, 0.1 * np.random.default_rng(2).standard_normal(16000))
    assert client.post(f"/api/v1/audio/recordings/{rec}/labels", json={"label": "  ", "start_s": 0}).status_code == 400
    assert client.post(f"/api/v1/audio/recordings/{rec}/labels",
                       json={"label": "bird", "start_s": 0.8, "end_s": 0.2}).status_code == 400
    r = client.post(f"/api/v1/audio/recordings/{rec}/labels", json={"label": "Bird", "start_s": 0.1, "end_s": 0.8})
    assert r.status_code == 201 and r.json()["label"] == "bird"
    csv = client.get("/api/v1/audio/export/dataset.csv").text
    assert "bird" in csv


def test_device_audio_upload_requires_signature(client):
    client.post("/api/v1/devices", json={"id": "AUD-1", "name": "a", "source": "device", "sensors": []})
    r = client.post("/api/v1/audio/upload", files={"file": ("n.wav", _wav(np.zeros(16000)), "audio/wav")},
                    data={"source": "device", "device_id": "AUD-1"})
    assert r.status_code == 401
