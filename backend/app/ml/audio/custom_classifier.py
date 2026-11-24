"""Trainable classifier for farm-specific sounds (moles, local machinery, pumps...).

Honest by construction:
- trained only on labels a human assigned in the Acoustic Lab
- cross-validated metrics are stored with the model
- below a confidence floor, or far from every training cluster, it answers "unknown"
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MIN_CLASSES = 2
MIN_PER_CLASS_TRAIN = 3
MIN_PER_CLASS_ACTIVATE = 5


def _pipeline() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5)),
    ])


@dataclass
class TrainResult:
    bundle: dict
    metrics: dict
    labels: list[str]
    class_counts: dict[str, int]


def train(X: np.ndarray, y: list[str], feature_version: str) -> TrainResult:
    counts = Counter(y)
    usable = sorted(c for c, n in counts.items() if n >= MIN_PER_CLASS_TRAIN)
    if len(usable) < MIN_CLASSES:
        have = ", ".join(f"«{k}» {v}" for k, v in sorted(counts.items())) or "nessuna"
        raise ValueError(
            f"Servono almeno {MIN_CLASSES} etichette diverse con almeno {MIN_PER_CLASS_TRAIN} esempi ciascuna. "
            f"Ora hai: {have}."
        )
    mask = np.array([lbl in usable for lbl in y])
    X, y_arr = X[mask], np.array(y)[mask]

    n_splits = min(5, min(Counter(y_arr).values()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0)
    y_pred = cross_val_predict(_pipeline(), X, y_arr, cv=cv)
    report = classification_report(y_arr, y_pred, labels=usable, output_dict=True, zero_division=0)
    metrics = {
        "validation": f"verificato su esempi esclusi dall'addestramento ({n_splits} giri)",
        "accuracy": round(float(accuracy_score(y_arr, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_arr, y_pred, average="macro", zero_division=0)), 4),
        "per_class": {c: {k: round(float(report[c][k]), 4) for k in ("precision", "recall", "f1-score", "support")}
                      for c in usable},
        "confusion_matrix": confusion_matrix(y_arr, y_pred, labels=usable).tolist(),
        "labels": usable,
        "excluded_classes": {c: n for c, n in counts.items() if c not in usable},
        "can_activate": all(counts[c] >= MIN_PER_CLASS_ACTIVATE for c in usable),
        "activation_rule": f"almeno {MIN_PER_CLASS_ACTIVATE} esempi etichettati per ogni etichetta",
    }

    model = _pipeline().fit(X, y_arr)
    Z = model.named_steps["scale"].transform(X)
    centroids, radius = {}, {}
    for c in usable:
        pts = Z[y_arr == c]
        centroids[c] = pts.mean(axis=0)
        d = np.linalg.norm(pts - centroids[c], axis=1)
        radius[c] = float(np.percentile(d, 95)) if len(d) else 0.0

    bundle = {"model": model, "centroids": centroids, "radius": radius,
              "feature_version": feature_version, "labels": usable}
    return TrainResult(bundle=bundle, metrics=metrics, labels=usable,
                       class_counts={c: int(counts[c]) for c in usable})


def save(bundle: dict, path: str) -> None:
    joblib.dump(bundle, path)


def load(path: str) -> dict:
    return joblib.load(path)


def predict(bundle: dict, x: np.ndarray, feature_version: str, min_conf: float) -> dict:
    if bundle["feature_version"] != feature_version:
        return {"label": "unknown", "confidence": 0.0,
                "reason": "modello creato con una versione precedente del programma: va riaddestrato"}
    model = bundle["model"]
    probs = model.predict_proba(x.reshape(1, -1))[0]
    classes = list(model.classes_)
    order = np.argsort(probs)[::-1]
    top = classes[order[0]]
    conf = float(probs[order[0]])
    z = model.named_steps["scale"].transform(x.reshape(1, -1))[0]
    dist = float(np.linalg.norm(z - bundle["centroids"][top]))
    limit = bundle["radius"][top] * 1.5 + 1e-6
    ranking = [{"label": classes[i], "probability": round(float(probs[i]), 4)} for i in order]

    if dist > limit:
        return {"label": "unknown", "confidence": round(conf, 4), "ranking": ranking,
                "reason": f"il suono è diverso da tutti gli esempi di «{top}» che hai etichettato: "
                          f"il modello non lo conosce"}
    if conf < min_conf:
        return {"label": "unknown", "confidence": round(conf, 4), "ranking": ranking,
                "reason": f"«{top}» è l'ipotesi migliore ma il modello non è abbastanza sicuro"}
    return {"label": top, "confidence": round(conf, 4), "ranking": ranking,
            "distance_to_class": round(dist, 2), "class_radius_95": round(bundle["radius"][top], 2)}
