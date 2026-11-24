from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class MLModel(Base):
    """Versioned model registry. Training never activates a model by itself:
    a human reviews the validation metrics and activates it explicitly."""
    __tablename__ = "ml_models"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(64), index=True)  # acoustic_custom
    version: Mapped[int] = mapped_column(Integer)
    feature_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="trained", index=True)  # trained|active|archived
    labels: Mapped[list] = mapped_column(JSON, default=list)
    class_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    n_samples: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_manifest: Mapped[list] = mapped_column(JSON, default=list)
    path: Mapped[str] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
