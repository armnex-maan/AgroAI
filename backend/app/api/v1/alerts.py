from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.alert import AlertOut
from app.services.alert_service import AlertService

router = APIRouter()


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(acknowledged: bool | None = None, limit: int = Query(100, le=500),
                db: Session = Depends(get_db)):
    return AlertService(db).list(acknowledged=acknowledged, limit=limit)


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
def ack_alert(alert_id: str, user: str = "demo", db: Session = Depends(get_db)):
    a = AlertService(db).ack(alert_id, user=user)
    if a is None:
        raise HTTPException(404, "alert not found")
    db.commit()
    return a
