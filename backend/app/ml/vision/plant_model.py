"""AGROAI image model for plant diseases.

Features: DINOv2-small (Meta, Apache-2.0) run with onnxruntime on the CPU — the CLS token and the mean of
the patch tokens (768 numbers per photo). Head: a logistic regression trained on public datasets
(PlantDoc, PlantVillage, MultiFruit-6D). Every trained version is saved with its dataset manifest and
its accuracy measured on held-out REAL photos; only a version marked active is used by the diagnosis.
"""
from __future__ import annotations

import io
import json
import logging
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import settings
from app.ml.vision.plant_labels import CLASSES, crop_key

log = logging.getLogger(__name__)
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_lock = threading.Lock()


def backbone_path() -> Path:
    return settings.media_path / "models" / "dinov2_small" / "model.onnx"


def models_dir() -> Path:
    p = settings.media_path / "models" / "plant_clf"
    p.mkdir(parents=True, exist_ok=True)
    return p


@lru_cache(maxsize=1)
def _session():
    import onnxruntime as ort
    path = backbone_path()
    if not path.exists():
        return None
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])


def available() -> bool:
    return _session() is not None


def preprocess(img: Image.Image) -> np.ndarray:
    """Shortest side 256 (bicubic), centre crop 224, ImageNet normalisation -> (3, 224, 224)."""
    img = img.convert("RGB")
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((max(224, round(w * s)), max(224, round(h * s))), Image.BICUBIC)
    w, h = img.size
    left, top = (w - 224) // 2, (h - 224) // 2
    x = np.asarray(img.crop((left, top, left + 224, top + 224)), dtype=np.float32) / 255.0
    return ((x - MEAN) / STD).transpose(2, 0, 1)


def embed_batch(images: list[Image.Image]) -> np.ndarray:
    sess = _session()
    if sess is None:
        raise RuntimeError("modello DINOv2 non scaricato")
    x = np.stack([preprocess(i) for i in images]).astype(np.float32)
    with _lock:
        h = sess.run(None, {"pixel_values": x})[0]  # (n, 1 + patches, 384)
    feats = np.concatenate([h[:, 0], h[:, 1:].mean(axis=1)], axis=1)
    return feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8)


def embed(content: bytes | Image.Image) -> np.ndarray:
    img = content if isinstance(content, Image.Image) else Image.open(io.BytesIO(content))
    return embed_batch([img])[0]


# ---------------- trained heads ----------------
def versions() -> list[dict]:
    out = []
    for d in sorted(models_dir().glob("v*")):
        card = d / "card.json"
        if card.exists():
            out.append(json.loads(card.read_text(encoding="utf-8")))
    return out


def active_version() -> str | None:
    f = models_dir() / "ACTIVE"
    return f.read_text().strip() if f.exists() else None


def set_active(version: str | None) -> None:
    f = models_dir() / "ACTIVE"
    if version is None:
        f.unlink(missing_ok=True)
    else:
        if not (models_dir() / version / "card.json").exists():
            raise ValueError("versione non trovata")
        f.write_text(version)
    _load_head.cache_clear()


@lru_cache(maxsize=2)
def _load_head(version: str):
    import joblib
    d = models_dir() / version
    return joblib.load(d / "head.joblib"), json.loads((d / "card.json").read_text(encoding="utf-8"))


