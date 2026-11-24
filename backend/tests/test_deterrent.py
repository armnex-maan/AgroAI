import io

import numpy as np
import soundfile as sf


def _prog(**kw):
    p = {"target": "sparrows", "sound_type": "tones", "f_lo": 2200, "f_hi": 3200,
         "plays_per_hour": 4, "clip_seconds": 2}
    p.update(kw)
    return p


def test_guide_is_honest_about_ultrasound(client):
    g = client.get("/api/v1/deterrent/guide").json()
    assert g["profiles"]["sparrows"]["best_band_hz"] == [2200, 3200]
    ultra = [m for m in g["methods"] if m["name"] == "Ultrasuoni"][0]
    assert ultra["tone"] == "bad"


def test_preview_tones_stay_in_audible_band(client):
    r = client.post("/api/v1/deterrent/preview?seed=1", json=_prog())
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    x, sr = sf.read(io.BytesIO(r.content))
    spec = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    peak = f[np.argmax(spec)]
    assert 2000 <= peak <= 3400
    assert spec[f > 6000].sum() < 0.02 * spec.sum()


def test_ultrasound_and_out_of_band_rejected(client):
    r = client.post("/api/v1/deterrent/preview", json=_prog(f_lo=20000, f_hi=25000))
    assert r.status_code == 400 and "ultrasuoni" in r.json()["detail"]
    r = client.post("/api/v1/deterrent/preview", json=_prog(f_lo=9000, f_hi=12000))
    assert r.status_code == 400


def test_bundled_library_is_verified_and_plays(client):
    import json
    from urllib.parse import unquote
    lib = client.get("/api/v1/deterrent/guide").json()["library"]
    assert {e["kind"] for e in lib if e["target"] == "sparrows"} == {"alarm_call", "predator_call"}
    assert all(e["verified"] and e["licence"].startswith("CC") and "ND" not in e["licence"] for e in lib)
    r = client.post("/api/v1/deterrent/preview?seed=3", json=_prog(sound_type="mix", clip_seconds=3))
    assert r.status_code == 200
    info = json.loads(unquote(r.headers["x-sound"]))
    assert info["target"] == "sparrows" and info["kind"] in ("alarm_call", "predator_call")
    x, sr = sf.read(io.BytesIO(r.content))
    assert abs(len(x) / sr - 3) < 0.1 and np.abs(x).max() > 0.3
    assert client.get(f"/api/v1/deterrent/library/{lib[0]['id']}.ogg").status_code == 200


def test_no_alarm_sounds_for_pigeons(client):
    r = client.post("/api/v1/deterrent/preview",
                    json=_prog(target="pigeons", sound_type="alarm_call", f_lo=500, f_hi=3000))
    assert r.status_code == 400


def test_device_is_simulated_and_physical_disabled(client, db):
    r = client.post("/api/v1/deterrent/devices", json={"name": "Test", "program": _prog()})
    assert r.status_code == 201
    d = r.json()
    assert d["physical_enabled"] is False and d["program"]["physical_enabled"] is False
    r = client.post(f"/api/v1/deterrent/devices/{d['id']}/test").json()
    assert r["log"][0]["simulated"] is True and r["log"][0]["physical"] is False
    plan = client.get(f"/api/v1/deterrent/devices/{d['id']}/plan").json()["times"]
    assert len(plan) == 4 * 3 + 4 * 2  # two windows (3 h and 2 h) x 4 plays/hour

    from app.services import deterrent_service as svc
    fired = svc.on_detection(db, ["Passer italiae"], None)
    assert len(fired) == 1
    assert svc.on_detection(db, ["Turdus merula"], None) == []
    client.delete(f"/api/v1/deterrent/devices/{d['id']}")
