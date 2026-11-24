"""Train AGROAI's plant-disease image model on public datasets.

    python scripts/train_plant_model.py --data C:/Users/<you>/agroai-data/datasets [--activate]

Datasets are read from --data (keep them OUTSIDE OneDrive: several GB):
  plantdoc/{train,test}/<class>/*      real photos, official split          (CC BY 4.0)
  plantvillage/raw/color/<class>/*     lab photos, training only            (CC BY-SA 3.0)
  multifruit6d/<root>/<class>/*        real fruit photos, 80/20 split       (CC BY 4.0)

Accuracy is measured ONLY on real photos never used for training. A new version is saved next to the
old ones and is used by the app only when activated (--activate or from the API).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import devenv  # noqa: E402

devenv.apply()
from app.ml.vision import plant_model  # noqa: E402
from app.ml.vision.plant_labels import CLASSES, DATASETS, MULTIFRUIT, PLANTDOC, PLANTVILLAGE  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect(data: Path, seed: int = 7) -> list[dict]:
    items: list[dict] = []
    for split in ("train", "test"):
        for d in sorted((data / "plantdoc" / split).glob("*")):
            if d.name in PLANTDOC:
                items += [{"path": str(f), "label": PLANTDOC[d.name], "dataset": "plantdoc", "split": split}
                          for f in sorted(d.iterdir()) if f.suffix.lower() in IMG_EXT]
    for d in sorted((data / "plantvillage" / "raw" / "color").glob("*")):
        if d.name in PLANTVILLAGE:
            items += [{"path": str(f), "label": PLANTVILLAGE[d.name], "dataset": "plantvillage", "split": "train"}
                      for f in sorted(d.iterdir()) if f.suffix.lower() in IMG_EXT]
    rng = random.Random(seed)
    for d in sorted((data / "multifruit6d").glob("*/*")):
        if d.name in MULTIFRUIT:
            files = sorted(f for f in d.iterdir() if f.suffix.lower() in IMG_EXT)
            rng.shuffle(files)
            cut = int(len(files) * 0.8)
            items += [{"path": str(f), "label": MULTIFRUIT[d.name], "dataset": "multifruit6d",
                       "split": "train" if i < cut else "test"} for i, f in enumerate(files)]
    # Hugging Face datasets prepared by prepare_hf_datasets.py (split already decided, by source photo)
    for ds_dir in sorted((data / "hf_extracted").glob("*")):
        for split in ("train", "test"):
            for d in sorted((ds_dir / split).glob("*")):
                label = d.name.replace("__", "/")
                if label in CLASSES:
                    items += [{"path": str(f), "label": label, "dataset": ds_dir.name, "split": split}
                              for f in sorted(d.iterdir()) if f.suffix.lower() in IMG_EXT]
    return items


def embed_all(items: list[dict], cache: Path, batch: int = 16) -> np.ndarray:
    store: dict[str, np.ndarray] = {}
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        store = dict(zip(z["keys"].tolist(), z["feats"]))
    key = lambda p: hashlib.sha1(p.encode()).hexdigest()  # noqa: E731
    todo = [it for it in items if key(it["path"]) not in store]
    t0 = time.time()
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        imgs = []
        for it in chunk:
            try:
                imgs.append(Image.open(it["path"]).convert("RGB"))
            except Exception:
                imgs.append(Image.new("RGB", (224, 224)))
                it["broken"] = True
        for it, f in zip(chunk, plant_model.embed_batch(imgs)):
            store[key(it["path"])] = f
        if (i // batch) % 20 == 0:
            done = i + len(chunk)
            print(f"  embedded {done}/{len(todo)}  {done / max(1e-6, time.time() - t0):.1f} img/s", flush=True)
            np.savez(cache, keys=np.array(list(store)), feats=np.stack(list(store.values())))
    if todo:
        np.savez(cache, keys=np.array(list(store)), feats=np.stack(list(store.values())))
    return np.stack([store[key(it["path"])] for it in items])


def drop_near_duplicates(X_tr: np.ndarray, X_te: np.ndarray, thr: float = 0.97) -> np.ndarray:
    """Test photos almost identical to a training photo would inflate the score: drop them."""
    sims = X_te @ X_tr.T
    return sims.max(axis=1) < thr


def topk(clf, X, y, k: int) -> float:
    if len(y) == 0:
        return float("nan")
    p = clf.predict_proba(X)
    cls = np.array(clf.classes_)
    best = np.argsort(-p, axis=1)[:, :k]
    return float(np.mean([yy in cls[b] for yy, b in zip(y, best)]))


def cause_acc(clf, X, y) -> float:
    pred = np.array(clf.classes_)[clf.predict_proba(X).argmax(1)]
    return float(np.mean([CLASSES[a][1] == CLASSES[b][1] for a, b in zip(pred, y)]))


def fit(X, y, C: float):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=C, max_iter=4000, class_weight="balanced").fit(X, y)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--activate", action="store_true")
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    data = Path(args.data)

    items = collect(data)
    print("images:", Counter((it["dataset"], it["split"]) for it in items))
    X = embed_all(items, data / "dinov2_small_features.npz")
    ok = np.array([not it.get("broken") for it in items])
    y = np.array([it["label"] for it in items])
    ds = np.array([it["dataset"] for it in items])
    is_train = np.array([it["split"] == "train" for it in items])
    te = ~is_train & ok
    # Lab photos (PlantVillage) lower the accuracy on real photos for classes that also have real photos
    # (measured: 75.5% -> 77.1% top-1 on real photos when they are left out): use them only for the
    # diseases that have no real training photos, so those classes are still recognised.
    real_classes = set(y[is_train & ok & (ds != "plantvillage")])
    tr = is_train & ok & ((ds != "plantvillage") | ~np.isin(y, list(real_classes)))
    keep = drop_near_duplicates(X[tr], X[te])
    te_idx = np.where(te)[0][keep]
    dropped = int((~keep).sum())
    print(f"real-photo test set: {len(te_idx)} photos ({dropped} near-duplicates of training photos removed)")

    # choose C on a validation split of the REAL training photos (PlantVillage stays in training)
    real_tr = np.where(tr & (ds != "plantvillage"))[0]
    rng = np.random.default_rng(0)
    val = rng.choice(real_tr, size=len(real_tr) // 5, replace=False)
    fit_idx = np.setdiff1d(np.where(tr)[0], val)
    grid = {}
    for C in (0.5, 1, 2, 5, 10, 20):
        grid[C] = topk(fit(X[fit_idx], y[fit_idx], C), X[val], y[val], 1)
        print(f"  C={C:<4} validation top-1 on real photos: {grid[C]:.3f}")
    C = max(grid, key=grid.get)

    clf = fit(X[tr], y[tr], C)
    # how much do lab photos alone generalise to real photos? (kept in the card for honesty)
    pv_all = is_train & ok & (ds == "plantvillage")
    pv_only = fit(X[pv_all], y[pv_all], C)
    pd_te = te_idx[ds[te_idx] == "plantdoc"]
    pv_classes = set(pv_only.classes_)
    pd_te_pv = np.array([i for i in pd_te if y[i] in pv_classes], dtype=int)

    def block(idx):
        if len(idx) == 0:
            return None
        return {"n": int(len(idx)), "top1": round(topk(clf, X[idx], y[idx], 1), 3),
                "top3": round(topk(clf, X[idx], y[idx], 3), 3), "cause_top1": round(cause_acc(clf, X[idx], y[idx]), 3)}

    per_class = {}
    pred = np.array(clf.classes_)[clf.predict_proba(X[te_idx]).argmax(1)]
    for lab in sorted(set(y[te_idx])):
        m = y[te_idx] == lab
        per_class[lab] = {"n": int(m.sum()), "top1": round(float(np.mean(pred[m] == lab)), 3)}
    confusions = Counter((a, b) for a, b in zip(y[te_idx], pred) if a != b).most_common(10)
    tomato = te_idx[np.char.startswith(y[te_idx].astype(str), "tomato/")]
    fruit = te_idx[[CLASSES[l][2] == "fruit" for l in y[te_idx]]]

    version = args.version or f"v{len(plant_model.versions()) + 1}"
    out = plant_model.models_dir() / version
    out.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump(clf, out / "head.joblib")
    card = {
        "version": version, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backbone": {"name": "DINOv2-small (Meta)", "licence": "Apache-2.0", "features": "CLS + media dei patch, 768"},
        "head": {"type": "LogisticRegression", "C": C, "class_weight": "balanced",
                 "lab_photos": "solo per le classi senza foto reali"},
        "classes": sorted(set(y[tr])),
        "datasets": {k: {**DATASETS[k], "train": int((tr & (ds == k)).sum()), "test": int((ds[te_idx] == k).sum())}
                     for k in DATASETS},
        "metrics": {
            "real_photos": block(te_idx),
            "plantdoc_test": block(pd_te),
            "multifruit_test": block(te_idx[ds[te_idx] == "multifruit6d"]),
            "tomato_greenhouse_test": block(te_idx[ds[te_idx] == "tomato_liu"]),
            "citrus_test": block(te_idx[ds[te_idx] == "citrus_fl"]),
            "vegetables_test": block(te_idx[ds[te_idx] == "veg_leaf"]),
            "tomato_fruit": block(te_idx[[l.startswith("tomato/") and CLASSES[l][2] == "fruit" for l in y[te_idx]]]),
            "v2_test_set": block(te_idx[np.isin(ds[te_idx], ["plantdoc", "multifruit6d"])]),
            "tomato_leaves": block(tomato),
            "fruits": block(fruit),
            "lab_only_model_on_real_photos": round(topk(pv_only, X[pd_te_pv], y[pd_te_pv], 1), 3),
            "near_duplicates_removed": dropped,
        },
        "per_class": per_class,
        "top_confusions": [{"true": a, "predicted": b, "n": n} for (a, b), n in confusions],
        "limits": ["Per i frutti: mela e agrumi (sano/malato, malattie degli agrumi) e solo la MUFFA GRIGIA sul pomodoro.",
                   "Pochi esempi di frutti di pomodoro malati (muffa grigia): per peronospora, marciume apicale e "
                   "scottatura sul frutto decidono l'analisi visiva e le domande.",
                   "Riconosce solo le classi elencate: per altre colture o malattie non è affidabile."],
    }
    (out / "card.json").write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(card["metrics"], indent=1))
    print("worst classes:", sorted(per_class.items(), key=lambda kv: kv[1]["top1"])[:8])
    print("confusions:", card["top_confusions"][:6])
    if args.activate:
        plant_model.set_active(version)
        print("ACTIVE ->", version)
    print("saved", out)


if __name__ == "__main__":
    main()
