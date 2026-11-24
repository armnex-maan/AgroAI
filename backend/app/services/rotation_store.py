"""Storage for the crop-rotation planner: turns the questionnaire answers into the dedicated tables
(conditions, problems, planned crops) and keeps the regulation tables in sync with the encoded rules.

Independent from vision/diagnosis: only farm, field and rotation tables are touched."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.ml.agronomy import rotation, rotation_rules
from app.models import (CropHistory, Field, PlannedCrop, PlotConditions, PlotProblem, PlotSection,
                        RegulationSource, RotationPlan, RotationRule)

COND_KEYS = ("texture", "fertility", "compaction", "water", "irrigation", "manure", "cover")
VALID = {
    "texture": {"sandy", "clay", "silty", "mixed"}, "fertility": {"high", "medium", "low"},
    "compaction": {"low", "medium", "high"}, "water": {"plenty", "limited", "none"},
    "irrigation": {"drip", "sprinkler", "furrow", "manual", "none"}, "manure": {"yearly", "sometimes", "no"},
    "cover": {"yes", "maybe", "no"},
}
TABLE_KEYS = set(COND_KEYS) | {"problems", "other_problem", "soil_state"}


def soil_state(cond: dict) -> str | None:
    """Simple soil state used by the rotation engine, derived only from the farmer's answers."""
    if not any(cond.get(k) for k in ("compaction", "fertility")):
        return None
    if cond.get("compaction") == "high":
        return "hard"
    return {"low": "tired", "high": "good"}.get(cond.get("fertility") or "", "normal")


# ---------------- conditions and problems ----------------
def write_profile(db: Session, f: Field, profile: dict) -> None:
    """Questionnaire answers -> plot_conditions + plot_problems; anything else (goals) stays in fields.profile."""
    cond = {k: profile.get(k) if profile.get(k) in VALID[k] else None for k in COND_KEYS}
    row = db.get(PlotConditions, f.id) or PlotConditions(field_id=f.id)
    for k, v in cond.items():
        setattr(row, k, v)
    st = profile.get("soil_state")
    row.soil_state = st if st in rotation.SOIL_STATE else soil_state(cond)
    row.updated_at = datetime.utcnow()
    db.merge(row)
    wanted = [p for p in profile.get("problems") or [] if p in rotation.PROBLEMS or p == "other"]
    other = (profile.get("other_problem") or "").strip()
    if other and "other" not in wanted:
        wanted.append("other")
    existing = {p.problem: p for p in db.query(PlotProblem).filter(PlotProblem.field_id == f.id)}
    for key, p in existing.items():
        if key not in wanted:
            db.delete(p)
    for key in wanted:
        p = existing.get(key) or PlotProblem(field_id=f.id, problem=key)
        p.description = other[:255] if key == "other" else rotation.PROBLEMS[key]["label"]
        db.add(p)
    f.profile = {k: v for k, v in profile.items() if k not in TABLE_KEYS} or None
    if cond["texture"]:
        f.soil_type = {"sandy": "sand", "clay": "clay", "silty": "silt", "mixed": "loam"}[cond["texture"]]


def read_profile(db: Session, f: Field) -> dict:
    """Profile as the UI and engine expect it: table values first, legacy JSON only for plots not migrated."""
    legacy = dict(f.profile or {})
    row = db.get(PlotConditions, f.id)
    probs = db.query(PlotProblem).filter(PlotProblem.field_id == f.id).all()
    if row is None and not probs:
        return legacy
    out = {k: v for k, v in legacy.items() if k not in TABLE_KEYS}
    if row is not None:
        out.update({k: getattr(row, k) for k in COND_KEYS if getattr(row, k)})
        if row.soil_state:
            out["soil_state"] = row.soil_state
    out["problems"] = [p.problem for p in probs if p.problem != "other"]
    other = next((p.description for p in probs if p.problem == "other"), None)
    if other:
        out["other_problem"] = other
    return out


def engine_inputs(db: Session, f: Field) -> tuple[set[str], str | None]:
    prof = read_profile(db, f)
    problems = {p for p in prof.get("problems", []) if p in rotation.PROBLEMS}
    st = prof.get("soil_state")
    return problems, st if st in rotation.SOIL_STATE else None


# ---------------- plans ----------------
def save_plan(db: Session, f: Field, year: int, assignments: list[dict], goals: dict | None) -> RotationPlan:
    plan = db.query(RotationPlan).filter_by(field_id=f.id, year=year).first()
    if plan is None:
        plan = RotationPlan(field_id=f.id, year=year, assignments=[])
        db.add(plan)
        db.flush()
    db.query(PlannedCrop).filter(PlannedCrop.plan_id == plan.id).delete()
    sections = {s.id for s in db.query(PlotSection).filter(PlotSection.field_id == f.id)}
    for a in assignments:
        crop = a.get("crop")
        if crop not in rotation.BY_KEY and crop != "cover":
            continue
        sid = a.get("section_id")
        db.add(PlannedCrop(plan_id=plan.id, field_id=f.id, section_id=sid if sid in sections else None, year=year,
                           crop=crop, family=rotation.BY_KEY[crop].family if crop in rotation.BY_KEY else None,
                           area_m2=a.get("area_m2"), verdict=a.get("verdict") if a.get("verdict") in ("ok", "care", "no") else None,
                           manual=bool(a.get("manual"))))
    plan.assignments = []  # the rows in planned_crops are the record; the JSON column is kept only for old data
    plan.goals = goals
    plan.status = "saved"
    plan.updated_at = datetime.utcnow()
    return plan


