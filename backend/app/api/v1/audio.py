import io
import math

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.security import verify_device_hmac
from app.schemas.common import iso_utc
from app.models import AudioRecording, AcousticDetection, AcousticLabel, Device, MLModel
from app.ml.audio import yamnet, birdnet, perch
from app.services.audio_service import AudioService

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class RecordingOut(BaseModel):
    id: str
    zone_id: str | None
    device_id: str | None
    ts: str
    duration_s: float
    sample_rate: int
    source: str
    status: str
    notes: str | None = None
    verdict: str | None = None
    summary: str | None = None


def _rec_out(r: AudioRecording, ident: AcousticDetection | None = None) -> RecordingOut:
    return RecordingOut(
        id=r.id, zone_id=r.zone_id, device_id=r.device_id, ts=iso_utc(r.ts),
        duration_s=r.duration_s, sample_rate=r.sample_rate, source=r.source, status=r.status,
        notes=r.notes,
        verdict=ident.category if ident else None,
        summary=(ident.evidence or {}).get("summary") if ident else None,
    )


class DetectionOut(BaseModel):
    id: str
    model: str
    model_version: str | None
    category: str
    confidence: float
    signal_quality: float
    evidence: dict | None
    ts: str


def _det_out(d: AcousticDetection) -> DetectionOut:
    return DetectionOut(id=d.id, model=d.model, model_version=d.model_version, category=d.category,
                        confidence=d.confidence, signal_quality=d.signal_quality, evidence=d.evidence,
                        ts=iso_utc(d.ts))


class LabelIn(BaseModel):
    label: str
    start_s: float = 0.0
    end_s: float | None = None
    labeler: str = "user"
    notes: str | None = None


class LabelOut(BaseModel):
    id: str
    recording_id: str
    label: str
    start_s: float
    end_s: float | None
    labeler: str
    notes: str | None


def _label_out(r: AcousticLabel) -> LabelOut:
    return LabelOut(id=r.id, recording_id=r.recording_id, label=r.label, start_s=r.start_s,
                    end_s=r.end_s, labeler=r.labeler, notes=r.notes)


class ModelOut(BaseModel):
    id: str
    kind: str
    version: int
    status: str
    feature_version: str
    labels: list
    class_counts: dict
    n_samples: int
    metrics: dict
    created_at: str
    notes: str | None


def _model_out(m: MLModel) -> ModelOut:
    return ModelOut(id=m.id, kind=m.kind, version=m.version, status=m.status,
                    feature_version=m.feature_version, labels=m.labels, class_counts=m.class_counts,
                    n_samples=m.n_samples, metrics=m.metrics, created_at=iso_utc(m.created_at),
                    notes=m.notes)


# ---------------- engines ----------------
@router.get("/audio/engines")
def engines(db: Session = Depends(get_db)):
    active = AudioService(db).active_model()
    return {
        "perch": {**perch.status(), "enabled": True} if settings.perch_enabled
        else {"available": False, "enabled": False},
        "yamnet": {**yamnet.status(), "enabled": settings.yamnet_enabled, "license": "Apache-2.0"}
        if settings.yamnet_enabled else {"available": False, "enabled": False},
        "birdnet": birdnet.status(settings.birdnet_enabled),
        "farm_model": {"active": bool(active), "version": active.version if active else None,
                       "labels": active.labels if active else []},
        "underground_experimental": {"available": True,
                                     "note": "pattern evidence only — never a species identification"},
        "thresholds": {"probable": settings.identification_probable,
                       "possible": settings.identification_possible,
                       "farm_model_min_confidence": settings.custom_model_min_confidence},
    }


# ---------------- recordings ----------------
@router.post("/audio/upload", response_model=RecordingOut, status_code=201)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    zone_id: str | None = Form(None),
    device_id: str | None = Form(None),
    source: str = Form("manual"),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if source not in ("manual", "device", "simulation"):
        raise HTTPException(400, "invalid source")
    if not file.filename or not file.filename.lower().endswith((".wav", ".flac", ".ogg")):
        raise HTTPException(400, "Formato non supportato: carica un file audio WAV, FLAC o OGG.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File troppo grande (massimo 25 MB).")
    if source == "device":
        dev = db.get(Device, device_id) if device_id else None
        if dev is None:
            raise HTTPException(401, "unknown device")
        verify_device_hmac(content, request.headers.get("x-agroai-timestamp", ""),
                           request.headers.get("x-agroai-signature", ""), dev.api_secret)
        zone_id = zone_id or dev.zone_id
    try:
        rec = AudioService(db).save(content, zone_id=zone_id, device_id=device_id, source=source, notes=notes)
    except Exception:
        raise HTTPException(400, "Non riesco a leggere questo file audio. Prova a salvarlo di nuovo come WAV.")
    return _rec_out(rec)


