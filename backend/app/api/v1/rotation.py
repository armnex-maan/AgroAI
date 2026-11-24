"""Crop rotation: easy questions, field history, multi-year plan."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PField
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml.agronomy import rotation
from app.models import Crop, CropHistory, Field, ImageAnalysis, Zone

router = APIRouter()

# photo diagnoses that point to a soil-borne problem the rotation must take into account
CAUSE_TO_PROBLEM = {"bacterial_wilt": "wilt"}


def last_season_year(today: date | None = None) -> int:
    """The 'last season' is this year once summer crops are harvested (from August), otherwise last year."""
    d = today or date.today()
    return d.year if d.month >= 8 else d.year - 1


def _history(db: Session, field_id: str | None) -> list[CropHistory]:
    if not field_id:
        return []
    return db.query(CropHistory).filter(CropHistory.field_id == field_id).order_by(CropHistory.year.desc()).all()


def _out(h: CropHistory) -> dict:
    c = rotation.BY_KEY.get(h.crop)
    return {"id": h.id, "year": h.year, "crop": h.crop, "name": c.name if c else "Riposo / nessuna coltura",
            "family": c.family if c else None}


@router.get("/rotation/setup")
def setup(field_id: str | None = None, db: Session = Depends(get_db)):
    fields = db.query(Field).all()
    field = db.get(Field, field_id) if field_id else (fields[0] if fields else None)
    hist = _history(db, field.id if field else None)
    year = last_season_year()
    by_year = {h.year: h.crop for h in hist}
    prefill = {"last": by_year.get(year), "before": by_year.get(year - 1), "problems": [], "detected": []}
    if field and not prefill["last"]:
        zones = db.query(Zone).filter(Zone.field_id == field.id).all()
        crop = db.query(Crop).filter(Crop.zone_id.in_([z.id for z in zones])).first() if zones else None
        found = rotation.find(crop.species) if crop else None
        if found:
            prefill["last"] = found.key
            prefill["detected"].append(f"Coltura registrata nel campo: {found.name.split(' (')[0].lower()}")
    # soil-borne problems already seen in plant-health photos of the last 2 years
    since = datetime.now(timezone.utc) - timedelta(days=730)
    for a in db.query(ImageAnalysis).filter(ImageAnalysis.ts >= since.replace(tzinfo=None)).all():
        for c in (a.findings or {}).get("causes", []):
            pr = CAUSE_TO_PROBLEM.get(c.get("id"))
            if pr and c.get("tier") in ("probable", "possible") and pr not in prefill["problems"]:
                prefill["problems"].append(pr)
                prefill["detected"].append(f"Nelle foto delle piante: {c.get('name')} ({c.get('tier_label', '').lower()})")
    return {"questions": rotation.QUESTIONS, "crops": rotation.catalog(), "families": rotation.FAMILIES,
            "fields": [{"id": f.id, "name": f.name, "soil_type": f.soil_type} for f in fields],
            "field_id": field.id if field else None, "season_year": year,
            "history": [_out(h) for h in hist], "prefill": prefill}


class AdviseIn(BaseModel):
    field_id: str | None = None
    last: str | None = None
    before: str | None = None
    wanted: list[str] = PField(default_factory=list)
    problems: list[str] = PField(default_factory=list)
    soil: str | None = None
    manure: str | None = None
    cover: str | None = None
    save: bool = False


def _valid(k: str | None) -> str | None:
    return k if k in rotation.BY_KEY or k == rotation.REST else None


@router.post("/rotation/advise")
def advise(body: AdviseIn, db: Session = Depends(get_db)):
    year = last_season_year()
    last, before = _valid(body.last), _valid(body.before)
    history: list[str | None] = [last, before]
    # older seasons from the saved history make the advice more precise
    if body.field_id:
        by_year = {h.year: h.crop for h in _history(db, body.field_id)}
        history += [by_year.get(year - k) for k in range(2, 6)]
    history = [None if k == rotation.REST else k for k in history]
    problems = {p for p in body.problems if p in rotation.PROBLEMS}
    soil = body.soil if body.soil in rotation.SOIL_STATE else None
    out = rotation.advise(history, [w for w in body.wanted if w in rotation.BY_KEY], problems, soil,
                          body.manure, body.cover)
    if body.save and body.field_id:
        if db.get(Field, body.field_id) is None:
            raise HTTPException(404, "Campo non trovato.")
        for y, k in ((year, last), (year - 1, before)):
            if not k:
                continue
            row = db.query(CropHistory).filter_by(field_id=body.field_id, year=y).first()
            if row:
                row.crop = k
            else:
                db.add(CropHistory(field_id=body.field_id, year=y, crop=k))
        db.commit()
        out["saved"] = True
    out["season_year"] = year
    out["plan_years"] = [year + i + 1 for i in range(len(out["plan"]))]
    return out


class HistoryIn(BaseModel):
    field_id: str
    year: int
    crop: str


@router.get("/rotation/history")
def history(field_id: str, db: Session = Depends(get_db)):
    return [_out(h) for h in _history(db, field_id)]


@router.post("/rotation/history", status_code=201)
def add_history(body: HistoryIn, db: Session = Depends(get_db)):
    if db.get(Field, body.field_id) is None:
        raise HTTPException(404, "Campo non trovato.")
    if not _valid(body.crop):
        raise HTTPException(400, "Coltura non riconosciuta.")
    row = db.query(CropHistory).filter_by(field_id=body.field_id, year=body.year).first()
    if row:
        row.crop = body.crop
    else:
        row = CropHistory(field_id=body.field_id, year=body.year, crop=body.crop)
        db.add(row)
    db.commit()
    return _out(row)


@router.delete("/rotation/history/{row_id}", status_code=204)
def delete_history(row_id: str, db: Session = Depends(get_db)):
    row = db.get(CropHistory, row_id)
    if row is None:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
