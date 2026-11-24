from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models import Alert, Prediction


class AlertService:
    def __init__(self, db: Session):
        self.db = db

    def from_prediction(self, p: Prediction) -> Alert | None:
        if p.severity in ("info", "low"):
            return None
        a = Alert(
            zone_id=p.zone_id,
            prediction_id=p.id,
            ts=datetime.now(timezone.utc),
            category=p.kind,
            severity=p.severity,
            message=p.summary,
            data={"confidence": p.confidence, "supporting": p.supporting},
        )
        self.db.add(a)
        return a

    def list(self, acknowledged: bool | None = None, limit: int = 100) -> list[Alert]:
        q = select(Alert).order_by(desc(Alert.ts)).limit(limit)
        if acknowledged is not None:
            q = q.where(Alert.acknowledged == acknowledged)
        return list(self.db.execute(q).scalars().all())

    def ack(self, alert_id: str, user: str) -> Alert | None:
        a = self.db.get(Alert, alert_id)
        if a is None:
            return None
        a.acknowledged = True
        a.ack_by = user
        a.ack_at = datetime.now(timezone.utc)
        return a