@router.get("/audio/recordings", response_model=list[RecordingOut])
def list_recordings(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.query(AudioRecording).order_by(desc(AudioRecording.ts)).limit(limit).all()
    idents = {d.recording_id: d for d in db.query(AcousticDetection)
              .filter(AcousticDetection.model == "identification",
                      AcousticDetection.recording_id.in_([r.id for r in rows])).all()}
    return [_rec_out(r, idents.get(r.id)) for r in rows]


@router.get("/audio/recordings/{recording_id}", response_model=RecordingOut)
def get_recording(recording_id: str, db: Session = Depends(get_db)):
    r = db.get(AudioRecording, recording_id)
    if r is None:
        raise HTTPException(404, "not found")
    ident = db.query(AcousticDetection).filter_by(recording_id=r.id, model="identification").first()
    return _rec_out(r, ident)


@router.delete("/audio/recordings/{recording_id}", status_code=204)
def delete_recording(recording_id: str, db: Session = Depends(get_db)):
    try:
        AudioService(db).delete(recording_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/audio/recordings/{recording_id}/analyze")
def analyze(recording_id: str, db: Session = Depends(get_db)):
    try:
        identification = AudioService(db).analyze(recording_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    dets = db.query(AcousticDetection).filter_by(recording_id=recording_id).all()
    return {"identification": identification, "detections": [_det_out(d) for d in dets]}


@router.get("/audio/recordings/{recording_id}/detections", response_model=list[DetectionOut])
def detections(recording_id: str, db: Session = Depends(get_db)):
    return [_det_out(d) for d in db.query(AcousticDetection).filter_by(recording_id=recording_id).all()]


@router.get("/audio/recordings/{recording_id}/waveform")
def waveform(recording_id: str, db: Session = Depends(get_db)):
    try:
        return AudioService(db).waveform(recording_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/audio/recordings/{recording_id}/spectrum")
def spectrum(recording_id: str, db: Session = Depends(get_db)):
    try:
        return AudioService(db).spectrum(recording_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/audio/recordings/{recording_id}/spectrogram.png")
def spectrogram(recording_id: str, db: Session = Depends(get_db)):
    try:
        png = AudioService(db).spectrogram_png(recording_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.get("/audio/recordings/{recording_id}/file")
def audio_file(recording_id: str, db: Session = Depends(get_db)):
    try:
        data = AudioService(db).audio_bytes(recording_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return Response(content=data, media_type="audio/wav")


# ---------------- labels / dataset ----------------
@router.post("/audio/recordings/{recording_id}/labels", response_model=LabelOut, status_code=201)
def add_label(recording_id: str, payload: LabelIn, db: Session = Depends(get_db)):
    try:
        row = AudioService(db).add_label(recording_id, payload.label, payload.start_s,
                                         payload.end_s, payload.labeler, payload.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _label_out(row)


@router.get("/audio/recordings/{recording_id}/labels", response_model=list[LabelOut])
def list_labels(recording_id: str, db: Session = Depends(get_db)):
    return [_label_out(r) for r in db.query(AcousticLabel).filter_by(recording_id=recording_id).all()]


@router.delete("/audio/labels/{label_id}", status_code=204)
def delete_label(label_id: str, db: Session = Depends(get_db)):
    try:
        AudioService(db).delete_label(label_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/audio/labels/summary")
def label_summary(db: Session = Depends(get_db)):
    return AudioService(db).label_summary()


@router.get("/audio/export/dataset.csv", response_class=PlainTextResponse)
def export_csv(db: Session = Depends(get_db)):
    return PlainTextResponse(AudioService(db).export_dataset_csv(),
                             headers={"Content-Disposition": "attachment; filename=agroai_acoustic_dataset.csv"})


# ---------------- farm model registry ----------------
class TrainIn(BaseModel):
    notes: str | None = None


@router.get("/ml/models", response_model=list[ModelOut])
def list_models(db: Session = Depends(get_db)):
    return [_model_out(m) for m in db.query(MLModel).order_by(desc(MLModel.created_at)).all()]


@router.post("/ml/models/train", response_model=ModelOut, status_code=201)
def train_model(payload: TrainIn, db: Session = Depends(get_db)):
    try:
        row = AudioService(db).train_custom_model(payload.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _model_out(row)


@router.post("/ml/models/{model_id}/activate", response_model=ModelOut)
def activate_model(model_id: str, db: Session = Depends(get_db)):
    try:
        return _model_out(AudioService(db).activate_model(model_id))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(409, str(e))


@router.post("/ml/models/{model_id}/deactivate", response_model=ModelOut)
def deactivate_model(model_id: str, db: Session = Depends(get_db)):
    try:
        return _model_out(AudioService(db).deactivate_model(model_id))
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---------------- synthetic samples ----------------
class GenerateIn(BaseModel):
    profile: str = "underground"
    duration_s: float = 4.0
    seed: int | None = None


PROFILES = {
    "underground": "Sottosuolo: colpi sordi ripetuti (60–120 Hz) nel silenzio, come un animale che scava",
    "bird": "Uccello: cinguettii che salgono di tono, ripetuti ogni mezzo secondo circa",
    "cricket": "Grillo: trillo acuto e pulsante intorno ai 4,5 kHz",
    "machinery": "Macchinario: ronzio di motore a bassa frequenza",
    "irrigation": "Irrigazione: fruscio d'acqua con gorgoglii",
    "tone": "Tono puro 440 Hz (per prova)",
    "noise": "Rumore di fondo (fruscio)",
}
PROFILE_IT = {"underground": "sottosuolo", "bird": "uccello", "cricket": "grillo", "machinery": "macchinario",
              "irrigation": "irrigazione", "tone": "tono di prova", "noise": "rumore di fondo"}


def _synth(profile: str, duration_s: float, seed: int | None, sr: int = 16000) -> bytes:
    duration_s = max(1.0, min(15.0, duration_s))
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    x = (0.01 * rng.standard_normal(n)).astype(np.float32)

    if profile == "tone":
        x = 0.4 * np.sin(2 * math.pi * 440.0 * t)
    elif profile == "noise":
        x = 0.3 * rng.standard_normal(n)
    elif profile == "bird":
        period = rng.uniform(0.5, 0.8)
        f0, f1 = rng.uniform(2200, 2800), rng.uniform(4800, 5800)
        k = int(0.22 * sr)
        for start in np.arange(0.1, duration_s - 0.3, period):
            i = int(start * sr)
            m = min(k, n - i)
            tt = np.arange(m) / sr
            phase = 2 * math.pi * (f0 * tt + 0.5 * (f1 - f0) / (k / sr) * tt * tt)
            x[i:i + m] += 0.6 * np.hanning(m) * np.sin(phase)
    elif profile == "cricket":
        fc = rng.uniform(4200, 4800)
        carrier = np.sin(2 * math.pi * fc * t)
        gate = (np.sin(2 * math.pi * rng.uniform(25, 35) * t) > 0.3).astype(np.float32)
        chirp_env = (np.sin(2 * math.pi * 0.8 * t) > -0.2).astype(np.float32)
        x += 0.4 * carrier * gate * chirp_env
    elif profile == "machinery":
        f0 = rng.uniform(35, 45)
        for h in range(1, 8):
            x += (0.25 / h) * np.sin(2 * math.pi * f0 * h * t + rng.uniform(0, 6.28))
        x *= 1 + 0.1 * np.sin(2 * math.pi * 2.0 * t)
    elif profile == "irrigation":
        # Water spray: falling water has a "pink" spectrum (more energy in the lows than white hiss);
        # the level rises and falls slowly as a rotating sprinkler sweeps past the microphone.
        from scipy.signal import butter, sosfilt
        f = np.fft.rfftfreq(n, 1 / sr)
        pink = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(f, 50.0)), n)
        spray = sosfilt(butter(4, [300, 7500], btype="band", fs=sr, output="sos"), pink)
        sweep = 0.7 + 0.3 * np.sin(2 * math.pi * t / rng.uniform(2.5, 3.5)) ** 2
        x = spray * sweep
        x /= (np.abs(x).max() or 1) / 0.8
    else:  # underground
        period = rng.uniform(0.5, 0.9)
        k = int(rng.uniform(0.08, 0.14) * sr)
        f = rng.uniform(60, 120)
        for start in np.arange(0.2, duration_s - 0.2, period):
            i = int((start + rng.uniform(-0.03, 0.03)) * sr)
            m = min(k, n - i)
            x[i:i + m] += rng.uniform(0.5, 0.8) * np.hanning(m) * np.sin(2 * math.pi * f * np.arange(m) / sr)

    x = np.clip(x, -1, 1).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, x, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@router.get("/audio/sample-profiles")
def sample_profiles():
    return [{"name": k, "description": v} for k, v in PROFILES.items()]


@router.post("/audio/generate-sample", response_model=RecordingOut, status_code=201)
def generate_sample(payload: GenerateIn, db: Session = Depends(get_db)):
    if payload.profile not in PROFILES:
        raise HTTPException(400, "Suono di prova sconosciuto.")
    wav = _synth(payload.profile, payload.duration_s, payload.seed)
    rec = AudioService(db).save(wav, zone_id=None, device_id=None, source="simulation",
                                notes=f"Suono di prova: {PROFILE_IT[payload.profile]} ({payload.duration_s:g} s)")
    return _rec_out(rec)
