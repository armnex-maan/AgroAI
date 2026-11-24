from datetime import datetime
import uuid
from sqlalchemy import String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Verification(Base):
    """Farmer feedback on predictions/alerts — feeds continuous-learning datasets."""
    __tablename__ = "verifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_type: Mapped[str] = mapped_column(String(32))  # prediction | alert | detection
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    verdict: Mapped[str] = mapped_column(String(32))  # confirmed | false_positive | partial | unknown
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    verifier: Mapped[str] = mapped_column(String(128), default="user")
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
