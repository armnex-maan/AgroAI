import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml import deterrence
from app.models import Device
from app.schemas.common import iso_utc
from app.services import deterrent_service as svc

router = APIRouter()


class Window(BaseModel):
    start: str
    end: str


class Program(BaseModel):
    target: str = "sparrows"
    sound_type: str = "mix"
    recording_id: str | None = None
    f_lo: float = 2200
    f_hi: float = 3200
    windows: list[Window] = Field(default_factory=lambda: [Window(start="05:30", end="08:30"),
                                                           Window(start="17:30", end="19:30")])
    plays_per_hour: int = 4
    clip_seconds: float = 4
    random_intervals: bool = True
    trigger_on_detection: bool = True


class DeviceIn(BaseModel):
    name: str = "Dissuasore campo"
    zone_id: str | None = None
    farm_id: str | None = None
    program: Program


def _out(d: Device) -> dict:
    cfg = d.config or {}
    return {"id": d.id, "name": d.name, "zone_id": d.zone_id, "status": d.status,
            "last_seen": iso_utc(d.last_seen) if d.last_seen else None,
            "program": cfg.get("program"), "log": cfg.get("log", [])[:30],
            "physical_enabled": False}


def _get(db: Session, device_id: str) -> Device:
    d = db.get(Device, device_id)
    if d is None or d.hardware_type != svc.HW:
        raise HTTPException(404, "Dissuasore non trovato.")
    return d


@router.get("/deterrent/guide")
def guide():
    return {"profiles": deterrence.PROFILES, "methods": deterrence.METHODS, "legal": deterrence.LEGAL,
            "sound_types": deterrence.SOUND_TYPES, "xeno_canto": deterrence.SRC["xeno_canto"]["url"],
            "library": deterrence.library()}


@router.get("/deterrent/library/{sound_id}.ogg")
def library_file(sound_id: str):
    e = next((e for e in deterrence.library() if e["id"] == sound_id), None)
    if e is None:
        raise HTTPException(404, "Suono non trovato.")
    return FileResponse(deterrence.LIBRARY_DIR / e["file"], media_type="audio/ogg")


@router.post("/deterrent/preview")
def preview(prog: Program, seed: int | None = None, db: Session = Depends(get_db)):
    try:
        wav, info = svc.preview_wav(db, prog.model_dump(), seed)
    except svc.DeterrentError as e:
        raise HTTPException(400, str(e))
    # which clip was chosen, for the player label (URL-encoded JSON keeps the header ASCII)
    return Response(wav, media_type="audio/wav", headers={"X-Sound": quote(json.dumps(info, ensure_ascii=False)),
                                                          "Access-Control-Expose-Headers": "X-Sound"})


@router.get("/deterrent/devices")
def devices(db: Session = Depends(get_db)):
    return [_out(d) for d in svc.list_devices(db)]


@router.post("/deterrent/devices", status_code=201)
def create(body: DeviceIn, db: Session = Depends(get_db)):
    try:
        return _out(svc.create_device(db, body.name, body.zone_id, body.farm_id, body.program.model_dump()))
    except svc.DeterrentError as e:
        raise HTTPException(400, str(e))


@router.put("/deterrent/devices/{device_id}/program")
def update(device_id: str, prog: Program, db: Session = Depends(get_db)):
    try:
        return _out(svc.update_program(db, _get(db, device_id), prog.model_dump()))
    except svc.DeterrentError as e:
        raise HTTPException(400, str(e))


@router.post("/deterrent/devices/{device_id}/test")
def test(device_id: str, db: Session = Depends(get_db)):
    d = _get(db, device_id)
    svc.manual_test(db, d)
    return _out(d)


@router.get("/deterrent/devices/{device_id}/plan")
def plan(device_id: str, db: Session = Depends(get_db)):
    return {"times": svc.plan_day(_get(db, device_id))}


@router.delete("/deterrent/devices/{device_id}", status_code=204)
def delete(device_id: str, db: Session = Depends(get_db)):
    d = _get(db, device_id)
    db.delete(d)
    db.commit()
