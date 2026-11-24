from pydantic import BaseModel, ConfigDict
from app.schemas.common import Severity, UTCDateTime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    zone_id: str | None
    ts: UTCDateTime
    category: str
    severity: Severity
    message: str
    data: dict | None = None
    acknowledged: bool
    prediction_id: str | None = None


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    zone_id: str | None
    ts: UTCDateTime
    kind: str
    severity: Severity
    summary: str
    supporting: list
    confidence: float
    model: str
    explanation: str | None = None


class AssessmentOut(BaseModel):
    zone_id: str | None
    status: str
    findings: list[str]
    recommendations: list[str]
    narrative: str | None = None
    predictions: list[PredictionOut]
    alerts: list[AlertOut]
    sources: list[str]
    generated_at: UTCDateTime
