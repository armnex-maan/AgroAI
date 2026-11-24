import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.ml.agronomy.crops import CROPS, KB_SOURCES
from app.services import agronomy_service, llm_service

router = APIRouter()

TEXTURES = ["sand", "loamy sand", "sandy loam", "loam", "silt loam", "silt", "sandy clay loam",
            "clay loam", "silty clay loam", "sandy clay", "silty clay", "clay"]


class AssessIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    farm_id: str | None = None
    ph: float | None = Field(default=None, ge=3.0, le=10.0)
    texture: str | None = None


@router.post("/agronomy/assess")
async def assess(payload: AssessIn, db: Session = Depends(get_db)):
    if payload.texture and payload.texture not in TEXTURES:
        raise HTTPException(400, f"texture must be one of {TEXTURES}")
    try:
        return await agronomy_service.assess(db, payload.lat, payload.lon, payload.country_code,
                                             payload.farm_id, payload.ph, payload.texture)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Il servizio dei dati climatici non risponde. Controlla la connessione e riprova.")


@router.post("/agronomy/ai-advice")
async def ai_advice(payload: AssessIn, db: Session = Depends(get_db)):
    """LLM-written advice grounded on the deterministic assessment (recomputed from cache)."""
    if settings.ai_provider == "none":
        raise HTTPException(409, "L'intelligenza artificiale non è configurata.")
    assessment = await assess(payload, db)
    try:
        text = await llm_service.advise_site(assessment)
    except llm_service.LLMUnavailable:
        raise HTTPException(503, "L'intelligenza artificiale non risponde in questo momento. Riprova tra poco.")
    return {"advice": text, "provider": settings.ai_provider, "model": settings.ai_model,
            "grounded_on": "AGROAI site assessment (climate, soil, crop ranking, tips, legal status)"}


@router.get("/agronomy/crops")
def crops():
    return {"crops": [c.__dict__ for c in CROPS], "textures": TEXTURES, "sources": KB_SOURCES}