def predict(content: bytes, crop_hint: str | None = None, organs: list[str] | None = None,
            top_k: int = 5) -> dict | None:
    """Top classes for a photo, or None when no model is active or the backbone is missing.

    If the crop is known, only that crop's classes are compared (probabilities renormalised).
    "applicable" is False when the model was not trained for this crop or for the organs in the photo.
    """
    version = active_version()
    if not version or not available():
        return None
    try:
        clf, card = _load_head(version)
        p = clf.predict_proba(embed(content)[None, :])[0]
    except Exception as exc:  # never break the photo analysis because of the extra model
        log.warning("plant model failed: %s", exc)
        return None
    labels = list(clf.classes_)
    crops_known = sorted({lab.split("/")[0] for lab in labels})
    crop = crop_key(crop_hint)
    notes: list[str] = []
    applicable = True
    if crop and crop not in crops_known:
        applicable = False
        notes.append("Il modello non è stato addestrato su questa coltura.")
    elif crop:
        mask = np.array([lab.startswith(crop + "/") for lab in labels])
        p = np.where(mask, p, 0.0)
        p = p / (p.sum() or 1.0)
    organs_trained = {CLASSES[lab][2] for lab in labels if not crop or lab.startswith(crop + "/")}
    seen = set(organs or [])
    # fruit only counts if the model learnt both healthy and diseased fruit of this crop: with diseased
    # examples alone it would call every fruit diseased
    crop_labels = [lab for lab in labels if not crop or lab.startswith(crop + "/")]
    fruit_classes = [lab for lab in crop_labels if CLASSES[lab][2] == "fruit"]
    fruit_ok = any(CLASSES[lab][1] == "healthy" for lab in fruit_classes) and len(fruit_classes) >= 2
    if not fruit_ok:
        organs_trained = organs_trained - {"fruit"}
        if fruit_classes and "fruit" in set(organs or []):
            notes.append("Per i frutti di questa coltura il modello conosce solo alcune malattie e nessun frutto sano: "
                         "risponderebbe sempre «malato», quindi qui non viene usato.")
    # a leaf-only model looking at fruit is outside what it learnt, even if some leaves are visible too
    if applicable and "fruit" in seen and "fruit" not in organs_trained:
        seen = {"fruit"}
    if applicable and seen and not (seen & organs_trained):
        applicable = False
        if not notes:
            notes.append("Nella foto ci sono " + ", ".join({"fruit": "frutti", "leaf": "foglie", "stem": "fusti"}.get(o, o)
                                                        for o in sorted(seen)) +
                     ": per questa coltura il modello conosce solo " +
                     ", ".join({"fruit": "frutti", "leaf": "foglie"}[o] for o in sorted(organs_trained)) + ".")
    order = np.argsort(-p)[:top_k]
    top = [{"label": labels[i], "name": CLASSES[labels[i]][0], "cause": CLASSES[labels[i]][1],
            "organ": CLASSES[labels[i]][2], "score": round(float(p[i]), 3)} for i in order if p[i] > 0]
    by_cause: dict[str, float] = {}
    for lab, pi in zip(labels, p):
        cid = CLASSES[lab][1]
        if cid:
            by_cause[cid] = by_cause.get(cid, 0.0) + float(pi)
    if applicable and "fruit" in seen and fruit_ok and crop:
        known_fruit = [CLASSES[lab][0].split(" – ", 1)[-1] for lab in fruit_classes]
        notes.append("Sui frutti di questa coltura il modello conosce solo: " + ", ".join(known_fruit) +
                     ". Se è un'altra malattia (es. peronospora, marciume apicale) sceglie la più simile tra queste.")
    # which knowledge-base causes the model can recognise on the organs in this photo (for this crop)
    # photos with fruit are dominated by the fruit: judge them by what the model knows about fruit
    look_organs = ({"fruit"} & organs_trained if "fruit" in seen else seen & organs_trained) or organs_trained
    known_causes = sorted({CLASSES[lab][1] for lab in crop_labels
                           if CLASSES[lab][1] and CLASSES[lab][2] in look_organs})
    m = card["metrics"]
    return {"version": version, "known_causes": known_causes, "organs_used": sorted(look_organs), "top": top, "by_cause": {k: round(v, 3) for k, v in by_cause.items()},
            "applicable": applicable, "crop": crop, "notes": notes, "crops_known": crops_known,
            "real_photo_accuracy": m["real_photos"]["top1"], "real_photo_top3": m["real_photos"]["top3"],
            "cause_accuracy": m["real_photos"]["cause_top1"],
            "datasets": [v["name"] for v in card["datasets"].values() if v.get("train")]}
