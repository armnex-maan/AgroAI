from datetime import datetime
import uuid
from sqlalchemy import String, Float, ForeignKey, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AudioRecording(Base):
    __tablename__ = "audio_recordings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    sample_rate: Mapped[int] = mapped_column(Integer, default=16000)
    channels: Mapped[int] = mapped_column(Integer, default=1)
    path: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|processed|error
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    detections: Mapped[list["AcousticDetection"]] = relationship(back_populates="recording", cascade="all, delete-orphan")


class AcousticDetection(Base):
    __tablename__ = "acoustic_detections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    recording_id: Mapped[str] = mapped_column(ForeignKey("audio_recordings.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(64))  # yamnet | birdnet | underground-experimental | manual
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(128))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    signal_quality: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    recording: Mapped[AudioRecording] = relationship(back_populates="detections")


class AcousticLabel(Base):
    """Manual labels — used for dataset export and continuous learning."""
    __tablename__ = "acoustic_labels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    recording_id: Mapped[str] = mapped_column(ForeignKey("audio_recordings.id", ondelete="CASCADE"), index=True)
    start_s: Mapped[float] = mapped_column(Float, default=0.0)
    end_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    label: Mapped[str] = mapped_column(String(128))
    labeler: Mapped[str] = mapped_column(String(128), default="user")
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
