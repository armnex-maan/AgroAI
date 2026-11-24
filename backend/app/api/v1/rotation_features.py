"""Farm elements of the Visual Farm Planner (buildings, tanks, wells, roads, irrigation mains, hedges, orchards,
vineyards, ponds). Stored as GeoJSON in WGS84; independent from vision/diagnosis.

Numbers the farmer does not give stay empty: the 3D view then draws an indicative layout and says so."""
from __future__ import annotations

import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PField
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml.agronomy import crop_heights, geo
from app.models import Farm, FarmFeature

router = APIRouter()

NUM = "num"
SPEC: dict[str, dict] = {
    "building": {"label": "Edificio", "geom": "Point", "props": {
        "type": ["casale", "fienile", "magazzino", "stalla", "ricovero_attrezzi"],
        "width_m": (NUM, 3, 80), "length_m": (NUM, 3, 150), "floors": (NUM, 1, 4), "rotation_deg": (NUM, -180, 180)}},
    "tank": {"label": "Cisterna", "geom": "Point", "props": {"diameter_m": (NUM, 1, 30), "height_m": (NUM, 1, 15), "capacity_l": (NUM, 100, 10_000_000)}},
    "well": {"label": "Pozzo", "geom": "Point", "props": {"depth_m": (NUM, 1, 500)}},
    "road": {"label": "Strada poderale", "geom": "LineString", "props": {"width_m": (NUM, 1.5, 12), "surface": ["sterrato", "ghiaia", "asfalto", "cemento"]}},
    "pipe": {"label": "Condotta irrigua", "geom": "LineString", "props": {"diameter_mm": (NUM, 10, 1000), "buried": [True, False]}},
    "hedge": {"label": "Siepe o filare", "geom": "LineString", "props": {"height_m": (NUM, 0.5, 25), "species": "text"}},
    "orchard": {"label": "Frutteto", "geom": "Polygon", "props": {
        "species": [k for k in crop_heights.TREE_HEIGHT_M if not k.startswith("grape")],
        "row_spacing_m": (NUM, 1.5, 12), "tree_spacing_m": (NUM, 0.5, 10), "planted_year": (NUM, 1900, 2100)}},
    "vineyard": {"label": "Vigneto", "geom": "Polygon", "props": {
        "species": ["grape_wine", "grape_table"], "row_spacing_m": (NUM, 1.5, 5), "plant_spacing_m": (NUM, 0.5, 3), "planted_year": (NUM, 1900, 2100)}},
    "pond": {"label": "Laghetto o vasca", "geom": "Polygon", "props": {"depth_m": (NUM, 0.2, 15)}},
    "greenhouse": {"label": "Serra", "geom": "Polygon", "props": {
        "type": ["tunnel", "vetro", "ombraio"], "height_m": (NUM, 1.5, 10), "heated": [True, False]}},
    "net": {"label": "Rete di copertura", "geom": "Polygon", "props": {
        "type": ["antigrandine", "ombreggiante", "antinsetto"], "height_m": (NUM, 1, 8)}},
    "fence": {"label": "Recinzione", "geom": "LineString", "props": {
        "type": ["rete_metallica", "staccionata", "elettrica"], "height_m": (NUM, 0.5, 4)}},
    "equipment": {"label": "Macchina o attrezzatura", "geom": "Point", "props": {
        "type": ["trattore", "motocoltivatore", "atomizzatore", "rimorchio", "pompa", "centralina_irrigazione"],
        "rotation_deg": (NUM, -180, 180), "model": "text"}},
    "beehive": {"label": "Arnie", "geom": "Point", "props": {"count": (NUM, 1, 100)}},
    "compost": {"label": "Compostiera", "geom": "Point", "props": {"volume_m3": (NUM, 0.2, 200)}},
    "solar": {"label": "Pannelli solari", "geom": "Polygon", "props": {"power_kw": (NUM, 0.5, 5000)}},
    "sprinkler": {"label": "Irrigatore", "geom": "Point", "props": {
        "type": ["statico", "dinamico", "a_impulsi", "microirrigatore"], "radius_m": (NUM, 0.5, 60), "flow_l_h": (NUM, 10, 100_000)}},
}


