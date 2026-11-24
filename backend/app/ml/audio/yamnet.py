"""YAMNet (Google, Apache-2.0) — 521 AudioSet classes.

Uses Google's official TFLite build (labels embedded in the model file),
downloaded once into MEDIA_ROOT/models. Each frame is 0.975 s with a 0.48 s hop,
as in the reference implementation. Scores are per-class sigmoid outputs,
NOT calibrated probabilities.
"""
from __future__ import annotations

import io
import logging
import threading
import urllib.request
import zipfile

import numpy as np

from app.config import settings

log = logging.getLogger("agroai.yamnet")

YAMNET_HANDLE = ("https://storage.googleapis.com/download.tensorflow.org/models/tflite/task_library/"
                 "audio_classification/android/lite-model_yamnet_classification_tflite_1.tflite")
FRAME_LEN = 15600
FRAME_HOP = 7680
FRAME_HOP_S = FRAME_HOP / 16000

_model = None
_labels: list[str] = []
_load_error: str | None = None
_lock = threading.Lock()
_infer_lock = threading.Lock()

# Keyword → group. Order matters: first match wins ("crowing" is poultry, not crow).
GROUPS: list[tuple[str, str, list[str]]] = [
    # machines first: "Vehicle horn, car horn, honking" must not match the goose "honk"
    ("machinery_vehicle", "context", ["vehicle", "engine", "motor", "truck", "tractor", "lawn mower", "chainsaw",
                                      "mechanical fan", "idling", "power tool", "drill", "helicopter", "aircraft",
                                      "train", "rail", "car ", "car,", "horn"]),
    ("poultry_waterfowl", "animal", ["chicken", "rooster", "cluck", "crowing", "turkey", "gobble",
                                     "duck", "quack", "goose", "honk", "fowl"]),
    ("bird", "animal", ["bird", "chirp", "tweet", "squawk", "pigeon", "dove", "coo", "crow", "caw",
                        "owl", "hoot", "gull"]),
    ("insect", "animal", ["insect", "cricket", "mosquito", "fly, housefly", "bee, wasp", "buzz"]),
    ("amphibian", "animal", ["frog", "croak"]),
    ("rodent", "animal", ["rodent", "mouse", "rats"]),
    ("dog_canid", "animal", ["dog", "bark", "yip", "howl", "bow-wow", "growling", "whimper (dog)", "canidae"]),
    # "Hiss" is a generic class (water spray, steam, gas, wind on the mic): in a field it is almost never a cat
    ("hiss_noise", "context", ["hiss", "steam", "white noise", "pink noise", "static"]),
    ("cat_feline", "animal", ["cat", "purr", "meow", "caterwaul", "roaring cats"]),
    # "Livestock, farm animals, working animals" is a parent class that also covers poultry
    ("farm_animal", "animal", ["livestock, farm animals"]),
    ("livestock", "animal", ["horse", "clip-clop", "neigh", "cattle", "moo", "cowbell",
                             "pig", "oink", "goat", "bleat", "sheep"]),
    ("crackle_impact", "context", ["crackle", "fire", "crack", "crumpling", "rub", "scrape", "sawing"]),
    # AudioSet "Snake" (hiss/rattle) fires on cricket trills AND on water spray: decided later with Perch
    ("snake_rattle", "ambiguous", ["snake"]),
    ("wild_animal", "animal", ["wild animals", "animal", "roar"]),
    ("water_irrigation", "context", ["rain", "raindrop", "water", "stream", "splash", "pour", "trickle",
                                     "drip", "gurgling", "liquid", "spray", "pump (liquid)", "sprinkler", "hose"]),
    ("wind_vegetation", "context", ["wind", "rustling", "rustle"]),
    ("human", "context", ["speech", "conversation", "shout", "laughter", "footsteps", "whistling", "singing"]),
    ("silence", "context", ["silence"]),
]


