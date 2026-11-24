"""Google Perch 2.0 — multi-taxa bioacoustic classifier (Apache-2.0).

~14,600 species (birds, amphibians, insects, mammals…) + 198 FSD50K sound events.
ONNX conversion from huggingface.co/tphakala/Perch-v2-Models, run with ONNX Runtime on CPU.
Input: 5 s windows at 32 kHz. Output per window: one logit per class and a 1536-d embedding.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

from app.config import settings

log = logging.getLogger("agroai.perch")

SR = 32000
WIN = 5 * SR
HOP = WIN // 2
BASE_URL = "https://huggingface.co/tphakala/Perch-v2-Models/resolve/main/full/"
MODEL_FILE = "perch_v2_no_dft_fp32.onnx"
LABELS_FILE = "perch_v2_labels.txt"
MODEL_SHA256 = "4dcf71c18a147198545944bb5149697e89e3ad2e16637fa8f0edf6d13035a017"
_SPECIES_RE = re.compile(r"[A-Z][a-z]+ '?[a-z\-]+'?( [a-z\-]+)?")
# Perch's general sound classes that reveal an animal of a given group.
SOUND_GROUPS = {
    "bird": ["Chirp_and_tweet", "Crow", "Fowl", "Chicken_and_rooster", "Gull_and_seagull"],
    "insect": ["Insect", "Cricket", "Buzz"],
    "amphibian": ["Frog"],
    "mammal": ["Dog", "Bark", "Cat", "Meow", "Purr", "Growling", "Livestock_and_farm_animals_and_working_animals",
               "Domestic_animals_and_pets"],
    "animal": ["Animal", "Wild_animals"],
}

_session = None
_labels: list[str] = []
_is_species: np.ndarray | None = None
_error: str | None = None
_lock = threading.Lock()
_infer_lock = threading.Lock()


def model_dir() -> Path:
    p = settings.media_path / "models" / "perch_v2"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _download(name: str) -> None:
    dst = model_dir() / name
    log.info("downloading %s …", name)
    part = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(BASE_URL + name, timeout=120) as r, open(part, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    part.replace(dst)


def _load() -> bool:
    global _session, _labels, _is_species, _error
    if _session is not None:
        return True
    if _error is not None:
        return False
    with _lock:
        if _session is not None:
            return True
        try:
            import onnxruntime as ort  # type: ignore
            d = model_dir()
            for name in (LABELS_FILE, MODEL_FILE):
                if not (d / name).exists():
                    _download(name)
            _labels = (d / LABELS_FILE).read_text(encoding="utf-8").splitlines()[1:]
            _is_species = np.array([bool(_SPECIES_RE.fullmatch(l)) for l in _labels])
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            _session = ort.InferenceSession(str(d / MODEL_FILE), opts, providers=["CPUExecutionProvider"])
            log.info("Perch 2.0 loaded: %d classes (%d species)", len(_labels), int(_is_species.sum()))
            return True
        except Exception as exc:
            _error = f"{type(exc).__name__}: {exc}"
            log.warning("Perch unavailable: %s", _error)
            return False


def status() -> dict:
    ok = _load()
    return {"available": ok, "classes": len(_labels), "species": int(_is_species.sum()) if ok else 0,
            "error": _error, "license": "Apache-2.0"}


def _windows(y32: np.ndarray) -> np.ndarray:
    if len(y32) < WIN:
        y32 = np.pad(y32, (0, WIN - len(y32)))
    starts = list(range(0, len(y32) - WIN + 1, HOP))
    if starts[-1] + WIN < len(y32):  # keep the tail
        starts.append(len(y32) - WIN)
    return np.stack([y32[s:s + WIN] for s in starts]).astype(np.float32), starts


def _resample(y: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return y.astype(np.float32)
    import librosa
    return librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=SR)


def _infer(batch: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    name = _session.get_inputs()[0].name
    logits, embs = [], []
    with _infer_lock:
        for i in range(0, len(batch), 8):
            out = dict(zip(["label", "embedding"], _session.run(["label", "embedding"], {name: batch[i:i + 8]})))
            logits.append(out["label"])
            embs.append(out["embedding"])
    return np.vstack(logits), np.vstack(embs)


_baseline: np.ndarray | None = None
MARGIN_MID = 3.0  # logits above the noise baseline that map to a score of 0.5


def _background_set() -> list[np.ndarray]:
    """Synthetic backgrounds that contain no animal: the model's response to them is its 'false alarm' level."""
    rng = np.random.default_rng(1234)
    n = WIN
    white = rng.standard_normal(n)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec = np.fft.rfft(rng.standard_normal(n))
    pink = np.fft.irfft(spec / np.sqrt(np.maximum(f, 1.0)), n)
    brown = np.fft.irfft(spec / np.maximum(f, 1.0), n)
    wind = np.fft.irfft(spec * (f < 300), n) * (1 + 0.6 * np.sin(2 * np.pi * 0.4 * np.arange(n) / SR))
    rain = np.zeros(n)
    rain[rng.integers(0, n, 400)] = rng.uniform(0.2, 1.0, 400)
    rain = np.convolve(rain, np.exp(-np.arange(200) / 20.0), mode="same") + 0.05 * white
    hum = sum(np.sin(2 * np.pi * 50 * k * np.arange(n) / SR) / k for k in range(1, 6))
    out = []
    for sig in (white, pink, brown, wind, rain, hum):
        sig = sig / (np.max(np.abs(sig)) or 1.0)
        for level in (0.01, 0.1, 0.5):
            out.append((sig * level).astype(np.float32))
    return out


