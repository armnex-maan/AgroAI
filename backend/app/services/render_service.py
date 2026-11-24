"""Photoreal render of the Visual Planner with Blender Cycles.

The browser exports the scene as it is on screen (scene.glb + meta.json, see frontend planner/renderExport.ts); this
service queues the job and runs Blender headless with tools/blender/render_scene.py, one job at a time (it uses the
GPU). Progress comes from the script's "STAGE"/"PROGRESS" lines. The finished image gets a caption stating what it is
(an illustration of the plan: plant size factor, demonstrative landscape), so it is never mistaken for a photo.
"""
from __future__ import annotations

import json
import math
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
TOOLS = REPO / "tools" / "blender"
PUBLIC_PLANNER = REPO / "frontend" / "public" / "planner"
TREES = ("tree_small_02", "island_tree_01", "island_tree_02", "island_tree_03")
CROPS = ("lettuce", "cabbage", "tomato", "tomato_green", "eggplant", "eggplant_green")
KEEP_JOBS = 12
TIMEOUT_S = 20 * 60
# share of the progress bar at the start of each stage (the render itself fills the rest by samples)
STAGES = {"crops": 0.02, "import": 0.05, "instances": 0.12, "assets": 0.16, "grass": 0.3, "materials": 0.33,
          "light": 0.34, "camera": 0.35, "render": 0.38, "done": 0.98}
STAGE_LABEL = {"queued": "In coda", "crops": "Preparo i modelli delle colture", "import": "Importo la scena",
               "instances": "Piante e cespugli", "assets": "Alberi e colture in 3D", "grass": "Erba",
               "materials": "Materiali e foschia", "light": "Cielo, sole e orizzonte", "camera": "Inquadratura",
               "render": "Rendering con Cycles", "done": "Ultimi ritocchi", "finished": "Pronto", "error": "Errore"}


def blender_path() -> str | None:
    if settings.render_blender and Path(settings.render_blender).exists():
        return settings.render_blender
    found = shutil.which("blender")
    if found:
        return found
    for base in (Path("C:/Program Files/Blender Foundation"), Path("/Applications/Blender.app/Contents/MacOS")):
        if base.exists():
            exes = sorted(base.glob("*/blender.exe")) + sorted(base.glob("blender"))
            if exes:
                return str(exes[-1])
    return None


def assets_dir() -> Path:
    return Path(settings.render_assets) if settings.render_assets else Path.home() / "agroai-assets"


def status() -> dict:
    exe = blender_path()
    a = assets_dir()
    trees = [t for t in TREES if (a / "src" / t / f"{t}_1k.blend").exists()]
    out = {"available": bool(exe) and (TOOLS / "render_scene.py").exists(), "blender": exe, "assets_dir": str(a),
           "trees": len(trees), "trees_total": len(TREES),
           "note": None if len(trees) == len(TREES) else "Alberi fotoscansionati non trovati: il render usa alberi semplici."}
    if not exe:
        out["reason"] = "Blender non trovato: installalo o indica il percorso in RENDER_BLENDER."
    return out


@dataclass
class Job:
    id: str
    folder: Path
    label: dict
    state: str = "queued"          # queued | running | done | error
    stage: str = "queued"
    progress: float = 0.0
    error: str | None = None
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    log: list[str] = field(default_factory=list)

    def out(self) -> dict:
        return {"id": self.id, "state": self.state, "stage": self.stage, "stage_label": STAGE_LABEL.get(self.stage, self.stage),
                "progress": round(self.progress, 3), "error": self.error,
                "seconds": round((self.finished or time.time()) - (self.started or self.created), 1),
                "image": f"/api/v1/render/{self.id}/image" if self.state == "done" else None,
                "label": {k: v for k, v in self.label.items() if not k.startswith("_")}}


_jobs: dict[str, Job] = {}
_queue: "queue.Queue[Job]" = queue.Queue()
_lock = threading.Lock()
_worker: threading.Thread | None = None


def _root() -> Path:
    p = settings.media_path / "renders"
    p.mkdir(parents=True, exist_ok=True)
    return p


def submit(glb: bytes, meta: dict, label: dict) -> Job:
    global _worker
    jid = uuid.uuid4().hex[:12]
    folder = _root() / jid
    folder.mkdir(parents=True)
    (folder / "scene.glb").write_bytes(glb)
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    job = Job(jid, folder, label)
    with _lock:
        _jobs[jid] = job
        _cleanup()
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, name="agroai-render", daemon=True)
            _worker.start()
    _queue.put(job)
    return job


def get(jid: str) -> Job | None:
    return _jobs.get(jid)


def _cleanup() -> None:
    old = sorted(_jobs.values(), key=lambda j: j.created)[:-KEEP_JOBS]
    for j in old:
        if j.state in ("done", "error"):
            shutil.rmtree(j.folder, ignore_errors=True)
            _jobs.pop(j.id, None)