def group_for(label: str) -> tuple[str, str]:
    low = label.lower()
    for name, kind, keys in GROUPS:
        if any(k in low for k in keys):
            return name, kind
    return "other", "context"


def _load() -> bool:
    global _model, _labels, _load_error
    if _model is not None:
        return True
    if _load_error is not None:
        return False
    with _lock:
        if _model is not None:
            return True
        try:
            path = settings.media_path / "models" / "yamnet.tflite"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                log.info("downloading YAMNet TFLite model…")
                blob = urllib.request.urlopen(YAMNET_HANDLE, timeout=120).read()
                path.write_bytes(blob)
            blob = path.read_bytes()
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                _labels = z.read("yamnet_label_list.txt").decode().splitlines()
            try:
                from ai_edge_litert.interpreter import Interpreter  # type: ignore
            except ImportError:
                import tensorflow as tf  # type: ignore
                Interpreter = tf.lite.Interpreter
            it = Interpreter(model_content=blob)
            it.allocate_tensors()
            _model = it
            log.info("YAMNet loaded (%d classes)", len(_labels))
            return True
        except Exception as exc:  # missing TF, no network on first run, ...
            _load_error = f"{type(exc).__name__}: {exc}"
            log.warning("YAMNet unavailable: %s", _load_error)
            return False


def _frame_scores(wav: np.ndarray) -> np.ndarray:
    if len(wav) < FRAME_LEN:
        wav = np.pad(wav, (0, FRAME_LEN - len(wav)))
    starts = range(0, len(wav) - FRAME_LEN + 1, FRAME_HOP)
    inp = _model.get_input_details()[0]["index"]
    out = _model.get_output_details()[0]["index"]
    rows = []
    with _infer_lock:  # the interpreter is not thread-safe
        for s in starts:
            _model.set_tensor(inp, wav[s:s + FRAME_LEN])
            _model.invoke()
            rows.append(_model.get_tensor(out)[0].copy())
    return np.vstack(rows)


def status() -> dict:
    loaded = _load()
    return {"available": loaded, "classes": len(_labels), "error": _load_error, "handle": YAMNET_HANDLE}


def analyze(waveform_16k: np.ndarray, top_k: int = 8) -> dict:
    if not _load():
        return {"available": False, "error": _load_error}

    wav = np.clip(waveform_16k.astype(np.float32), -1.0, 1.0)
    s = _frame_scores(wav)  # (frames, 521)
    frame_max = s.max(axis=0)
    frame_mean = s.mean(axis=0)
    idx = np.argsort(frame_max)[::-1][:top_k]
    top = [{"label": _labels[i], "max_score": round(float(frame_max[i]), 4),
            "mean_score": round(float(frame_mean[i]), 4),
            "group": group_for(_labels[i])[0]} for i in idx]

    groups: dict[str, dict] = {}
    for i, lbl in enumerate(_labels):
        g, kind = group_for(lbl)
        if g == "other":
            continue
        sc = float(frame_max[i])
        cur = groups.get(g)
        if cur is None or sc > cur["score"]:
            groups[g] = {"group": g, "kind": kind, "score": round(sc, 4), "best_class": lbl}

    generic = {i for i, lbl in enumerate(_labels) if lbl in ("Animal", "Wild animals", "Domestic animals, pets")}
    timeline = []
    for fi, row in enumerate(s):
        order = np.argsort(row)[::-1]
        j = int(order[0])
        # prefer the most specific class when a parent class (e.g. "Animal") wins narrowly
        for k in order[:5]:
            if int(k) not in generic and row[k] >= 0.5 * row[j]:
                j = int(k)
                break
        timeline.append({"t": round(fi * FRAME_HOP_S, 2), "label": _labels[j],
                         "group": group_for(_labels[j])[0], "score": round(float(row[j]), 3)})

    return {
        "available": True,
        "frames": int(s.shape[0]),
        "top_classes": top,
        "groups": sorted(groups.values(), key=lambda g: g["score"], reverse=True),
        "timeline": timeline,
    }
