"""Turn the Hugging Face parquet datasets into image folders for train_plant_model.py.

    python scripts/prepare_hf_datasets.py --data C:/Users/<you>/agroai-data/datasets

Reads   <data>/hf/{tomato_liu,citrus_fl,veg_leaf}/*.parquet
Writes  <data>/hf_extracted/<dataset>/<train|test>/<class>/<n>.jpg

- tomato_liu (Liu 2025, CC BY 4.0): object-detection boxes are cropped one by one, so each image shows ONE
  plant part with ONE disease (fruit with grey mould, leaf with virus, wilted stem...). Train/test split is
  by SOURCE photo, so crops of the same photo never end up on both sides.
- citrus_fl (CC BY 4.0) and veg_leaf (CC BY 4.0): whole images, 80/20 split.
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image, ImageOps

TOMATO_CATS = {0: "tomato/grey_mould_fruit", 1: "tomato/grey_mould_leaf", 2: "tomato/viral", 3: "tomato/viral",
               4: "tomato/viral", 5: "tomato/bacterial_wilt", 6: "tomato/bacterial_wilt", 7: "tomato/bacterial_wilt",
               8: "tomato/bacterial_wilt", 9: "tomato/bacterial_wilt"}
CITRUS = {("black_spot", "fruit"): "citrus/fruit_black_spot", ("canker", "fruit"): "citrus/fruit_canker",
          ("greening", "fruit"): "citrus/fruit_greening", ("healthy", "fruit"): "citrus/fruit_healthy",
          ("melanose", "fruit"): "citrus/fruit_melanose", ("scab", "fruit"): "citrus/fruit_scab",
          ("black_spot", "leaf"): "citrus/black_spot", ("canker", "leaf"): "citrus/canker",
          ("greening", "leaf"): "citrus/greening", ("healthy", "leaf"): "citrus/leaf_healthy",
          ("melanose", "leaf"): "citrus/melanose", ("scab", "leaf"): "citrus/scab"}
VEG = {
    "Broccoli Alternaria black spot": "broccoli/alternaria", "Broccoli Black rot": "broccoli/black_rot",
    "Broccoli Health leaf": "broccoli/healthy", "Cabbage Alternaria leaf spot": "cabbage/alternaria",
    "Cabbage Damaged by white butterfly": "cabbage/cabbage_white", "Cabbage Grey mould disease": "cabbage/grey_mould",
    "Cabbage Healthy leaf": "cabbage/healthy", "Cabbage Tip burn": "cabbage/tip_burn",
    "Cauliflower Alternaria Curd  spot": "cauliflower/curd_alternaria",
    "Cauliflower Alternaria leaf spot": "cauliflower/alternaria", "Cauliflower Bacterial soft rot": "cauliflower/soft_rot",
    "Cauliflower Healthy leaf": "cauliflower/healthy", "Cauliflower Yellow virus": "cauliflower/virus",
    "Turnip Alternaria leaf spot": "turnip/alternaria", "Turnip Black rot": "turnip/black_rot",
    "Turnip Healthy leaf": "turnip/healthy",
}
MAX_SIDE = 640
MIN_BOX = 120          # smaller boxes have too little detail
MAX_CROPS_PER_PHOTO = 3


def _open(cell, upright: bool = True) -> Image.Image:
    img = Image.open(io.BytesIO(cell["bytes"]))
    return (ImageOps.exif_transpose(img) if upright else img).convert("RGB")


def _save(img: Image.Image, path: Path) -> None:
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=90)


def class_names(pf: pq.ParquetFile, col: str) -> list[str]:
    hf = json.loads((pf.schema_arrow.metadata or {}).get(b"huggingface", b"{}") or "{}")
    return hf.get("info", {}).get("features", {}).get(col, {}).get("names", [])


def tomato(src: Path, out: Path, rng: random.Random) -> Counter:
    c: Counter = Counter()
    n = 0
    for f in sorted(src.glob("*.parquet")):
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=8, columns=["image", "objects"]):
            for img_cell, objs in zip(batch.column("image").to_pylist(), batch.column("objects").to_pylist()):
                split = "test" if rng.random() < 0.2 else "train"
                img = _open(img_cell, upright=False)  # boxes refer to the stored pixel orientation
                W, H = img.size
                boxes = list(zip(objs["bbox"], objs["categories"]))
                rng.shuffle(boxes)
                # always keep fruit boxes (rare and the most useful), then the others up to the limit
                boxes.sort(key=lambda b: b[1] != 0)
                for (x, y, w, h), cat in boxes[:MAX_CROPS_PER_PHOTO]:
                    if min(w, h) < MIN_BOX:
                        continue
                    pad = 0.08
                    box = (max(0, x - w * pad), max(0, y - h * pad), min(W, x + w * (1 + pad)), min(H, y + h * (1 + pad)))
                    if box[2] - box[0] < MIN_BOX or box[3] - box[1] < MIN_BOX:
                        continue  # box outside the image or too small after clipping
                    label = TOMATO_CATS[cat]
                    _save(img.crop(box), out / "tomato_liu" / split / label.replace("/", "__") / f"{n:05d}.jpg")
                    c[(split, label)] += 1
                    n += 1
    return c


def whole(src: Path, out: Path, name: str, mapping, rng: random.Random, part_col: str | None = None) -> Counter:
    c: Counter = Counter()
    n = 0
    pf = pq.ParquetFile(next(src.glob("*.parquet")))
    labels = class_names(pf, "label")
    parts = class_names(pf, part_col) if part_col else []
    cols = ["image", "label"] + ([part_col] if part_col else [])
    for batch in pf.iter_batches(batch_size=16, columns=cols):
        rows = zip(*(batch.column(k).to_pylist() for k in cols))
        for row in rows:
            key = (labels[row[1]], parts[row[2]]) if part_col else labels[row[1]]
            label = mapping.get(key)
            if not label:
                continue
            split = "test" if rng.random() < 0.2 else "train"
            _save(_open(row[0]), out / name / split / label.replace("/", "__") / f"{n:05d}.jpg")
            c[(split, label)] += 1
            n += 1
    return c


FRESH_FRUIT = {"apple": "apple", "grape": "grape", "orange": "citrus", "strawberry": "strawberry",
               "pomegranate": "pomegranate", "banana": "banana", "guava": "guava", "jujube": "jujube"}


def tomato_ripe(src: Path, out: Path, rng: random.Random) -> Counter:
    """160x160 crops: raw / half_ripe / ripe = healthy fruit, rotten = rotten fruit. Official train/test split."""
    import zipfile
    c: Counter = Counter()
    z = zipfile.ZipFile(src / "crops.zip")
    groups: dict[tuple, list] = {}
    for i in z.infolist():
        parts = i.filename.split("/")
        if i.is_dir() or "cls_tomato" not in parts:
            continue
        k = parts.index("cls_tomato")
        if len(parts) < k + 4:
            continue
        split, cls = parts[k + 1], parts[k + 2]
        if split not in ("train", "test"):
            continue
        label = "tomato/fruit_rotten" if cls == "rotten" else "tomato/fruit_healthy"
        groups.setdefault((split, label, cls), []).append(i)
    # healthy = 3 ripeness folders, so 150 each; rotten train crops include flipped copies
    limits = {"train": {"tomato/fruit_healthy": 150, "tomato/fruit_rotten": 400},
              "test": {"tomato/fruit_healthy": 60, "tomato/fruit_rotten": 200}}
    n = 0
    for (split, label, cls), files in sorted(groups.items()):
        rng.shuffle(files)
        for i in files[:limits[split][label]]:
            img = Image.open(io.BytesIO(z.read(i))).convert("RGB")
            _save(img, out / "tomato_ripe" / split / label.replace("/", "__") / f"{n:05d}.jpg")
            c[(split, label)] += 1
            n += 1
    return c


def fresh_rotten(src: Path, out: Path, rng: random.Random, per_class: int = 160) -> Counter:
    c: Counter = Counter()
    seen: Counter = Counter()
    n = 0
    for f in sorted(src.glob("*.parquet")):
        pf = pq.ParquetFile(f)
        names = class_names(pf, "label")
        for batch in pf.iter_batches(batch_size=16, columns=["image", "label", "fruit_type"]):
            cols = [batch.column(k).to_pylist() for k in ("image", "label", "fruit_type")]
            for img, lab, fruit in zip(*cols):
                crop = FRESH_FRUIT.get(fruit)
                if not crop:
                    continue
                label = f"{crop}/fruit_healthy" if names[lab] == "fresh" else f"{crop}/fruit_rotten"
                if seen[label] >= per_class:
                    continue
                seen[label] += 1
                split = "test" if rng.random() < 0.2 else "train"
                _save(_open(img), out / "fresh_rotten" / split / label.replace("/", "__") / f"{n:05d}.jpg")
                c[(split, label)] += 1
                n += 1
    return c


def diamos(src: Path, out: Path, rng: random.Random) -> Counter:
    folders = {"fruits": "pear/fruit_healthy", "leaves/healthy": "pear/healthy", "leaves/spot": "pear/leaf_spot",
               "leaves/curl": "pear/leaf_curl", "leaves/slug": "pear/slug_damage"}
    c: Counter = Counter()
    n = 0
    for sub, label in folders.items():
        for f in sorted((src / "Pear" / sub).glob("*.jpg")):
            if f.name.startswith("._"):
                continue
            split = "test" if rng.random() < 0.2 else "train"
            _save(Image.open(f).convert("RGB"), out / "diamos" / split / label.replace("/", "__") / f"{n:05d}.jpg")
            c[(split, label)] += 1
            n += 1
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--only", nargs="*", help="prepare only these datasets")
    args = ap.parse_args()
    data = Path(args.data)
    out = data / "hf_extracted"
    jobs = {
        "tomato_liu": lambda r: tomato(data / "hf" / "tomato_liu", out, r),
        "citrus_fl": lambda r: whole(data / "hf" / "citrus_fl", out, "citrus_fl", CITRUS, r, "plant_part"),
        "veg_leaf": lambda r: whole(data / "hf" / "veg_leaf", out, "veg_leaf", VEG, r),
        "tomato_ripe": lambda r: tomato_ripe(data / "hf" / "tomato_ripe", out, r),
        "fresh_rotten": lambda r: fresh_rotten(data / "hf" / "fresh_rotten", out, r),
        "diamos": lambda r: diamos(data / "diamos", out, r),
    }
    counts = Counter()
    for name, job in jobs.items():
        if args.only and name not in args.only:
            continue
        counts += job(random.Random(11) if name in ("tomato_liu", "citrus_fl", "veg_leaf") else random.Random(name))
    for (split, label), n in sorted(counts.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"{label:<32} {split:<5} {n}")
    print("total", sum(counts.values()))


if __name__ == "__main__":
    sys.exit(main())
