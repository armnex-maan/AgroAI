"""Plant-health photo analysis: colour measurement + vision model + vetted tips + sensor cross-check."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Device, ImageAnalysis, Sensor, Verification, Zone
from app.ml.agronomy import soil_water
from app.ml.vision import color, differential, natural, plant_model, vlm
from app.ml.vision.causes import CAUSES, URGENCY_ORDER, colour_candidates
from app.services.llm_service import LLMUnavailable
from app.services.sensor_service import SensorService

CONTEXT_TYPES = ("soil_moisture", "soil_ph", "air_temperature", "air_humidity")
DISCLAIMER = ("Prima valutazione da una sola foto, non una diagnosi certa. Sintomi simili possono avere cause "
              "diverse: segui i passi in «Come esserne sicuri» o chiedi al Servizio Fitosanitario della tua Regione.")
TIER_LABEL = {"probable": "Causa probabile", "possible": "Causa possibile", "unlikely": "Causa poco probabile"}


def images_dir() -> Path:
    p = settings.media_path / "images"
    p.mkdir(parents=True, exist_ok=True)
    return p


def field_context(db: Session, zone_id: str | None) -> dict:
    rows = SensorService(db).latest_per_device()
    if zone_id:
        rows = [r for r in rows if r["zone_id"] == zone_id] or rows
    rows.sort(key=lambda r: r["source"] != "device")  # real sensors first
    ctx: dict = {t: None for t in CONTEXT_TYPES}
    sources: dict = {}
    devices: dict = {}
    units: dict = {}
    for r in rows:
        for t in CONTEXT_TYPES:
            if ctx[t] is None and t in r["values"]:
                ctx[t] = r["values"][t]["value"]
                units[t] = r["values"][t].get("unit")
                sources[t] = r["source"]
                devices[t] = r["device_id"]
    ctx["sources"] = sources
    ctx["devices"] = devices
    ctx["units"] = units
    return ctx


def soil_reading(db: Session, ctx: dict, zone_id: str | None, crop: str | None) -> dict | None:
    """Soil moisture interpreted with the soil texture of the field and the sensor's calibration."""
    if ctx.get("soil_moisture") is None:
        return None
    dev_id = (ctx.get("devices") or {}).get("soil_moisture")
    sensor = None
    if dev_id:
        sensor = db.query(Sensor).filter(Sensor.device_id == dev_id, Sensor.type == "soil_moisture").first()
    soil_type = None
    zid = zone_id or (db.get(Device, dev_id).zone_id if dev_id and db.get(Device, dev_id) else None)
    if zid and (z := db.get(Zone, zid)) is not None and z.field is not None:
        soil_type = z.field.soil_type
    return soil_water.interpret(ctx["soil_moisture"], (ctx.get("units") or {}).get("soil_moisture") or "%",
                                (ctx.get("sources") or {}).get("soil_moisture"), soil_type, crop,
                                sensor.calibration if sensor else None)


def model_view(jpeg: bytes, crop: str | None, ai: dict | None) -> dict | None:
    """Run the trained image model (if one is active) with the crop and organs seen by the vision model."""
    organs = ((ai or {}).get("observations") or {}).get("organs") or []
    return plant_model.predict(jpeg, crop or (ai or {}).get("plant_guess"), organs)


def build_causes(ai: dict | None, measured: dict, soil: dict | None, ctx: dict, answers: dict | None,
                 model: dict | None = None) -> dict:
    """Run the differential diagnosis and attach the vetted advice for each cause."""
    if ai and ai.get("is_plant_image") is False:
        return {"causes": [], "questions": [], "observations": {}, "organs": [], "cap": 0}
    fallback = [] if (ai and ai.get("causes")) else colour_candidates(measured)
    dx = differential.diagnose(ai, fallback, soil, ctx, answers, model)
    causes = []
    for r in dx["causes"]:
        kb = CAUSES[r["id"]]
        shown = r["tier"] != "unlikely"  # remedies only for causes that fit the symptoms
        causes.append({
            "id": r["id"], "name": kb["name"], "category": kb["category"], "urgency": kb["urgency"],
            "tier": r["tier"], "tier_label": TIER_LABEL[r["tier"]], "probability": r["probability"],
            "likelihood": differential.TIER_TO_LIKELIHOOD[r["tier"]],
            "why": r["model_view"] or "", "evidence": r["evidence"], "signs": kb["signs"],
            "sensor_checks": [{"effect": e["effect"], "text": e["text"]} for e in r["evidence"]
                              if e["origin"] == "sensore" and e["effect"] != "neutral"],
            "fix": kb["fix"] if shown else [], "prevent": kb["prevent"] if shown else [],
            "verify": kb["verify"], "sources": kb["sources"],
            "natural": natural.for_cause(r["id"]) if shown else [],
        })
    order = {"probable": 0, "possible": 1, "unlikely": 2}
    causes.sort(key=lambda c: (order[c["tier"]], -c["probability"], URGENCY_ORDER[c["urgency"]]))
    return {**dx, "causes": causes}