def _check_coords(coords: list) -> list[list[float]]:
    out = []
    for c in coords:
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            raise HTTPException(400, "Coordinate non valide.")
        lon, lat = float(c[0]), float(c[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise HTTPException(400, "Coordinate fuori scala.")
        out.append([round(lon, 8), round(lat, 8)])
    return out


def _geometry(kind: str, g: dict) -> dict:
    want = SPEC[kind]["geom"]
    if not isinstance(g, dict) or g.get("type") != want:
        raise HTTPException(400, f"{SPEC[kind]['label']}: serve una geometria {want}.")
    c = g.get("coordinates")
    if want == "Point":
        return {"type": "Point", "coordinates": _check_coords([c])[0]}
    if want == "LineString":
        pts = _check_coords(c or [])
        if len(pts) < 2:
            raise HTTPException(400, "Una linea ha bisogno di almeno 2 punti.")
        return {"type": "LineString", "coordinates": pts}
    ring = _check_coords((c or [[]])[0])
    try:
        ring = geo.clean_ring(ring)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


LABELS = {"type": "Tipo", "width_m": "Larghezza", "length_m": "Lunghezza", "floors": "Piani", "rotation_deg": "Rotazione",
          "diameter_m": "Diametro", "height_m": "Altezza", "capacity_l": "Capacità", "depth_m": "Profondità", "surface": "Fondo",
          "diameter_mm": "Diametro", "buried": "Interrata", "species": "Specie", "row_spacing_m": "Distanza tra le file",
          "tree_spacing_m": "Distanza sulla fila", "plant_spacing_m": "Distanza sulla fila", "planted_year": "Anno d'impianto",
          "radius_m": "Raggio di bagnatura", "flow_l_h": "Portata", "heated": "Riscaldata", "count": "Numero",
          "volume_m3": "Volume", "power_kw": "Potenza", "model": "Modello"}


def _props(kind: str, p: dict | None) -> dict:
    out = {}
    for k, rule in SPEC[kind]["props"].items():
        v = (p or {}).get(k)
        if v is None or v == "":
            continue                                    # not given: stays empty, never guessed
        if rule == "text":
            out[k] = str(v)[:120]
        elif isinstance(rule, list):
            if v not in rule:
                raise HTTPException(400, f"Valore non valido per {LABELS.get(k, k)}.")
            out[k] = v
        else:
            _, lo, hi = rule
            try:
                f = float(v)
            except (TypeError, ValueError):
                raise HTTPException(400, f"{LABELS.get(k, k)} deve essere un numero.")
            if not lo <= f <= hi:
                raise HTTPException(400, f"{LABELS.get(k, k)} deve essere tra {lo:g} e {hi:g}.")
            out[k] = f
    return out


def _line_length(pts: list[list[float]]) -> float:
    tot = 0.0
    for (lo1, la1), (lo2, la2) in zip(pts, pts[1:]):
        a = math.sin(math.radians(la2 - la1) / 2) ** 2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
        tot += 2 * geo.R * math.asin(math.sqrt(a))
    return tot


def _out(f: FarmFeature) -> dict:
    g = f.geometry or {}
    extra: dict = {}
    if g.get("type") == "Polygon":
        extra["area_m2"] = round(geo.area_m2(g["coordinates"][0]), 1)
    elif g.get("type") == "LineString":
        extra["length_m"] = round(_line_length(g["coordinates"]), 1)
    sp = (f.props or {}).get("species")
    if f.kind in ("orchard", "vineyard") and sp in crop_heights.TREE_HEIGHT_M:
        extra["height_m"] = list(crop_heights.TREE_HEIGHT_M[sp])
        extra["species_name"] = crop_heights.TREE_NAMES[sp]
    return {"id": f.id, "kind": f.kind, "label": SPEC.get(f.kind, {}).get("label", f.kind), "name": f.name, "geometry": g,
            "props": f.props or {}, **extra}


def _farm(db: Session) -> Farm:
    farm = db.query(Farm).first()
    if farm is None:
        raise HTTPException(404, "Nessuna azienda.")
    return farm


@router.get("/rotation/features")
def list_features(db: Session = Depends(get_db)):
    farm = db.query(Farm).first()
    rows = db.query(FarmFeature).filter(FarmFeature.farm_id == farm.id).order_by(FarmFeature.created_at).all() if farm else []
    kinds = {k: {"label": v["label"], "geom": v["geom"],
                 "props": {p: (r if isinstance(r, (list, str)) else {"min": r[1], "max": r[2]}) for p, r in v["props"].items()}}
             for k, v in SPEC.items()}
    trees = {k: {"name": crop_heights.TREE_NAMES[k], "height_m": list(h)} for k, h in crop_heights.TREE_HEIGHT_M.items()}
    return {"features": [_out(f) for f in rows], "kinds": kinds, "trees": trees, "height_source": crop_heights.SOURCE}


class FeatureIn(BaseModel):
    kind: str
    name: str = PField(min_length=1, max_length=128)
    geometry: dict
    props: dict | None = None


@router.post("/rotation/features", status_code=201)
def create_feature(body: FeatureIn, db: Session = Depends(get_db)):
    if body.kind not in SPEC:
        raise HTTPException(400, "Tipo di elemento non valido.")
    farm = _farm(db)
    f = FarmFeature(farm_id=farm.id, kind=body.kind, name=body.name.strip(), geometry=_geometry(body.kind, body.geometry),
                    props=_props(body.kind, body.props))
    db.add(f)
    db.commit()
    return _out(f)


class FeatureUpdate(BaseModel):
    name: str | None = PField(default=None, min_length=1, max_length=128)
    geometry: dict | None = None
    props: dict | None = None


@router.put("/rotation/features/{feature_id}")
def update_feature(feature_id: str, body: FeatureUpdate, db: Session = Depends(get_db)):
    f = db.get(FarmFeature, feature_id)
    if f is None:
        raise HTTPException(404, "Elemento non trovato.")
    if body.name is not None:
        f.name = body.name.strip()
    if body.geometry is not None:
        f.geometry = _geometry(f.kind, body.geometry)
    if body.props is not None:
        f.props = _props(f.kind, body.props)
    f.updated_at = datetime.utcnow()
    db.commit()
    return _out(f)


@router.delete("/rotation/features/{feature_id}", status_code=204)
def delete_feature(feature_id: str, db: Session = Depends(get_db)):
    f = db.get(FarmFeature, feature_id)
    if f is None:
        raise HTTPException(404, "Elemento non trovato.")
    db.delete(f)
    db.commit()
