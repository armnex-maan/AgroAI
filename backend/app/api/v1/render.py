"""Photoreal render of the Visual Planner (Blender Cycles), see app/services/render_service.py.

The render runs a local Blender process on the GPU: by default only requests from this computer are accepted
(the dev API listens on the LAN for the ESP32 boards). Set RENDER_ALLOW_REMOTE=true to allow other hosts.
"""
import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.services import render_service as svc

router = APIRouter()
MAX_GLB = 400 * 1024 * 1024
MAX_ITEMS = 2_000_000          # numbers in the instance / impostor lists


def _local_only(request: Request) -> None:
    host = request.client.host if request.client else ""
    if not settings.render_allow_remote and host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "Il render fotorealistico si avvia solo dal computer dove gira AgroAI.")


@router.get("/render/status")
def render_status():
    return svc.status()


@router.post("/render", status_code=202)
async def start_render(request: Request, scene: UploadFile = File(...), meta: UploadFile = File(...), label: str = Form("{}")):
    _local_only(request)
    glb = await scene.read()
    if len(glb) > MAX_GLB:
        raise HTTPException(413, "Scena troppo grande.")
    if glb[:4] != b"glTF":
        raise HTTPException(400, "La scena non è un file glTF binario.")
    try:
        m = json.loads((await meta.read()).decode("utf-8"))
        lab = json.loads(label or "{}")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Dati della scena non validi.")
    if not isinstance(m, dict) or not isinstance(m.get("camera"), dict) or len(m["camera"].get("matrix", [])) != 16:
        raise HTTPException(400, "Inquadratura mancante.")
    total = sum(len(g.get("items", [])) for g in m.get("impostors", [])) + sum(len(i.get("matrices", [])) for i in m.get("instances", []))
    if total > MAX_ITEMS:
        raise HTTPException(413, "Troppi oggetti nella scena: riduci la qualità grafica e riprova.")
    m["width"] = max(640, min(3840, int(m.get("width", 1920))))
    m["samples"] = max(16, min(1024, int(m.get("samples", 128))))
    lab = {k: lab.get(k) for k in ("farm", "year", "exag")} if isinstance(lab, dict) else {}
    st = svc.status()
    if not st["available"]:
        raise HTTPException(503, st.get("reason") or "Render non disponibile.")
    job = svc.submit(glb, m, lab)
    return job.out()


@router.get("/render/{job_id}")
def render_job(job_id: str):
    job = svc.get(job_id)
    if not job:
        raise HTTPException(404, "Render non trovato.")
    return job.out()


@router.get("/render/{job_id}/image")
def render_image(job_id: str):
    job = svc.get(job_id)
    if not job or job.state != "done":
        raise HTTPException(404, "Immagine non disponibile.")
    return FileResponse(job.folder / "render.png", media_type="image/png", filename=f"agroai-render-{job_id}.png")