def _load_baseline() -> np.ndarray:
    global _baseline
    if _baseline is not None:
        return _baseline
    path = model_dir() / "noise_baseline_v1.npy"
    if path.exists():
        _baseline = np.load(path)
    else:
        logits, _ = _infer(np.stack(_background_set()))
        _baseline = logits.max(axis=0).astype(np.float32)
        np.save(path, _baseline)
    return _baseline


def score(logits: np.ndarray) -> np.ndarray:
    """0..1 score from how far each logit rises above what pure background noise produces
    for that class. Not a calibrated probability."""
    margin = logits - _load_baseline()
    return 1.0 / (1.0 + np.exp(-(margin - MARGIN_MID)))


def embed(y: np.ndarray, sr: int) -> np.ndarray | None:
    """Mean Perch embedding of a clip — used as features for the farm-trained model."""
    if not _load():
        return None
    batch, _ = _windows(_resample(y, sr))
    _, embs = _infer(batch)
    return embs.mean(axis=0)


def analyze(y: np.ndarray, sr: int, top_k: int = 8, min_score: float = 0.1,
            allowed: set[str] | None = None) -> dict:
    """allowed: scientific names plausible at the farm (local species list). Others are ignored."""
    if not _load():
        return {"available": False, "error": _error}
    t0 = time.time()
    y32 = np.clip(_resample(y, sr), -1.0, 1.0)  # keep the real level: boosting silence turns hiss into "animals"
    rms_db = 20 * np.log10(float(np.sqrt(np.mean(y32 ** 2))) + 1e-12)
    if rms_db < -65:
        return {"available": True, "model": "Perch 2.0 (Google DeepMind)", "windows": 0, "seconds": 0.0,
                "species": [], "sound_events": [], "note": "registrazione quasi silenziosa"}
    batch, starts = _windows(y32)
    logits, _ = _infer(batch)
    s = score(logits)  # (windows, classes)
    best = s.max(axis=0)

    mask = _is_species & (best >= min_score)
    excluded = 0
    if allowed is not None:
        local = np.array([l in allowed for l in _labels])
        excluded = int((mask & ~local).sum())
        mask &= local
    species_idx = np.where(mask)[0]
    species_idx = species_idx[np.argsort(best[species_idx])[::-1]][:top_k]
    detections = []
    for i in species_idx:
        hits = np.where(s[:, i] >= min_score)[0]
        detections.append({
            "scientific_name": _labels[i],
            "score": round(float(best[i]), 4),
            "start_s": round(starts[hits[0]] / SR, 1),
            "end_s": round((starts[hits[-1]] + WIN) / SR, 1),
            "windows": int(len(hits)),
        })
    sound_idx = np.where(~_is_species)[0]
    sound_idx = sound_idx[np.argsort(best[sound_idx])[::-1]][:5]
    sounds = [{"label": _labels[i].replace("_", " "), "score": round(float(best[i]), 4)} for i in sound_idx]
    index = {l: i for i, l in enumerate(_labels)}
    group_evidence = {g: round(float(max(best[index[n]] for n in names if n in index)), 4)
                      for g, names in SOUND_GROUPS.items()}
    return {
        "available": True,
        "model": "Perch 2.0 (Google DeepMind)",
        "windows": int(len(starts)),
        "seconds": round(time.time() - t0, 2),
        "species": detections,
        "sound_events": sounds,
        "group_evidence": group_evidence,
        "excluded_not_local": excluded,
        "local_filter": allowed is not None,
    }
