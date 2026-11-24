from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.models import Farm, Field, Zone
from app.schemas.farm import FarmCreate, FarmOut, FieldCreate, FieldOut, ZoneCreate, ZoneOut

router = APIRouter()


@router.get("/farms", response_model=list[FarmOut])
def list_farms(db: Session = Depends(get_db)):
    return db.query(Farm).all()


@router.post("/farms", response_model=FarmOut, status_code=201)
def create_farm(payload: FarmCreate, db: Session = Depends(get_db)):
    f = Farm(**payload.model_dump(), created_at=datetime.now(timezone.utc))
    db.add(f); db.commit(); db.refresh(f)
    return f


@router.get("/fields", response_model=list[FieldOut])
def list_fields(farm_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Field)
    if farm_id:
        q = q.filter(Field.farm_id == farm_id)
    return q.all()


@router.post("/fields", response_model=FieldOut, status_code=201)
def create_field(payload: FieldCreate, db: Session = Depends(get_db)):
    if not db.get(Farm, payload.farm_id):
        raise HTTPException(404, "farm not found")
    f = Field(**payload.model_dump())
    db.add(f); db.commit(); db.refresh(f)
    return f


@router.get("/zones", response_model=list[ZoneOut])
def list_zones(field_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Zone)
    if field_id:
        q = q.filter(Zone.field_id == field_id)
    return q.all()


@router.post("/zones", response_model=ZoneOut, status_code=201)
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)):
    if not db.get(Field, payload.field_id):
        raise HTTPException(404, "field not found")
    z = Zone(**payload.model_dump())
    db.add(z); db.commit(); db.refresh(z)
    return z
