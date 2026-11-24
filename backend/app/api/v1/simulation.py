from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import SimulationScenario
from app.simulation.scenarios import list_scenarios, SCENARIOS

router = APIRouter()


class ScenarioOut(BaseModel):
    name: str
    title: str
    description: str
    active: bool


class ActivatePayload(BaseModel):
    name: str


@router.get("/simulation/scenarios", response_model=list[ScenarioOut])
def scenarios(db: Session = Depends(get_db)):
    rows = {s.name: s for s in db.query(SimulationScenario).all()}
    out = []
    for cfg in list_scenarios():
        s = rows.get(cfg["name"])
        out.append(ScenarioOut(name=cfg["name"], title=cfg["title"], description=cfg["description"],
                               active=bool(s and s.active)))
    return out


@router.post("/simulation/scenarios/activate", response_model=list[ScenarioOut])
def activate(payload: ActivatePayload, db: Session = Depends(get_db)):
    if payload.name not in SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    for s in db.query(SimulationScenario).all():
        s.active = (s.name == payload.name)
    if not db.query(SimulationScenario).filter_by(name=payload.name).first():
        db.add(SimulationScenario(name=payload.name, description=SCENARIOS[payload.name]["description"],
                                  config=SCENARIOS[payload.name], active=True))
    db.commit()
    return scenarios(db)
