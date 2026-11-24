"""Colour-based plant tissue analysis — deterministic, runs offline.

Classifies pixels as green (healthy-looking), yellow (chlorosis) or brown (necrosis)
in HSV space. Brown is only counted next to plant tissue, because bare soil has
the same colour. Lighting and white balance change colours: this is a measurement
of the photo, not a diagnosis.
"""
from __future__ import annotations

import io

import numpy as np
from matplotlib.colors import rgb_to_hsv
from PIL import Image, ImageOps
from scipy import ndimage

ANALYSIS_SIDE = 512
STORE_SIDE = 1600
MAX_PIXELS = 50_000_000


def load(content: bytes) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    with Image.open(io.BytesIO(content)) as probe:
        probe.verify()  # rejects truncated / non-image files
    img = Image.open(io.BytesIO(content))
    img = ImageOps.exif_transpose(img)  # phone photos carry rotation in EXIF
    return img.convert("RGB")


def to_jpeg(img: Image.Image, side: int = STORE_SIDE, quality: int = 88) -> bytes:
    """Re-encode (drops EXIF, including GPS) and cap the size."""
    im = img.copy()
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _masks(img: Image.Image):
    im = img.copy()
    im.thumbnail((ANALYSIS_SIDE, ANALYSIS_SIDE))
    rgb = np.asarray(im, dtype=np.float32) / 255.0
    hsv = rgb_to_hsv(rgb)
    hue, sat, val = hsv[..., 0] * 360.0, hsv[..., 1], hsv[..., 2]

    green = (hue >= 70) & (hue <= 170) & (sat > 0.18) & (val > 0.15)
    yellow = (hue >= 40) & (hue < 70) & (sat > 0.25) & (val > 0.35)
    brown_colour = (hue >= 5) & (hue < 40) & (sat > 0.2) & (val > 0.1) & (val < 0.7)
    near_plant = ndimage.binary_dilation(green | yellow, iterations=12)
    brown = brown_colour & near_plant
    # Pale grey-white film lying ON the leaf (powdery mildew, dust, spray residue, glare):
    # low saturation, not pure-white background, enclosed by leaf tissue.
    leaf = ndimage.binary_fill_holes(ndimage.binary_closing(green | yellow | brown, iterations=4))
    whitish = leaf & ~(green | yellow | brown) & (sat < 0.22) & (val > 0.5) & (val < 0.93)
    whitish |= green & (sat < 0.3) & (val > 0.7)  # green tissue strongly washed with white
    # edge pixels blend leaf and background colours: ignore a thin border around leaf and holes
    interior = ndimage.binary_erosion(green | yellow | brown, iterations=3)
    whitish &= ndimage.binary_dilation(interior, iterations=1) & ndimage.binary_erosion(leaf, iterations=3)
    return rgb, green, yellow, brown, whitish, leaf


def analyze(img: Image.Image) -> dict:
    rgb, green, yellow, brown, whitish, leaf = _masks(img)
    plant = green | yellow | brown
    total = plant.size
    n_plant = int(plant.sum())
    gray = rgb.mean(axis=2)
    sharpness = float(ndimage.laplace(gray).var())
    # exposure judged on the plant, not on a white or black background
    brightness = float(gray[plant].mean()) if n_plant else float(gray.mean())

    warnings = []
    if n_plant / total < 0.08:
        warnings.append("La pianta occupa meno dell'8% della foto: avvicinati alle foglie.")
    if brightness < 0.2:
        warnings.append("La foto è molto scura: i colori non sono affidabili.")
    if brightness > 0.88:
        warnings.append("La foto è troppo chiara (sovraesposta): i colori non sono affidabili.")
    if sharpness < 0.0008:
        warnings.append("La foto sembra mossa o sfocata: le macchie piccole potrebbero sfuggire.")

    if n_plant == 0:
        return {"plant_coverage": 0.0, "healthy_green": 0.0, "chlorotic_yellow": 0.0, "necrotic_brown": 0.0,
                "whitish_coating": 0.0, "symptom_fraction": 0.0, "pattern": "no_plant_detected", "excess_green_index": None,
                "brightness": round(brightness, 3), "sharpness": round(sharpness, 5), "warnings": warnings,
                "method": "Analisi dei colori (v1)"}

    g, y, b = (int(m.sum()) / n_plant for m in (green, yellow, brown))
    r_, g_, b_ = (rgb[..., i][plant] for i in range(3))
    exg = float(np.mean(2 * g_ - r_ - b_))
    white = float(whitish.sum()) / max(1, int(leaf.sum()))
    symptoms = y + b
    pattern = ("looks_healthy" if symptoms < 0.08 else
               "mild_discolouration" if symptoms < 0.25 else "marked_discolouration")
    return {
        "plant_coverage": round(n_plant / total, 3),
        "healthy_green": round(g, 3),
        "chlorotic_yellow": round(y, 3),
        "necrotic_brown": round(b, 3),
        "whitish_coating": round(white, 3),
        "symptom_fraction": round(symptoms, 3),
        "pattern": pattern,
        "excess_green_index": round(exg, 3),
        "brightness": round(brightness, 3),
        "sharpness": round(sharpness, 5),
        "warnings": warnings,
        "method": "Analisi dei colori (v1): il marrone è contato solo vicino al tessuto verde, per non confonderlo con la terra",
    }


def overlay_png(img: Image.Image) -> bytes:
    rgb, green, yellow, brown, whitish, _leaf = _masks(img)
    out = rgb * 0.35
    out[green] = out[green] * 0.6 + np.array([0.2, 0.75, 0.4]) * 0.4
    out[yellow] = np.array([1.0, 0.85, 0.1])
    out[brown] = np.array([0.95, 0.3, 0.25])
    out[whitish] = np.array([0.35, 0.8, 1.0])
    buf = io.BytesIO()
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(buf, "PNG")
    return buf.getvalue()
