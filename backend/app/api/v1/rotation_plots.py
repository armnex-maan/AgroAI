"""Crop rotation planner API: farm location, plots, visual layout, detailed history, multi-year plans.

Independent from the plant-health (vision) features: it only uses farms, fields and its own tables.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PField
from sqlalchemy.orm import Session

from app.api.v1.rotation import last_season_year
from app.core.database import get_db
from app.ml.agronomy import ecosystems, geo, irrigation, layout_generator, rotation, rotation_planner, rotation_rules
from app.models import (CropHistory, Farm, Field, PlannedCrop, PlannerRevision, PlotSection, RegulationSource,
                        RotationPlan, RotationRule)
from app.services import rotation_store as store

router = APIRouter()
HISTORY_YEARS = 6
STATUSES = ("crop", "rest", "cover", "unknown")
KINDS = ("bed", "path", "access", "water", "no_crop", "shade", "greenhouse")


def _farm(db: Session) -> Farm:
    farm = db.query(Farm).first()
    if farm is None:
        farm = Farm(name="La mia azienda", owner="", timezone="Europe/Rome")
        db.add(farm)
        db.commit()
        db.refresh(farm)
    return farm


def _plot(db: Session, plot_id: str) -> Field:
    f = db.get(Field, plot_id)
    if f is None:
        raise HTTPException(404, "Appezzamento non trovato.")
    return f


def _sections(db: Session, plot_id: str) -> list[PlotSection]:
    return db.query(PlotSection).filter(PlotSection.field_id == plot_id).order_by(PlotSection.sort).all()


def _sec_out(s: PlotSection, outline: list | None = None) -> dict:
    """area_m2 is the part of the section really inside the plot outline (irregular plots)."""
    out = {"id": s.id, "name": s.name, "kind": s.kind, "x": s.x, "y": s.y, "w": s.w, "h": s.h,
           "area_m2": round(geo.area_in(outline, s.x, s.y, s.w, s.h), 1),
           "row_spacing_m": s.row_spacing_m, "plant_spacing_m": s.plant_spacing_m, "row_dir": s.row_dir}
    if s.row_spacing_m:   # number of rows that fit across the section with the declared spacing
        across = s.h if s.row_dir == "x" else s.w if s.row_dir == "y" else min(s.w, s.h)
        out["rows"] = max(1, int(across // s.row_spacing_m))
    return out


def _hist_out(h: CropHistory) -> dict:
    c = rotation.BY_KEY.get(h.crop)
    return {"id": h.id, "year": h.year, "status": h.status or "crop", "crop": h.crop,
            "name": c.name.split(" (")[0] if c else {"rest": "Riposo", "cover": "Sovescio", "unknown": "Non ricordo"}.get(h.status or h.crop, h.crop),
            "family": c.family if c else None, "section_id": h.section_id, "area_m2": h.area_m2,
            "diseases": h.diseases, "treatments": h.treatments, "notes": h.notes}


def _plot_out(db: Session, f: Field) -> dict:
    hist = db.query(CropHistory).filter(CropHistory.field_id == f.id).order_by(CropHistory.year.desc()).all()
    area = f.area_m2 or ((f.width_m or 0) * (f.length_m or 0)) or ((f.area_ha or 0) * 10000) or None
    return {"id": f.id, "name": f.name, "area_m2": area, "shape": f.shape or "rectangle",
            "width_m": f.width_m, "length_m": f.length_m, "orientation_deg": f.orientation_deg or 0,
            "exposure": f.exposure, "outline": f.outline, "profile": store.read_profile(db, f), "soil_type": f.soil_type,
            "polygon": f.polygon if (f.polygon or {}).get("type") == "Polygon" else None,
            "sections": [_sec_out(s, f.outline) for s in _sections(db, f.id)],
            "history": [_hist_out(h) for h in hist],
            "plans": store.plans_out(db, f)}


# ---------------- regions and rules ----------------
@router.get("/rotation/regions")
def regions():
    return [{"key": k, "name": v, **{x: rotation_rules.coverage(k)[x] for x in ("level", "text")}}
            for k, v in rotation_rules.REGIONS.items()]


@router.get("/rotation/rules")
def rules(region: str | None = None):
    return {"coverage": rotation_rules.coverage(region), "rules": rotation_rules.all_rules(region)}


@router.get("/rotation/sources")
def sources(region: str | None = None, db: Session = Depends(get_db)):
    """Regulation sources and rules as stored in the database (synced from the reviewed rules)."""
    if not db.query(RegulationSource).count():
        store.sync_rules(db)
    q = db.query(RotationRule)
    if region:
        q = q.filter(RotationRule.region.in_([region, "*"]))
    docs = {d.id: {"id": d.id, "region": d.region, "year": d.year, "type": d.type, "title": d.title, "url": d.url}
            for d in db.query(RegulationSource)}
    return {"sources": list(docs.values()),
            "rules": [{"id": r.id, "source": docs.get(r.source_id), "region": r.region, "year": r.year, "level": r.level,
                       "crop": None if r.crop == "*" else r.crop, "interval_years": r.interval_years,
                       "repeat": r.repeat, "text": r.text} for r in q.order_by(RotationRule.region, RotationRule.crop)]}


@router.get("/rotation/calendar")
def calendar():
    return {"note": "Calendario indicativo per il pieno campo nel Centro-Nord: cambia con zona, clima e varietà.",
            "crops": {k: {"name": rotation.BY_KEY[k].name.split(" (")[0], **v}
                      for k, v in rotation_planner.CALENDAR.items() if k in rotation.BY_KEY}}


# ---------------- farm ----------------
class FarmIn(BaseModel):
    name: str | None = None
    region: str | None = None
    province: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    goals: dict | None = None


def _farm_out(farm: Farm) -> dict:
    return {"id": farm.id, "name": farm.name, "region": farm.region, "province": farm.province,
            "municipality": farm.municipality, "latitude": farm.latitude, "longitude": farm.longitude,
            "coverage": rotation_rules.coverage(farm.region)}


@router.get("/rotation/farm")
def get_farm(db: Session = Depends(get_db)):
    farm = _farm(db)
    plots = db.query(Field).filter(Field.farm_id == farm.id).all()
    from app.ml.agronomy import crop_heights
    return {**_farm_out(farm), "season_year": last_season_year(), "height_source": crop_heights.SOURCE,
            "plots": [_plot_out(db, f) for f in plots], "crops": rotation.catalog(), "families": rotation.FAMILIES}


@router.put("/rotation/farm")
def put_farm(body: FarmIn, db: Session = Depends(get_db)):
    farm = _farm(db)
    if body.region is not None and body.region not in rotation_rules.REGIONS and body.region != "":
        raise HTTPException(400, "Regione non valida.")
    for k in ("name", "region", "province", "municipality", "latitude", "longitude"):
        v = getattr(body, k)
        if v is not None:
            setattr(farm, k, v or None if k != "name" else v)
    db.commit()
    return _farm_out(farm)


# ---------------- plots ----------------
class PlotIn(BaseModel):
    name: str
    area_m2: float | None = None
    shape: str | None = "rectangle"
    width_m: float | None = None
    length_m: float | None = None
    orientation_deg: float | None = 0
    exposure: str | None = None
    profile: dict | None = None


def _apply_plot(db: Session, f: Field, body: PlotIn) -> None:
    f.name = body.name
    f.shape = body.shape if body.shape in ("rectangle", "square", "irregular") else "rectangle"
    f.width_m, f.length_m = body.width_m, body.length_m
    if f.shape == "square" and f.width_m:
        f.length_m = f.width_m
    if (not f.width_m or not f.length_m) and body.area_m2:
        side = body.area_m2 ** 0.5  # no dimensions given: draw an equivalent square, the farmer can reshape it
        f.width_m, f.length_m = f.width_m or round(side, 1), f.length_m or round(side, 1)
    f.area_m2 = body.area_m2 or (f.width_m or 0) * (f.length_m or 0) or None
    f.orientation_deg = body.orientation_deg or 0
    f.exposure = body.exposure
    if body.profile is not None:
        store.write_profile(db, f, body.profile)


@router.post("/rotation/plots", status_code=201)
def create_plot(body: PlotIn, db: Session = Depends(get_db)):
    farm = _farm(db)
    f = Field(farm_id=farm.id, name=body.name)
    db.add(f)
    db.flush()
    _apply_plot(db, f, body)
    db.commit()
    db.refresh(f)
    return _plot_out(db, f)


@router.put("/rotation/plots/{plot_id}")
def update_plot(plot_id: str, body: PlotIn, db: Session = Depends(get_db)):
    f = _plot(db, plot_id)
    _apply_plot(db, f, body)
    db.commit()
    return _plot_out(db, f)


@router.delete("/rotation/plots/{plot_id}", status_code=204)
def delete_plot(plot_id: str, db: Session = Depends(get_db)):
    f = _plot(db, plot_id)
    store.delete_plot_data(db, f.id)
    db.delete(f)
    db.commit()


class SectionIn(BaseModel):
    id: str | None = None
    name: str
    kind: str = "bed"
    x: float
    y: float
    w: float = PField(gt=0)
    h: float = PField(gt=0)
    row_spacing_m: float | None = PField(default=None, ge=0.1, le=20)
    plant_spacing_m: float | None = PField(default=None, ge=0.05, le=20)
    row_dir: str | None = PField(default=None, pattern="^[xy]$")


class LayoutIn(BaseModel):
    width_m: float = PField(gt=0)
    length_m: float = PField(gt=0)
    shape: str = "rectangle"
    outline: list[list[float]] | None = None
    orientation_deg: float = 0
    exposure: str | None = None
    sections: list[SectionIn] = PField(default_factory=list)


@router.put("/rotation/plots/{plot_id}/layout")
def save_layout(plot_id: str, body: LayoutIn, db: Session = Depends(get_db)):
    """Replace the plot drawing. Sections keep their id (and so their history) when sent back."""
    f = _plot(db, plot_id)
    _apply_layout(db, f, body)
    db.commit()
    return _plot_out(db, f)


def _apply_layout(db: Session, f: Field, body: LayoutIn) -> dict[str, str]:
    """Write a plot drawing (no commit). Returns {id sent by the client -> id saved}: new parts ("tmp-..." or ids
    that no longer exist) get a new id, so plans sent in the same save can follow them."""
    f.width_m, f.length_m, f.orientation_deg, f.exposure = body.width_m, body.length_m, body.orientation_deg, body.exposure
    f.shape = body.shape if body.shape in ("rectangle", "square", "irregular") else "rectangle"
    f.outline = body.outline if f.shape == "irregular" and body.outline and len(body.outline) >= 3 else None
    f.area_m2 = _polygon_area(f.outline) if f.outline else round(body.width_m * body.length_m, 1)
    poly = f.polygon or {}
    if poly.get("type") == "Polygon" and poly.get("origin") and poly.get("k"):  # plot traced on the map: follow the edit
        pts = f.outline or [[0, 0], [body.width_m, 0], [body.width_m, body.length_m], [0, body.length_m]]
        ring = geo.from_local(pts, poly["origin"], poly["k"])
        f.polygon = {**poly, "coordinates": [ring + [ring[0]]]}
        f.area_m2 = round(geo.area_m2(ring), 1)
        f.area_ha = round(f.area_m2 / 10000, 4)
    keep = {s.id for s in body.sections if s.id}
    for s in body.sections:
        if s.kind not in KINDS:
            raise HTTPException(400, f"Tipo di area non valido: {s.kind}")
    for old in _sections(db, f.id):
        if old.id not in keep:  # history and plans of a removed bed fall back to the whole plot
            for model in (CropHistory, PlannedCrop):
                db.query(model).filter(model.section_id == old.id).update({model.section_id: None})
            db.delete(old)
    ids: dict[str, str] = {}
    for i, s in enumerate(body.sections):
        x, y = max(0.0, min(s.x, body.width_m)), max(0.0, min(s.y, body.length_m))
        w, h = min(s.w, body.width_m - x), min(s.h, body.length_m - y)
        row = db.get(PlotSection, s.id) if s.id else None
        if row is None or row.field_id != f.id:
            row = PlotSection(field_id=f.id)
            db.add(row)
        row.name, row.kind, row.x, row.y, row.w, row.h, row.sort = s.name[:64], s.kind, x, y, max(w, 0.1), max(h, 0.1), i
        row.row_spacing_m, row.plant_spacing_m, row.row_dir = s.row_spacing_m, s.plant_spacing_m, s.row_dir
        db.flush()
        if s.id:
            ids[s.id] = row.id
    return ids


class BoundaryIn(BaseModel):
    ring: list[list[float]] = PField(min_length=3)   # [[lon, lat], ...] drawn on the satellite map


@router.put("/rotation/plots/{plot_id}/boundary")
def save_boundary(plot_id: str, body: BoundaryIn, db: Session = Depends(get_db)):
    """Plot traced on the map: real area from the coordinates, local metre outline for the field editor."""
    f = _plot(db, plot_id)
    try:
        ring = geo.clean_ring(body.ring)
        area = geo.area_m2(ring)
        loc = geo.to_local(ring)
    except (ValueError, IndexError, TypeError) as e:
        raise HTTPException(400, str(e) or "Confine non valido.")
    if area < 1:
        raise HTTPException(400, "Il terreno disegnato è troppo piccolo.")
    if area > 5_000_000:
        raise HTTPException(400, "Il terreno disegnato supera 500 ettari: dividilo in più appezzamenti.")
    f.polygon = {"type": "Polygon", "coordinates": [ring + [ring[0]]], "origin": loc["origin"], "k": loc["k"]}
    f.shape, f.outline, f.orientation_deg = "irregular", loc["outline"], 0
    f.width_m, f.length_m = loc["width_m"], loc["length_m"]
    f.area_m2, f.area_ha = round(area, 1), round(area / 10000, 4)
    for s in _sections(db, f.id):  # keep the drawn sections inside the new bounding box
        s.x, s.y = min(s.x, f.width_m - 0.1), min(s.y, f.length_m - 0.1)
        s.w, s.h = max(0.1, min(s.w, f.width_m - s.x)), max(0.1, min(s.h, f.length_m - s.y))
    farm = db.get(Farm, f.farm_id)
    if farm is not None and farm.latitude is None:
        farm.longitude, farm.latitude = round(loc["centroid"][0], 5), round(loc["centroid"][1], 5)
    db.commit()
    return {**_plot_out(db, f), "perimeter_m": round(geo.perimeter_m(ring), 1)}


class AutoLayoutIn(BaseModel):
    parts: int | None = PField(default=None, ge=1, le=12)
    path_m: float | None = PField(default=None, ge=0, le=12)


@router.post("/rotation/plots/{plot_id}/auto-layout")
def auto_layout(plot_id: str, body: AutoLayoutIn, db: Session = Depends(get_db)):
    """Split the plot into strips of equal real area (one per crop of the rotation), with paths in between.
    Replaces the drawn sections: records of removed beds fall back to the whole plot."""
    f = _plot(db, plot_id)
    if not f.width_m or not f.length_m:
        raise HTTPException(400, "Prima indica le misure o traccia il terreno sulla mappa.")
    area = f.area_m2 or f.width_m * f.length_m
    garden = area < 2000
    wanted = ((store.read_profile(db, f).get("goals") or {}).get("wanted") or {})
    parts = body.parts or min(8, max(3, len(wanted) + 2))  # at least 3 parts: a rotation needs 3 different crops
    path = body.path_m if body.path_m is not None else (0.6 if garden else 3.0)
    try:
        rects = geo.split_strips(f.outline if f.shape == "irregular" else None, f.width_m, f.length_m, parts, path)
    except ZeroDivisionError:
        raise HTTPException(400, "Il terreno è troppo stretto per essere diviso così.")
    bed_name = "Aiuola" if garden else "Parte"
    secs, n = [], 0
    for r in rects:
        if r["kind"] == "bed":
            n += 1
            secs.append(SectionIn(name=f"{bed_name} {n}", **r))
        else:
            secs.append(SectionIn(name="Sentiero" if garden else "Capezzagna", **r))
    secs.sort(key=lambda s: (s.x, s.y))
    body2 = LayoutIn(width_m=f.width_m, length_m=f.length_m, shape=f.shape or "rectangle", outline=f.outline,
                     orientation_deg=f.orientation_deg or 0, exposure=f.exposure, sections=secs)
    out = save_layout(plot_id, body2, db)
    beds = [x for x in out["sections"] if x["kind"] == "bed"]
    return {**out, "auto": {"parts": len(beds), "path_m": path,
                            "bed_area_m2": round(sum(b["area_m2"] for b in beds) / max(1, len(beds)), 1)}}


@router.get("/rotation/plots/{plot_id}/ecosystems")
def plot_ecosystems(plot_id: str, db: Session = Depends(get_db)):
    f = _plot(db, plot_id)
    prof = store.read_profile(db, f)
    crops = {h.crop for h in db.query(CropHistory).filter(CropHistory.field_id == f.id)} |             {p.crop for p in db.query(PlannedCrop).filter(PlannedCrop.field_id == f.id)} |             set(((prof.get("goals") or {}).get("wanted") or {}).keys())
    return {"plot_id": f.id, "items": ecosystems.suggest(prof, crops, f.area_m2)}


@router.get("/rotation/aquaponics")
def aquaponics(bed_m2: float, fruiting: bool = False):
    if not 0 < bed_m2 <= 1000:
        raise HTTPException(400, "Indica una superficie coltivata tra 0 e 1000 m².")
    return ecosystems.aquaponics(bed_m2, fruiting)


def _polygon_area(pts: list[list[float]]) -> float:
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return round(abs(a) / 2, 1)


# ---------------- history ----------------
class HistoryCrop(BaseModel):
    crop: str
    section_id: str | None = None
    area_m2: float | None = None
    diseases: str | None = None
    treatments: str | None = None
    notes: str | None = None


class SeasonIn(BaseModel):
    year: int
    status: str  # crop | rest | cover | unknown
    crops: list[HistoryCrop] = PField(default_factory=list)


@router.put("/rotation/plots/{plot_id}/history")
def save_season(plot_id: str, body: SeasonIn, db: Session = Depends(get_db)):
    """Replace what is recorded for one season of a plot. 'unknown' stores nothing invented."""
    f = _plot(db, plot_id)
    if body.status not in STATUSES:
        raise HTTPException(400, "Stato non valido.")
    if not (last_season_year() - 15 <= body.year <= last_season_year() + 1):
        raise HTTPException(400, "Anno fuori intervallo.")
    db.query(CropHistory).filter(CropHistory.field_id == f.id, CropHistory.year == body.year).delete()
    if body.status == "crop":
        if not body.crops:
            raise HTTPException(400, "Indica almeno una coltura.")
        for c in body.crops:
            if c.crop not in rotation.BY_KEY:
                raise HTTPException(400, f"Coltura non riconosciuta: {c.crop}")
            db.add(CropHistory(field_id=f.id, year=body.year, crop=c.crop, status="crop", section_id=c.section_id,
                               area_m2=c.area_m2, diseases=(c.diseases or None), treatments=(c.treatments or None),
                               notes=(c.notes or None)))
    else:
        db.add(CropHistory(field_id=f.id, year=body.year, crop=body.status, status=body.status))
    db.commit()
    return _plot_out(db, f)


def _seasons(rows: list[CropHistory], section_id: str | None, last: int) -> list:
    """Seasons from the most recent back: list of crop keys, or None for rest/cover/unknown/no record."""
    out = []
    for y in range(last, last - HISTORY_YEARS, -1):
        keys = [r.crop for r in rows if r.year == y and r.status == "crop" and r.crop in rotation.BY_KEY
                and (section_id is None or r.section_id in (None, section_id))]
        out.append(keys or None)
    return out


# ---------------- planning ----------------
class GoalsIn(BaseModel):
    wanted: dict[str, float] = PField(default_factory=dict)   # crop -> wished area m² (0 = any)
    purpose: str = "family"                                   # family | commercial
    integrated: bool | None = None                            # joins regional integrated production?
    cap: bool | None = None                                   # receives CAP payments?
    years: int = 4


@router.post("/rotation/plots/{plot_id}/plan")
def make_plan(plot_id: str, goals: GoalsIn, db: Session = Depends(get_db)):
    f = _plot(db, plot_id)
    farm = db.get(Farm, f.farm_id)
    region = farm.region if farm and farm.region in rotation_rules.REGIONS else None
    last = last_season_year()
    rows = db.query(CropHistory).filter(CropHistory.field_id == f.id).all()
    secs = [_sec_out(s, f.outline) for s in _sections(db, f.id)]
    history = {s["id"]: _seasons(rows, s["id"], last) for s in secs}
    has_section_hist = {r.section_id for r in rows if r.section_id}
    for s in secs:  # beds without their own records use the whole-plot records
        if s["id"] not in has_section_hist:
            history[s["id"]] = _seasons(rows, None, last)
    problems, soil = store.engine_inputs(db, f)
    wanted = {k: max(0.0, float(v or 0)) for k, v in goals.wanted.items() if k in rotation.BY_KEY}
    years = [last + 1 + i for i in range(max(1, min(goals.years, 6)))]
    out = rotation_planner.plan_plot(secs, history, _seasons(rows, None, last), years, problems=problems, soil=soil,
                                     region=region, integrated=goals.integrated, wanted=wanted,
                                     plot_area=f.area_m2, purpose=goals.purpose)
    cov = rotation_rules.coverage(region)
    notes = [cov["text"]]
    if goals.cap:
        notes.append(rotation_rules.all_rules(region)[0]["text"])
    if goals.integrated is None and cov["level"] != "none":
        notes.append("Le regole del disciplinare sono obbligatorie solo se aderisci alla produzione integrata: "
                     "qui le trattiamo come vincolanti.")
    known = [y for y in range(last, last - HISTORY_YEARS, -1) if any(r.year == y for r in rows)]
    if len(known) < 3:
        notes.append("Lo storico ha meno di 3 anni registrati: gli anni mancanti non vengono inventati, quindi i "
                     "controlli su quegli anni non sono possibili.")
    return {"plot_id": f.id, "region": region, "coverage": cov, "season_year": last, **out,
            "current": {"year": last, "assignments": _current(rows, secs, last)}, "notes": notes,
            "general_rule": cov.get("general_rule")}


# ---------------- irrigation advice ----------------
class IrrigationIn(BaseModel):
    year: int
    assignments: list[dict] = PField(default_factory=list)   # [{section_id, crop, area_m2}] as shown in the planner


async def _climate(farm: Farm | None) -> tuple[dict | None, str | None]:
    """Monthly ET0 and rain for the farm location (cached); None with the reason when not available."""
    if farm is None or farm.latitude is None or farm.longitude is None:
        return None, "Posizione dell'azienda non indicata: servono le coordinate per il clima (traccia un appezzamento sulla mappa)."
    from app.integrations import open_meteo
    from app.services.agronomy_service import _cached
    key = (round(farm.latitude, 3), round(farm.longitude, 3))
    try:
        raw = await _cached(("climate",) + key, lambda: open_meteo.fetch_daily_climate(farm.latitude, farm.longitude))
        return open_meteo.summarize_climate(raw), None
    except Exception:
        return None, "Il servizio del clima (Open-Meteo) non risponde: per ora mostro solo i coefficienti colturali."


@router.post("/rotation/plots/{plot_id}/irrigation")
async def irrigation_advice(plot_id: str, body: IrrigationIn, db: Session = Depends(get_db)):
    """Water need of the crops planned in a year, month by month (Kc FAO-56 × local ET0 − useful rain), and the
    irrigation system AgroAI suggests next to the one the farmer declared. Advice only: nothing is written."""
    f = _plot(db, plot_id)
    farm = db.get(Farm, f.farm_id)
    climate, why_not = await _climate(farm)
    declared = (store.read_profile(db, f) or {}).get("irrigation")
    kinds = {s.id: s.kind for s in _sections(db, f.id)}
    beds = []
    for a in body.assignments:
        c = rotation.BY_KEY.get(a.get("crop"))
        if c is None:
            continue
        adv = irrigation.advice(c.key, c.name.split(" (")[0], c.group, kinds.get(a.get("section_id"), "bed"),
                                float(a.get("area_m2") or 0), rotation_planner.CALENDAR.get(c.key), climate, declared)
        beds.append({"section_id": a.get("section_id"), "section": a.get("section"), **adv})
    notes = ["Fabbisogno = Kc × ET0 − pioggia utile. Le fasi sono divise in modo indicativo dal calendario di semina e "
             "raccolta; la pioggia utile è stimata come l'80% della pioggia media. Sono medie di più anni, non una previsione."]
    if why_not:
        notes.append(why_not)
    return {"year": body.year, "beds": beds, "declared": declared,
            "climate": {"source": climate["source"], "period": climate["period"]} if climate else None,
            "sources": [irrigation.KC_SOURCE, irrigation.EFF_SOURCE], "notes": notes}


# ---------------- AI Farm Layout Generator ----------------
class LayoutAiIn(BaseModel):
    goals: GoalsIn | None = None                                 # empty: the goals saved in the questionnaire
    parts: int | None = PField(default=None, ge=2, le=12)
    path_m: float | None = PField(default=None, ge=0, le=12)
    greenhouse_m2: float | None = PField(default=None, ge=0, le=100_000)
    water_point: bool = False


@router.post("/rotation/plots/{plot_id}/layout-ai")
def layout_ai(plot_id: str, body: LayoutAiIn, db: Session = Depends(get_db)):
    """Alternative layouts for one plot, each with the rotation plan the engine makes for it and figures to compare
    them. Nothing is written: the farmer previews a layout in the 3D view and saves it with the project."""
    f = _plot(db, plot_id)
    if not f.width_m or not f.length_m:
        raise HTTPException(400, "Prima indica le misure o traccia il terreno sulla mappa.")
    goals = body.goals or GoalsIn(**{k: v for k, v in ((store.read_profile(db, f).get("goals") or {}).items()) if k in GoalsIn.model_fields})
    farm = db.get(Farm, f.farm_id)
    region = farm.region if farm and farm.region in rotation_rules.REGIONS else None
    last = last_season_year()
    rows = db.query(CropHistory).filter(CropHistory.field_id == f.id).all()
    plot_hist = _seasons(rows, None, last)
    problems, soil = store.engine_inputs(db, f)
    wanted = {k: max(0.0, float(v or 0)) for k, v in goals.wanted.items() if k in rotation.BY_KEY}
    years = [last + 1 + i for i in range(max(1, min(goals.years, 6)))]
    area = f.area_m2 or f.width_m * f.length_m
    outline = f.outline if f.shape == "irregular" else None
    out = []
    for v in layout_generator.variants(outline, f.width_m, f.length_m, area, wanted, parts=body.parts, path_m=body.path_m,
                                       greenhouse_m2=body.greenhouse_m2, water_point=body.water_point):
        secs = [{**x, "area_m2": round(geo.area_in(outline, x["x"], x["y"], x["w"], x["h"]), 1)} for x in v["sections"]]
        # new parts have no records of their own: the whole-plot history applies to each of them
        plan = rotation_planner.plan_plot(secs, {}, plot_hist, years, problems=problems, soil=soil, region=region,
                                          integrated=goals.integrated, wanted=wanted, plot_area=area, purpose=goals.purpose)
        grow = sum(x["area_m2"] for x in secs if _growing(x["kind"]))
        paths = sum(x["area_m2"] for x in secs if x["kind"] == "path")
        ass = [a for y in plan["years"] for a in y["assignments"]]
        cnt = {k: sum(1 for a in ass if a["verdict"] == k) for k in ("ok", "care", "no")}
        cover = (sum(len({a["crop"] for a in y["assignments"]} & set(wanted)) for y in plan["years"])
                 / (len(wanted) * len(plan["years"]))) if wanted else None
        unplaced = sorted({u["name"] for y in plan["years"] for u in y["unplaced"]})
        rules = 100 * (cnt["ok"] + 0.5 * cnt["care"]) / max(1, len(ass))
        score = round(0.6 * rules + 0.3 * 100 * (cover if cover is not None else 1) + 0.1 * 100 * (1 - paths / max(1.0, area)))
        out.append({**v, "sections": secs, "plan": plan["years"], "score": score,
                    "metrics": {"parts": sum(1 for x in secs if _growing(x["kind"])), "growing_m2": round(grow, 1),
                                "path_m2": round(paths, 1), "path_share": round(paths / max(1.0, area), 3),
                                "bed_m2": round(grow / max(1, sum(1 for x in secs if _growing(x["kind"]))), 1),
                                "verdicts": cnt, "wanted_cover": None if cover is None else round(cover, 2), "unplaced": unplaced}})
    if not out:
        raise HTTPException(400, "Il terreno è troppo stretto per queste opzioni: riduci le parti o la larghezza dei passaggi.")
    out.sort(key=lambda v: (-v["score"], v["metrics"]["path_share"]))   # tie: less ground lost in paths
    out[0]["best"] = True
    cov = rotation_rules.coverage(region)
    notes = ["Il punteggio serve solo a confrontare le proposte tra loro (60% colture che rispettano le regole, 30% colture "
             "richieste che trovano posto, 10% superficie non persa in passaggi): non è un dato agronomico.", cov["text"]]
    known = [y for y in range(last, last - HISTORY_YEARS, -1) if any(r.year == y for r in rows)]
    if len(known) < 3:
        notes.append("Lo storico ha meno di 3 anni registrati: gli anni mancanti non vengono inventati.")
    return {"plot_id": f.id, "years": years, "wanted": list(wanted), "variants": out, "notes": notes}


def _growing(kind: str) -> bool:
    return kind in rotation_planner.GROWING


def _current(rows: list[CropHistory], secs: list[dict], year: int) -> list[dict]:
    out = []
    for r in rows:
        if r.year != year:
            continue
        c = rotation.BY_KEY.get(r.crop)
        out.append({"section_id": r.section_id, "crop": r.crop, "name": c.name if c else r.crop,
                    "family": c.family if c else "", "status": r.status, "area_m2": r.area_m2})
    return out


class CheckIn(BaseModel):
    section_id: str | None = None
    crop: str
    year: int
    planned: dict[str, str] = PField(default_factory=dict)   # earlier planned years {year: crop} for this bed
    integrated: bool | None = None


@router.post("/rotation/plots/{plot_id}/check")
def check(plot_id: str, body: CheckIn, db: Session = Depends(get_db)):
    """Re-evaluate a crop the farmer moved by hand into a bed for a given year."""
    f = _plot(db, plot_id)
    if body.crop not in rotation.BY_KEY:
        raise HTTPException(400, "Coltura non riconosciuta.")
    return _judge_in_bed(db, f, body.section_id, body.crop, body.year, body.planned, body.integrated)


def _judge_in_bed(db: Session, f: Field, section_id: str | None, crop: str, year: int, planned: dict[str, str],
                  integrated: bool | None) -> dict:
    """Judge a crop in one bed for one year: recorded history first, then the planned seasons in between."""
    farm = db.get(Farm, f.farm_id)
    region = farm.region if farm and farm.region in rotation_rules.REGIONS else None
    last = last_season_year()
    rows = db.query(CropHistory).filter(CropHistory.field_id == f.id).all()
    own = any(r.section_id == section_id for r in rows) if section_id else False
    hist = _seasons(rows, section_id if own else None, last)
    for y in range(last + 1, year):  # planned seasons between now and the checked year come first
        k = planned.get(str(y))
        hist.insert(0, [k] if k in rotation.BY_KEY else None)
    problems, soil = store.engine_inputs(db, f)
    return rotation.judge(rotation.BY_KEY[crop], hist, problems, soil, region, integrated)


class SavePlanIn(BaseModel):
    assignments: list[dict]
    goals: dict | None = None


@router.put("/rotation/plots/{plot_id}/plans/{year}")
def save_plan(plot_id: str, year: int, body: SavePlanIn, db: Session = Depends(get_db)):
    f = _plot(db, plot_id)
    _apply_plan(db, f, year, body.assignments, body.goals, refresh_area=False)
    db.commit()
    return _plot_out(db, f)


def _apply_plan(db: Session, f: Field, year: int, assignments: list[dict], goals: dict | None, refresh_area: bool) -> None:
    """Write one year's plan (no commit). A crop sent without verdict or area is checked here, never stored blank;
    a part that is not in this plot falls back to the whole plot. With refresh_area the area is always the real
    area of the part as drawn now (it may have been moved or resized)."""
    saved = {p["year"]: p["assignments"] for p in store.plans_out(db, f)}
    areas = {s.id: round(geo.area_in(f.outline, s.x, s.y, s.w, s.h), 1) for s in _sections(db, f.id)}
    integrated = (goals or {}).get("integrated")
    out = []
    for a in assignments:
        a = dict(a)
        sid, crop = a.get("section_id"), a.get("crop")
        if sid and sid not in areas:
            sid = a["section_id"] = None
        if a.get("area_m2") is None or refresh_area:
            a["area_m2"] = areas.get(sid) if sid else (f.area_m2 or a.get("area_m2"))
        if a.get("verdict") not in ("ok", "care", "no") and crop in rotation.BY_KEY:
            planned = {str(y): next((x["crop"] for x in ass if x.get("section_id") == sid), None)
                       for y, ass in saved.items() if y < year}
            a["verdict"] = _judge_in_bed(db, f, sid, crop, year, planned, integrated)["verdict"]
        out.append(a)
    store.save_plan(db, f, year, out, goals)


# ---------------- whole project: one save, saved versions, restore ----------------
MAX_REVISIONS = 30


class ProjectIn(BaseModel):
    layouts: dict[str, LayoutIn] = PField(default_factory=dict)              # plot id -> drawing
    plans: dict[str, dict[int, list[dict]]] = PField(default_factory=dict)   # plot id -> year -> assignments
    goals: dict[str, dict | None] = PField(default_factory=dict)             # plot id -> goals used for the plan
    label: str | None = PField(default=None, max_length=128)


def _snapshot(db: Session, farm: Farm) -> dict:
    out = {}
    for f in db.query(Field).filter(Field.farm_id == farm.id).all():
        secs = [{"id": s.id, "name": s.name, "kind": s.kind, "x": s.x, "y": s.y, "w": s.w, "h": s.h, "row_spacing_m": s.row_spacing_m,
                 "plant_spacing_m": s.plant_spacing_m, "row_dir": s.row_dir} for s in _sections(db, f.id)]
        layout = {"width_m": f.width_m, "length_m": f.length_m, "shape": f.shape or "rectangle", "outline": f.outline,
                  "orientation_deg": f.orientation_deg or 0, "exposure": f.exposure, "sections": secs}
        plans = {str(p["year"]): {"assignments": p["assignments"], "goals": p["goals"]} for p in store.plans_out(db, f)}
        out[f.id] = {"name": f.name, "layout": layout if f.width_m and f.length_m else None, "plans": plans}
    return out


def _summary(snap: dict) -> dict:
    return {"plots": len(snap), "parts": sum(len((p["layout"] or {}).get("sections", [])) for p in snap.values()),
            "plans": sum(len(p["plans"]) for p in snap.values()),
            "years": sorted({int(y) for p in snap.values() for y in p["plans"]})}


def _revision(db: Session, farm: Farm, label: str) -> PlannerRevision:
    snap = _snapshot(db, farm)
    rev = PlannerRevision(farm_id=farm.id, label=label[:128], summary=_summary(snap), snapshot=snap)
    db.add(rev)
    db.flush()
    old = db.query(PlannerRevision).filter(PlannerRevision.farm_id == farm.id).order_by(PlannerRevision.created_at.desc()).offset(MAX_REVISIONS).all()
    for r in old:
        db.delete(r)
    return rev


def _rev_out(r: PlannerRevision) -> dict:
    return {"id": r.id, "label": r.label, "summary": r.summary, "created_at": r.created_at.isoformat()}


def _apply_project(db: Session, farm: Farm, body: ProjectIn) -> dict[str, str]:
    plots = {f.id: f for f in db.query(Field).filter(Field.farm_id == farm.id).all()}
    for pid in [*body.layouts, *body.plans]:
        if pid not in plots:
            raise HTTPException(404, "Appezzamento non trovato: nessuna modifica salvata.")
    ids: dict[str, str] = {}
    for pid, lay in body.layouts.items():
        ids.update(_apply_layout(db, plots[pid], lay))
    db.flush()
    for pid, years in body.plans.items():
        for year, ass in sorted(years.items()):
            fixed = [{**a, "section_id": ids.get(a.get("section_id"), a.get("section_id"))} for a in ass]
            _apply_plan(db, plots[pid], int(year), fixed, body.goals.get(pid), refresh_area=True)
    return ids


@router.put("/rotation/project")
def save_project(body: ProjectIn, db: Session = Depends(get_db)):
    """Save the planner in one go: drawings first (new parts get their id), then the plans that use them.
    All or nothing: if anything is invalid, nothing is written. Each save is kept as a version."""
    farm = _farm(db)
    if not db.query(PlannerRevision).filter(PlannerRevision.farm_id == farm.id).first():
        _revision(db, farm, "Situazione prima del primo salvataggio")   # the starting point can always be restored
    ids = _apply_project(db, farm, body)
    db.flush()
    rev = _revision(db, farm, body.label or "Salvataggio del progetto")
    db.commit()
    return {"ids": ids, "revision": _rev_out(rev)}


@router.get("/rotation/project/revisions")
def list_revisions(db: Session = Depends(get_db)):
    farm = _farm(db)
    rows = db.query(PlannerRevision).filter(PlannerRevision.farm_id == farm.id).order_by(PlannerRevision.created_at.desc()).all()
    return {"revisions": [_rev_out(r) for r in rows], "max": MAX_REVISIONS}


@router.post("/rotation/project/revisions/{rev_id}/restore")
def restore_revision(rev_id: str, db: Session = Depends(get_db)):
    """Bring drawings and plans back to a saved version. Plots created later are left as they are; plots deleted
    since then cannot come back. Crop history is never touched."""
    farm = _farm(db)
    rev = db.get(PlannerRevision, rev_id)
    if rev is None or rev.farm_id != farm.id:
        raise HTTPException(404, "Versione non trovata.")
    existing = {f.id for f in db.query(Field).filter(Field.farm_id == farm.id).all()}
    snap = {pid: p for pid, p in (rev.snapshot or {}).items() if pid in existing}
    layouts = {pid: LayoutIn(**p["layout"]) for pid, p in snap.items() if p.get("layout")}
    plans = {pid: {int(y): v["assignments"] for y, v in p["plans"].items()} for pid, p in snap.items()}
    goals = {pid: next((v.get("goals") for v in p["plans"].values() if v.get("goals")), None) for pid, p in snap.items()}
    # years planned now but not in that version are removed, so the plan really is the old one
    for pid, p in snap.items():
        keep = {int(y) for y in p["plans"]}
        for plan in db.query(RotationPlan).filter(RotationPlan.field_id == pid).all():
            if plan.year not in keep:
                db.query(PlannedCrop).filter(PlannedCrop.plan_id == plan.id).delete()
                db.delete(plan)
    _apply_project(db, farm, ProjectIn(layouts=layouts, plans=plans, goals=goals))
    db.flush()
    when = rev.created_at.strftime("%d/%m/%Y %H:%M")
    new = _revision(db, farm, f"Ripristino della versione del {when}")
    db.commit()
    return {"revision": _rev_out(new), "skipped_plots": len(rev.snapshot or {}) - len(snap)}


@router.delete("/rotation/plots/{plot_id}/plans/{year}", status_code=204)
def delete_plan(plot_id: str, year: int, db: Session = Depends(get_db)):
    f = _plot(db, plot_id)
    plan = db.query(RotationPlan).filter_by(field_id=f.id, year=year).first()
    if plan is not None:
        db.query(PlannedCrop).filter(PlannedCrop.plan_id == plan.id).delete()
        db.delete(plan)
    db.commit()