async def analyze(db: Session, content: bytes, zone_id: str | None, crop: str | None,
                  notes: str | None, source: str = "manual") -> ImageAnalysis:
    img = color.load(content)
    jpeg = color.to_jpeg(img)
    measured = color.analyze(img)
    ctx = field_context(db, zone_id)

    ai, ai_error = None, None
    try:
        ai = await vlm.assess(color.to_jpeg(img, side=768, quality=80), crop, measured, ctx)
    except LLMUnavailable as exc:
        ai_error = str(exc)

    soil = soil_reading(db, ctx, zone_id, crop)
    model = model_view(jpeg, crop, ai)
    dx = build_causes(ai, measured, soil, ctx, None, model)
    causes = dx["causes"]
    overall = (ai or {}).get("overall") or {"looks_healthy": "looks_healthy",
                                             "mild_discolouration": "mild_symptoms",
                                             "marked_discolouration": "marked_symptoms"}.get(measured["pattern"], "unclear")
    if ai and ai.get("is_plant_image") is False:
        overall = "not_a_plant"

    rec_id = str(uuid.uuid4())
    path = images_dir() / f"{rec_id}.jpg"
    path.write_bytes(jpeg)
    findings = {
        "crop": crop, "notes": notes, "overall": overall,
        "color": measured,
        "ai": ai, "ai_error": ai_error,
        "ai_model": settings.nvidia_model if ai else None,
        "causes": causes,
        "questions": dx["questions"], "answers": {}, "observations": dx["observations"], "organs": dx["organs"],
        "certainty_cap": dx["cap"], "engine": "differential-v1",
        "context": ctx, "soil": soil, "plant_model": model,
        "disclaimer": DISCLAIMER,
    }
    row = ImageAnalysis(
        id=rec_id, zone_id=zone_id, path=str(path), ts=datetime.now(timezone.utc),
        model=f"color-v1+{settings.nvidia_model}" if ai else "color-v1",
        findings=findings,
        confidence=causes[0]["probability"] if causes else 0.0,
        source=source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def answer(db: Session, analysis_id: str, answers: dict[str, str]) -> ImageAnalysis:
    """Farmer answers to the follow-up questions: re-run the differential without calling the model again."""
    row = db.get(ImageAnalysis, analysis_id)
    if row is None:
        raise ValueError("analysis not found")
    f = dict(row.findings)
    valid = {q: v for q, v in answers.items()
             if q in differential.QUESTIONS and v in {o for o, _ in differential.QUESTIONS[q]["options"]}}
    merged = {**(f.get("answers") or {}), **valid}
    ctx = f.get("context") or {}
    soil = f.get("soil") or soil_reading(db, ctx, row.zone_id, f.get("crop"))
    dx = build_causes(f.get("ai"), f.get("color") or {}, soil, ctx, merged, f.get("plant_model"))
    f.update(causes=dx["causes"], questions=dx["questions"], answers=merged, observations=dx["observations"],
             organs=dx["organs"], certainty_cap=dx["cap"], soil=soil, engine="differential-v1")
    row.findings = f
    row.confidence = dx["causes"][0]["probability"] if dx["causes"] else 0.0
    db.commit()
    db.refresh(row)
    return row


async def reanalyze(db: Session, analysis_id: str) -> ImageAnalysis:
    """Run an older photo again through the current model and diagnostic engine (keeps the answers)."""
    row = db.get(ImageAnalysis, analysis_id)
    if row is None or not Path(row.path).exists():
        raise ValueError("analysis not found")
    f = dict(row.findings)
    img = color.load(Path(row.path).read_bytes())
    ctx = field_context(db, row.zone_id)
    ai, ai_error = None, None
    try:
        ai = await vlm.assess(color.to_jpeg(img, side=768, quality=80), f.get("crop"), f.get("color") or {}, ctx)
    except LLMUnavailable as exc:
        ai_error = str(exc)
        if f.get("ai"):  # never replace a good earlier answer with a worse one when the AI is unreachable
            ai = f["ai"]
            ai_error = f"AI non raggiungibile ({exc}): tenuta l'analisi visiva precedente."
    soil = soil_reading(db, ctx, row.zone_id, f.get("crop"))
    model = model_view(Path(row.path).read_bytes(), f.get("crop"), ai)
    dx = build_causes(ai, f.get("color") or {}, soil, ctx, f.get("answers") or {}, model)
    f.update(ai=ai, ai_error=ai_error, ai_model=settings.nvidia_model if ai else None, context=ctx, soil=soil,
             plant_model=model,
             causes=dx["causes"], questions=dx["questions"], observations=dx["observations"], organs=dx["organs"],
             certainty_cap=dx["cap"], engine="differential-v1", disclaimer=DISCLAIMER)
    if ai and ai.get("overall"):
        f["overall"] = ai["overall"]
    row.findings = f
    row.confidence = dx["causes"][0]["probability"] if dx["causes"] else 0.0
    db.commit()
    db.refresh(row)
    return row


def list_analyses(db: Session, zone_id: str | None = None, limit: int = 100) -> list[ImageAnalysis]:
    q = db.query(ImageAnalysis).order_by(desc(ImageAnalysis.ts))
    if zone_id:
        q = q.filter(ImageAnalysis.zone_id == zone_id)
    return q.limit(limit).all()


def verify(db: Session, analysis_id: str, verdict: str, actual_cause: str | None, notes: str | None) -> Verification:
    if db.get(ImageAnalysis, analysis_id) is None:
        raise ValueError("analysis not found")
    if actual_cause and actual_cause not in CAUSES:
        raise ValueError("unknown cause id")
    v = Verification(target_type="image_analysis", target_id=analysis_id, verdict=verdict, notes=notes,
                     extra={"actual_cause": actual_cause}, created_at=datetime.now(timezone.utc))
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def verifications(db: Session, analysis_id: str) -> list[Verification]:
    return (db.query(Verification).filter_by(target_type="image_analysis", target_id=analysis_id)
            .order_by(desc(Verification.created_at)).all())