def plans_out(db: Session, f: Field) -> list[dict]:
    names = {s.id: s.name for s in db.query(PlotSection).filter(PlotSection.field_id == f.id)}
    out = []
    for p in db.query(RotationPlan).filter(RotationPlan.field_id == f.id).order_by(RotationPlan.year):
        rows = db.query(PlannedCrop).filter(PlannedCrop.plan_id == p.id).all()
        if rows:
            ass = [{"section_id": r.section_id, "section": names.get(r.section_id, "Intero appezzamento"),
                    "crop": r.crop, "name": rotation.BY_KEY[r.crop].name if r.crop in rotation.BY_KEY else "Sovescio",
                    "family": r.family or "", "area_m2": r.area_m2, "verdict": r.verdict, "manual": r.manual}
                   for r in rows]
        else:
            ass = p.assignments or []
        out.append({"year": p.year, "assignments": ass, "goals": p.goals, "status": p.status,
                    "updated_at": p.updated_at.isoformat()})
    return out


def delete_plot_data(db: Session, field_id: str) -> None:
    """SQLite does not enforce ON DELETE CASCADE by default: remove every rotation row of a plot explicitly."""
    for model in (PlannedCrop, RotationPlan, CropHistory, PlotProblem, PlotConditions, PlotSection):
        db.query(model).filter(model.field_id == field_id).delete()


# ---------------- regulation sources and rules ----------------
def _rule_rows() -> list[dict]:
    d = rotation_rules.DOCS
    rows = [{"source_id": "eu_gaec7", "crop": "*", "level": "obbligatoria", "interval_years": None, "repeat": None,
             "text": rotation_rules.all_rules(None)[0]["text"]}]
    for region, (doc_id, text) in rotation_rules.GENERAL.items():
        rows.append({"source_id": doc_id, "crop": "*", "level": "disciplinare", "interval_years": None,
                     "repeat": None, "text": text})
    for region, crops in rotation_rules.REGIONAL_CROP_RULES.items():
        for crop, r in crops.items():
            rows.append({"source_id": r["doc"], "crop": crop, "level": "disciplinare", "interval_years": r.get("gap"),
                         "repeat": r.get("repeat"), "text": r["text"]})
    for c in rotation.CROPS:
        r = rotation_rules.er_rule(c)
        rows.append({"source_id": "er_2023", "crop": c.key, "level": "disciplinare", "interval_years": r["gap"],
                     "repeat": r["repeat"], "text": r["text"]})
    for r in rows:
        r["region"], r["year"] = d[r["source_id"]]["region"], d[r["source_id"]]["year"]
    return rows


def sync_rules(db: Session) -> int:
    """Upsert regulation_sources and rotation_rules from the encoded rules (the code is the reviewed source)."""
    for key, d in rotation_rules.DOCS.items():
        db.merge(RegulationSource(id=key, region=d["region"], year=d["year"], type=d["type"], title=d["title"], url=d["url"]))
    db.flush()
    wanted = {(r["source_id"], r["crop"]): r for r in _rule_rows()}
    existing = {(r.source_id, r.crop): r for r in db.query(RotationRule)}
    for k, row in existing.items():
        if k not in wanted:
            db.delete(row)
    for k, r in wanted.items():
        row = existing.get(k) or RotationRule(source_id=r["source_id"], crop=r["crop"])
        for a in ("region", "year", "level", "interval_years", "repeat", "text"):
            setattr(row, a, r[a])
        db.add(row)
    db.commit()
    return len(wanted)


def migrate_legacy(db: Session) -> dict:
    """Move answers kept in fields.profile and plans kept in rotation_plans.assignments into the new tables."""
    n_prof = n_plan = 0
    for f in db.query(Field).all():
        prof = f.profile or {}
        if db.get(PlotConditions, f.id) is None and any(k in prof for k in TABLE_KEYS):
            write_profile(db, f, prof)
            n_prof += 1
    db.flush()
    for p in db.query(RotationPlan).all():
        if p.assignments and not db.query(PlannedCrop).filter(PlannedCrop.plan_id == p.id).count():
            f = db.get(Field, p.field_id)
            if f is not None:
                save_plan(db, f, p.year, list(p.assignments), p.goals)
                n_plan += 1
    db.commit()
    return {"profiles": n_prof, "plans": n_plan}
