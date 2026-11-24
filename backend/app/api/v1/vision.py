from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml.vision import color, differential, natural, plant_model
from app.ml.vision.causes import CAUSES
from app.models import ImageAnalysis
from app.schemas.common import iso_utc
from app.services import vision_service

router = APIRouter()
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _out(r: ImageAnalysis, db: Session | None = None) -> dict:
    out = {"id": r.id, "zone_id": r.zone_id, "ts": iso_utc(r.ts), "model": r.model,
           "confidence": r.confidence, "source": r.source, "findings": r.findings}
    if db is not None:
        out["verifications"] = [{"verdict": v.verdict, "actual_cause": (v.extra or {}).get("actual_cause"),
                                 "notes": v.notes, "created_at": iso_utc(v.created_at)}
                                for v in vision_service.verifications(db, r.id)]
    return out


@router.post("/vision/analyze", status_code=201)
async def analyze(
    file: UploadFile = File(...),
    zone_id: str | None = Form(None),
    crop: str | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "La foto è troppo grande (massimo 15 MB).")
    try:
        row = await vision_service.analyze(db, content, zone_id or None, (crop or "").strip() or None, notes)
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(400, "Il file non è una foto leggibile. Usa una foto JPG o PNG.")
    return _out(row, db)


@router.get("/vision/analyses")
def list_analyses(zone_id: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    return [_out(r) for r in vision_service.list_analyses(db, zone_id, limit)]


@router.get("/vision/analyses/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    r = db.get(ImageAnalysis, analysis_id)
    if r is None:
        raise HTTPException(404, "not found")
    return _out(r, db)


@router.delete("/vision/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, db: Session = Depends(get_db)):
    r = db.get(ImageAnalysis, analysis_id)
    if r is None:
        raise HTTPException(404, "not found")
    Path(r.path).unlink(missing_ok=True)
    db.delete(r)
    db.commit()


@router.get("/vision/analyses/{analysis_id}/image")
def image(analysis_id: str, db: Session = Depends(get_db)):
    r = db.get(ImageAnalysis, analysis_id)
    if r is None or not Path(r.path).exists():
        raise HTTPException(404, "not found")
    return Response(Path(r.path).read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@router.get("/vision/analyses/{analysis_id}/overlay.png")
def overlay(analysis_id: str, db: Session = Depends(get_db)):
    r = db.get(ImageAnalysis, analysis_id)
    if r is None or not Path(r.path).exists():
        raise HTTPException(404, "not found")
    png = color.overlay_png(color.load(Path(r.path).read_bytes()))
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=86400"})


class VerifyIn(BaseModel):
    verdict: Literal["confirmed", "partly", "wrong"]
    actual_cause: str | None = None
    notes: str | None = None


@router.post("/vision/analyses/{analysis_id}/verify", status_code=201)
def verify(analysis_id: str, payload: VerifyIn, db: Session = Depends(get_db)):
    try:
        vision_service.verify(db, analysis_id, payload.verdict, payload.actual_cause, payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _out(db.get(ImageAnalysis, analysis_id), db)


class AnswersIn(BaseModel):
    answers: dict[str, str]


@router.post("/vision/analyses/{analysis_id}/answers")
def answer(analysis_id: str, payload: AnswersIn, db: Session = Depends(get_db)):
    """Answers to the follow-up questions: the diagnosis is recalculated with them."""
    try:
        return _out(vision_service.answer(db, analysis_id, payload.answers), db)
    except ValueError:
        raise HTTPException(404, "not found")


@router.post("/vision/analyses/{analysis_id}/reanalyze")
async def reanalyze(analysis_id: str, db: Session = Depends(get_db)):
    """Analyse the same photo again with the current model and diagnostic engine."""
    try:
        return _out(await vision_service.reanalyze(db, analysis_id), db)
    except ValueError:
        raise HTTPException(404, "not found")


@router.get("/vision/model")
def model_info():
    """Image models trained on public datasets: versions, which one is active, accuracy on real photos."""
    return {"active": plant_model.active_version(), "backbone_ready": plant_model.available(),
            "versions": plant_model.versions()}


class ActivateIn(BaseModel):
    version: str | None


@router.post("/vision/model/activate")
def model_activate(payload: ActivateIn):
    try:
        plant_model.set_active(payload.version)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return model_info()


@router.get("/vision/questions")
def questions():
    return differential.QUESTIONS


@router.get("/vision/causes")
def causes():
    return [{"id": k, "name": v["name"], "category": v["category"]} for k, v in CAUSES.items()]


@router.get("/vision/remedies")
def remedies():
    """Catalogue of natural and biological remedies, each linked to the problems it addresses."""
    return {"remedies": natural.catalog(),
            "causes": {k: v["name"] for k, v in CAUSES.items()},
            "by_cause": natural.BY_CAUSE}