def _work() -> None:
    while True:
        job = _queue.get()
        job.state, job.started = "running", time.time()
        try:
            _run(job)
            job.state, job.stage, job.progress = "done", "finished", 1.0
        except Exception as e:  # noqa: BLE001 - reported to the user
            job.state, job.stage, job.error = "error", "error", str(e)[:400]
        job.finished = time.time()


def _blender(args: list[str], job: Job, env: dict | None = None) -> None:
    exe = blender_path()
    if not exe:
        raise RuntimeError("Blender non trovato.")
    proc = subprocess.Popen([exe, "--background", "--factory-startup", "--disable-autoexec", *args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, **(env or {})}, cwd=str(job.folder))
    deadline = time.time() + TIMEOUT_S
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        job.log = (job.log + [line])[-60:]
        if line.startswith("STAGE "):
            job.stage = line.split()[1]
            job.progress = max(job.progress, STAGES.get(job.stage, job.progress))
            if job.stage == "render":
                _tick_render(job)
        m = re.search(r"PROGRESS (\d+) (\d+)", line) or re.search(r"Sample (\d+)/(\d+)", line)
        if m and job.stage == "render":
            done, total = int(m.group(1)), max(1, int(m.group(2)))
            job.progress = max(job.progress, STAGES["render"] + (STAGES["done"] - STAGES["render"]) * done / total)
        if time.time() > deadline:
            proc.kill()
            raise RuntimeError("Render troppo lungo: interrotto dopo 20 minuti.")
    if proc.wait() != 0:
        tail = [l for l in job.log if "Error" in l or "Traceback" in l or "error" in l][-3:]
        raise RuntimeError("Blender si è fermato con un errore. " + " | ".join(tail))


def _tick_render(job: Job) -> None:
    """Indicative progress while Cycles renders (no per-sample log in background mode): eases toward 95 %."""
    t0 = time.time()
    expected = float(job.label.get("_expected_s", 75))

    def tick() -> None:
        while job.stage == "render" and job.state == "running":
            k = 1 - math.exp(-(time.time() - t0) / expected)
            job.progress = max(job.progress, STAGES["render"] + (STAGES["done"] - STAGES["render"]) * 0.97 * k)
            time.sleep(0.5)
    threading.Thread(target=tick, daemon=True).start()


def _ensure_crops(job: Job, meta: dict) -> None:
    need = {g["name"][5:] for g in meta.get("impostors", []) if str(g.get("name", "")).startswith("crop_")}
    missing = [c for c in need if c in CROPS and not (assets_dir() / "crops" / f"{c}.blend").exists()]
    if missing:
        job.stage = "crops"
        (assets_dir() / "crops").mkdir(parents=True, exist_ok=True)
        _blender(["--python", str(TOOLS / "make_crops.py"), "--", str(assets_dir() / "crops")], job, {"CROPS": ",".join(missing)})


def _run(job: Job) -> None:
    meta = json.loads((job.folder / "meta.json").read_text(encoding="utf-8"))
    w = int(meta.get("width", 1920))
    h = w / max(0.3, float(meta.get("camera", {}).get("aspect", 1.6)))
    job.label["_expected_s"] = 75 * (w * h / 2.28e6) * (int(meta.get("samples", 128)) / 128)   # RTX-class GPU, measured
    _ensure_crops(job, meta)
    _blender(["--python", str(TOOLS / "render_scene.py"), "--", str(job.folder), str(assets_dir()), str(PUBLIC_PLANNER)], job)
    img = job.folder / "render.png"
    if not img.exists():
        raise RuntimeError("Blender non ha prodotto l'immagine.")
    _finish(img, job.label)


def _font(size: int):
    from PIL import ImageFont
    try:
        import matplotlib
        return ImageFont.truetype(str(Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf" / "DejaVuSans.ttf"), size)
    except Exception:  # noqa: BLE001 - any font is fine
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def _finish(path: Path, label: dict) -> None:
    """Final grade (like the planner's: a little more colour and contrast than AgX gives) and a small caption in the
    bottom-left corner stating what the picture is, so it is never mistaken for a photo of the farm."""
    from PIL import Image, ImageDraw, ImageEnhance
    im = Image.open(path).convert("RGB")
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.2)).enhance(1.06)
    W, H = im.size
    parts = ["AgroAI · render illustrativo del piano (Blender Cycles)"]
    if label.get("farm"):
        parts.append(str(label["farm"])[:60])
    if label.get("year"):
        parts.append(f"anno {label['year']}")
    if label.get("exag") and float(label["exag"]) > 1:
        parts.append(f"piante ingrandite ×{label['exag']}")
    parts.append("paesaggio dimostrativo, non dati reali")
    text = " · ".join(parts)
    size = max(12, W // 120)
    font = _font(size)
    d = ImageDraw.Draw(im, "RGBA")
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=font)
    pad = size // 2
    box = (pad, H - (y1 - y0) - 3 * pad, pad + (x1 - x0) + 2 * pad, H - pad)
    d.rounded_rectangle(box, radius=pad, fill=(10, 19, 14, 170))
    d.text((box[0] + pad, box[1] + pad - y0), text, fill=(238, 245, 240, 255), font=font)
    im.save(path, optimize=True)
