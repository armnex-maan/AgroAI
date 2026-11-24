from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.schemas.alert import AssessmentOut, PredictionOut, AlertOut
from app.services.intelligence_service import assess_zone
from app.services.alert_service import AlertService
from app.services.llm_service import explain

router = APIRouter()


@router.get("/intelligence/assessment", response_model=AssessmentOut)
async def assessment(zone_id: str | None = None, db: Session = Depends(get_db)):
    result = assess_zone(db, zone_id)
    alert_svc = AlertService(db)
    created_alerts = []
    for p in result["predictions"]:
        a = alert_svc.from_prediction(p)
        if a is not None:
            db.flush()
            created_alerts.append(a)
    db.commit()

    narrative = None
    if settings.ai_provider != "none":
        narrative = await explain(result["findings"], result["recommendations"])

    return AssessmentOut(
        zone_id=zone_id,
        status=result["status"],
        findings=result["findings"],
        recommendations=result["recommendations"],
        narrative=narrative,
        predictions=[PredictionOut.model_validate(p) for p in result["predictions"]],
        alerts=[AlertOut.model_validate(a) for a in created_alerts],
        sources=result["sources"],
        generated_at=result["generated_at"],
    )
