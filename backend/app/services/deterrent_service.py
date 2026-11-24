"""Simulated acoustic bird deterrents.

A deterrent is a Device (hardware_type "deterrent-sim", source "simulation") whose config holds the
sound program and an activation log. Nothing is ever emitted by real hardware: physical output is
fixed to disabled until a real speaker node and an explicit authorisation exist.
"""
from __future__ import annotations

import io
import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import soundfile as sf
from sqlalchemy.orm import Session

from app.ml import deterrence
from app.ml.audio import signal as dsp
from app.models import Alert, AudioRecording, Device

HW = "deterrent-sim"
SR = 32000
MAX_LOG = 200


class DeterrentError(ValueError):
    pass


def default_program(target: str) -> dict:
    p = deterrence.PROFILES[target]
    return {
        "target": target, "sound_type": "mix", "recording_id": None,
        "f_lo": p["best_band_hz"][0], "f_hi": p["best_band_hz"][1],
        "windows": [{"start": "05:30", "end": "08:30"}, {"start": "17:30", "end": "19:30"}],
        "plays_per_hour": 4, "clip_seconds": 4, "random_intervals": True,
        "trigger_on_detection": True, "physical_enabled": False,
    }


def validate_program(db: Session, prog: dict) -> dict:
    if prog.get("target") not in deterrence.PROFILES:
        raise DeterrentError("Specie da allontanare non valida.")
    if prog.get("sound_type") not in deterrence.SOUND_TYPES:
        raise DeterrentError("Tipo di suono non valido.")
    p = deterrence.PROFILES[prog["target"]]
    lo, hi = p["audible_band_hz"]
    if prog["sound_type"] == "tones":
        f_lo, f_hi = float(prog.get("f_lo", 0)), float(prog.get("f_hi", 0))
        if f_hi >= deterrence.ULTRASOUND_HZ or f_lo >= deterrence.ULTRASOUND_HZ:
            raise DeterrentError("Gli uccelli non sentono gli ultrasuoni (sopra 20.000 Hz): non avrebbe alcun effetto.")
        if f_lo < lo or f_hi > hi or f_lo >= f_hi:
            raise DeterrentError(f"Per i {p['name'].lower()} usa frequenze tra {lo} e {hi} Hz: "
                                 f"fuori da questa fascia non sentono bene il suono.")
    else:
        rid = prog.get("recording_id")
        if rid and db.get(AudioRecording, rid) is None:
            raise DeterrentError("La registrazione scelta non esiste più.")
        if not rid and not deterrence.library_for(prog["target"], prog["sound_type"]):
            raise DeterrentError("Per questa specie non ci sono suoni di questo tipo: scegline un altro.")
    n = int(prog.get("plays_per_hour", 4))
    if not 1 <= n <= 12:
        raise DeterrentError("Scegli da 1 a 12 riproduzioni all'ora: di più fa abituare gli uccelli e disturba i vicini.")
    secs = float(prog.get("clip_seconds", 4))
    if not 1 <= secs <= 15:
        raise DeterrentError("La durata di ogni riproduzione deve essere tra 1 e 15 secondi.")
    for w in prog.get("windows", []):
        _parse_hhmm(w["start"]), _parse_hhmm(w["end"])
    prog["physical_enabled"] = False  # never enabled from software in this version
    return prog


def _parse_hhmm(s: str) -> int:
    try:
        h, m = (int(x) for x in s.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
        return h * 60 + m
    except Exception as exc:
        raise DeterrentError(f"Orario non valido: {s!r} (usa HH:MM)") from exc


# ---------------- sound ----------------
def _tones(f_lo: float, f_hi: float, seconds: float, rng: np.random.Generator) -> np.ndarray:
    """Irregular chirps and pulses inside the band the target species hears best."""
    n = int(seconds * SR)
    x = np.zeros(n, dtype=np.float32)
    t = 0.0
    while t < seconds - 0.15:
        dur = rng.uniform(0.08, 0.35)
        a, b = rng.uniform(f_lo, f_hi, 2)
        m = int(dur * SR)
        tt = np.arange(m) / SR
        phase = 2 * math.pi * (a * tt + 0.5 * (b - a) / dur * tt * tt)
        i = int(t * SR)
        m = min(m, n - i)
        x[i:i + m] += (np.hanning(m) * np.sin(phase[:m])).astype(np.float32)
        t += dur + rng.uniform(0.05, 0.4)
    return x


def _from_file(path: str, seconds: float, rng: np.random.Generator) -> np.ndarray:
    data, sr = dsp.load_mono(path)
    import librosa
    y = librosa.resample(data.astype(np.float32), orig_sr=sr, target_sr=SR) if sr != SR else data.astype(np.float32)
    y = y[: int(min(len(y) / SR, seconds) * SR)]
    # small random pitch change at every play makes habituation slower
    steps = float(rng.uniform(-1.0, 1.0))
    return librosa.effects.pitch_shift(y, sr=SR, n_steps=steps).astype(np.float32)


def pick_sound(db: Session, prog: dict, rng: np.random.Generator) -> tuple[str, dict]:
    """The file to play this time: the user's recording, or a random clip from the bundled library."""
    if prog.get("recording_id"):
        rec = db.get(AudioRecording, prog["recording_id"])
        if rec is None:
            raise DeterrentError("Registrazione non trovata.")
        return rec.path, {"id": rec.id, "kind": prog["sound_type"], "own_recording": True}
    pool = deterrence.library_for(prog["target"], prog["sound_type"])
    e = pool[int(rng.integers(len(pool)))]
    return str(deterrence.LIBRARY_DIR / e["file"]), e


def preview_wav(db: Session, prog: dict, seed: int | None = None) -> tuple[bytes, dict]:
    prog = validate_program(db, dict(prog))
    rng = np.random.default_rng(seed)
    secs = float(prog.get("clip_seconds", 4))
    if prog["sound_type"] == "tones":
        x = _tones(float(prog["f_lo"]), float(prog["f_hi"]), secs, rng)
        info: dict = {"kind": "tones"}
    else:
        path, info = pick_sound(db, prog, rng)
        x = _from_file(path, secs, rng)
    peak = float(np.max(np.abs(x))) or 1.0
    x = (x / peak * 0.7).astype(np.float32)
    fade = min(len(x) // 10, int(0.05 * SR))
    if fade:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        x[:fade] *= ramp
        x[-fade:] *= ramp[::-1]
    buf = io.BytesIO()
    sf.write(buf, x, SR, format="WAV", subtype="PCM_16")
    return buf.getvalue(), info


# ---------------- devices ----------------
def list_devices(db: Session) -> list[Device]:
    return db.query(Device).filter(Device.hardware_type == HW).all()


def create_device(db: Session, name: str, zone_id: str | None, farm_id: str | None, prog: dict) -> Device:
    prog = validate_program(db, prog)
    n = len(list_devices(db)) + 1
    dev_id = f"DISS-SIM-{n:03d}"
    while db.get(Device, dev_id) is not None:
        n += 1
        dev_id = f"DISS-SIM-{n:03d}"
    d = Device(id=dev_id, name=name, zone_id=zone_id, farm_id=farm_id, hardware_type=HW, source="simulation",
               status="online", last_seen=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc),
               config={"program": prog, "log": []})
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def update_program(db: Session, dev: Device, prog: dict) -> Device:
    prog = validate_program(db, prog)
    cfg = dict(dev.config or {})
    cfg["program"] = prog
    dev.config = cfg
    db.commit()
    db.refresh(dev)
    return dev


def _log(db: Session, dev: Device, reason: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    prog = (dev.config or {}).get("program", {})
    entry = {"ts": now.isoformat(), "reason": reason, "sound_type": prog.get("sound_type"),
             "simulated": True, "physical": False}
    cfg = dict(dev.config or {})
    cfg["log"] = ([entry] + list(cfg.get("log", [])))[:MAX_LOG]
    dev.config = cfg
    dev.last_seen = now
    return entry


def plays_last_hour(dev: Device, now: datetime) -> int:
    since = now - timedelta(hours=1)
    return sum(1 for e in (dev.config or {}).get("log", []) if datetime.fromisoformat(e["ts"]) >= since)


def manual_test(db: Session, dev: Device) -> dict:
    entry = _log(db, dev, "prova manuale")
    db.commit()
    return entry


def plan_day(dev: Device, seed: int | None = None) -> list[str]:
    """When the simulated device would play in the next 24 h (random inside the time windows)."""
    prog = (dev.config or {}).get("program", {})
    rng = random.Random(seed)
    times: list[int] = []
    for w in prog.get("windows", []):
        a, b = _parse_hhmm(w["start"]), _parse_hhmm(w["end"])
        if b <= a:
            b += 24 * 60
        hours = max(1, math.ceil((b - a) / 60))
        k = int(prog.get("plays_per_hour", 4)) * hours
        if prog.get("random_intervals", True):
            times += sorted(rng.randint(a, b - 1) for _ in range(k))
        else:
            step = (b - a) / k
            times += [int(a + i * step) for i in range(k)]
    return [f"{(m // 60) % 24:02d}:{m % 60:02d}" for m in sorted(times)]


def on_detection(db: Session, species_names: list[str], zone_id: str | None) -> list[dict]:
    """Called after a sound analysis: trigger simulated deterrents whose target was heard."""
    fired = []
    now = datetime.now(timezone.utc)
    for dev in list_devices(db):
        prog = (dev.config or {}).get("program", {})
        if not prog.get("trigger_on_detection"):
            continue
        if zone_id and dev.zone_id and dev.zone_id != zone_id:
            continue
        genera = deterrence.PROFILES.get(prog.get("target"), {}).get("genera", [])
        heard = [s for s in species_names if s.split()[0] in genera]
        if not heard:
            continue
        if plays_last_hour(dev, now) >= int(prog.get("plays_per_hour", 4)):
            continue  # respect the hourly cap: more plays only speed up habituation
        entry = _log(db, dev, f"rilevati: {', '.join(heard)}", now)
        name = deterrence.PROFILES[prog["target"]]["name"].lower()
        db.add(Alert(zone_id=dev.zone_id, ts=now, category="bird_deterrent", severity="low",
                     message=f"Sentiti {name} vicino al campo: dissuasore «{dev.name}» attivato (simulazione).",
                     data={"device_id": dev.id, "species": heard}))
        fired.append({"device_id": dev.id, **entry})
    if fired:
        db.commit()
    return fired
