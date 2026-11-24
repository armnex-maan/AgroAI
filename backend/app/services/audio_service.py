"""Audio ingest + full acoustic analysis pipeline."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AudioRecording, AcousticDetection, AcousticLabel, Zone, Field, Farm, MLModel
from app.ml.audio import signal as dsp
from app.ml.audio import underground, yamnet, birdnet, features, identification, perch, species, taxonomy
from app.ml.audio import custom_classifier


def audio_dir() -> Path:
    p = settings.media_path / "audio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def models_dir() -> Path:
    p = settings.media_path / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


class AudioService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- storage ----------
    def save(self, content: bytes, zone_id: str | None, device_id: str | None,
             source: str, notes: str | None) -> AudioRecording:
        rec_id = str(uuid.uuid4())
        path = audio_dir() / f"{rec_id}.wav"
        path.write_bytes(content)
        try:
            data, sr = dsp.load_mono(str(path))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        rec = AudioRecording(
            id=rec_id, zone_id=zone_id, device_id=device_id, ts=datetime.now(timezone.utc),
            duration_s=round(len(data) / sr, 3), sample_rate=sr, channels=1,
            path=str(path), source=source, status="pending", notes=notes,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def _location(self, rec: AudioRecording) -> tuple[float | None, float | None]:
        farm = None
        if rec.zone_id:
            zone = self.db.get(Zone, rec.zone_id)
            field = self.db.get(Field, zone.field_id) if zone else None
            farm = self.db.get(Farm, field.farm_id) if field else None
        if farm is None:
            farm = self.db.query(Farm).first()
        return (farm.latitude, farm.longitude) if farm else (None, None)

    def active_model(self) -> MLModel | None:
        return (self.db.query(MLModel)
                .filter(MLModel.kind == "acoustic_custom", MLModel.status == "active")
                .first())

    # ---------- analysis ----------
    def analyze(self, recording_id: str) -> dict:
        rec = self.db.get(AudioRecording, recording_id)
        if rec is None:
            raise ValueError("recording not found")
        data, sr = dsp.load_mono(rec.path)
        y16, sr16 = dsp.resample(data, sr, dsp.TARGET_SR)
        now = datetime.now(timezone.utc)

        self.db.query(AcousticDetection).filter_by(recording_id=rec.id).delete()

        spectral = {"dominant_frequencies": dsp.dominant_frequencies(y16, sr16, top_k=6),
                    "snr_db": dsp.snr_estimate_db(y16),
                    "band_energy": dsp.band_energy(y16, sr16)}
        ug = underground.analyze(y16, sr16)

        yam = yamnet.analyze(y16) if settings.yamnet_enabled else {"available": False, "error": "disabled"}

        bird = None
        if settings.birdnet_enabled:
            bird_group = next((g for g in yam.get("groups", []) if g["group"] == "bird"), None)
            if not yam.get("available") or (bird_group and bird_group["score"] >= settings.identification_possible):
                lat, lon = self._location(rec)
                bird = birdnet.analyze(rec.path, lat, lon, rec.ts)

        perch_res, sp_ok, sp_rejected, gate = None, [], [], {}
        if settings.perch_enabled:
            lat, lon = self._location(rec)
            local = None
            if settings.species_location_filter and lat is not None:
                local = taxonomy.local_species(lat, lon)
            perch_res = perch.analyze(data, sr, allowed=set(local) if local else None)
            sp_ok, sp_rejected, gate = species.candidates(perch_res, yam, local,
                                                          settings.identification_probable,
                                                          settings.identification_possible)
            perch_res["gate"] = gate
            perch_res["local_species"] = len(local) if local else None

        custom = None
        model_row = self.active_model()
        if model_row is not None:
            bundle = custom_classifier.load(model_row.path)
            vec = features.for_version(y16, sr16, model_row.feature_version)
            if vec is None:
                custom = {"label": "unknown", "confidence": 0.0,
                          "reason": "il modello della tua azienda richiede Perch, che ora non è disponibile"}
            else:
                custom = custom_classifier.predict(bundle, vec, model_row.feature_version,
                                                   settings.custom_model_min_confidence)
            custom["version"] = model_row.version

        perch_info = None
        if perch_res is not None:
            perch_info = {"available": perch_res.get("available", False),
                          "local_filter": perch_res.get("local_filter", False),
                          "local_species": perch_res.get("local_species"),
                          "excluded_not_local": perch_res.get("excluded_not_local", 0)}
        fused = identification.fuse(yam, bird, custom, ug,
                                    settings.identification_probable,
                                    settings.identification_possible,
                                    species=sp_ok, rejected=sp_rejected, perch_info=perch_info)

        rows = [
            AcousticDetection(model="identification", model_version="fusion-v1",
                              category=fused["verdict"],
                              confidence=max([c["score"] for c in fused["candidates"]], default=0.0),
                              signal_quality=min(1.0, max(0.0, spectral["snr_db"] / 40.0)),
                              evidence=fused),
            AcousticDetection(model="spectral", model_version="v1", category="spectral_summary",
                              confidence=1.0, signal_quality=min(1.0, max(0.0, spectral["snr_db"] / 40.0)),
                              evidence=spectral),
            AcousticDetection(model="underground-experimental", model_version="v1",
                              category=ug["category"], confidence=ug["confidence"],
                              signal_quality=ug["signal_quality"], evidence=ug["evidence"]),
        ]
        if yam.get("available"):
            top = yam["groups"][0] if yam["groups"] else {"group": "none", "score": 0.0}
            rows.append(AcousticDetection(model="yamnet", model_version="1", category=top["group"],
                                          confidence=top["score"], signal_quality=0.0, evidence=yam))
        else:
            rows.append(AcousticDetection(model="yamnet", model_version="unavailable", category="unavailable",
                                          confidence=0.0, signal_quality=0.0, evidence=yam))
        if perch_res is not None:
            top_s = sp_ok[0] if sp_ok else None
            rows.append(AcousticDetection(model="perch", model_version="2.0",
                                          category=top_s["scientific_name"] if top_s else
                                          ("unavailable" if not perch_res.get("available") else "no_species"),
                                          confidence=top_s["score"] if top_s else 0.0, signal_quality=0.0,
                                          evidence=perch_res))
        if bird is not None:
            top_b = bird.get("detections", [{}])[0] if bird.get("detections") else {}
            rows.append(AcousticDetection(model="birdnet", model_version="birdnetlib",
                                          category=top_b.get("scientific_name") or "no_detection",
                                          confidence=top_b.get("confidence", 0.0), signal_quality=0.0,
                                          evidence=bird))
        if custom is not None:
            rows.append(AcousticDetection(model="farm-model", model_version=f"v{custom['version']}",
                                          category=custom["label"], confidence=custom["confidence"],
                                          signal_quality=0.0, evidence=custom))
        for r in rows:
            r.recording_id = rec.id
            r.ts = now
            self.db.add(r)
        rec.status = "processed"
        self.db.commit()
        heard = [s["scientific_name"] for s in sp_ok if s.get("scientific_name")]
        if bird is not None:
            heard += [d["scientific_name"] for d in bird.get("detections", []) if d.get("scientific_name")]
        if heard:
            from app.services import deterrent_service
            fired = deterrent_service.on_detection(self.db, heard, rec.zone_id)
            if fired:
                fused["deterrents_triggered"] = fired
        return fused

    def waveform(self, recording_id: str, buckets: int = 800) -> dict:
        rec = self._get(recording_id)
        data, sr = dsp.load_mono(rec.path)
        return {"duration_s": rec.duration_s, "sample_rate": sr,
                "min_max": dsp.waveform_downsample(data, buckets)}

    def spectrum(self, recording_id: str) -> dict:
        rec = self._get(recording_id)
        data, sr = dsp.load_mono(rec.path)
        y16, sr16 = dsp.resample(data, sr, dsp.TARGET_SR)
        return dsp.spectrum_curve(y16, sr16)

    def spectrogram_png(self, recording_id: str) -> bytes:
        rec = self._get(recording_id)
        data, sr = dsp.load_mono(rec.path)
        y16, sr16 = dsp.resample(data, sr, dsp.TARGET_SR)
        return dsp.spectrogram_png(y16, sr16)

    def audio_bytes(self, recording_id: str) -> bytes:
        return Path(self._get(recording_id).path).read_bytes()

    def _get(self, recording_id: str) -> AudioRecording:
        rec = self.db.get(AudioRecording, recording_id)
        if rec is None:
            raise ValueError("not found")
        return rec

    def delete(self, recording_id: str) -> None:
        rec = self._get(recording_id)
        Path(rec.path).unlink(missing_ok=True)
        self.db.delete(rec)
        self.db.commit()

    # ---------- labels / dataset ----------
    def add_label(self, recording_id: str, label: str, start_s: float,
                  end_s: float | None, labeler: str, notes: str | None) -> AcousticLabel:
        rec = self._get(recording_id)
        label = label.strip().lower()
        if not label:
            raise ValueError("Scrivi un nome per l'etichetta.")
        end = rec.duration_s if end_s is None else min(end_s, rec.duration_s)
        if end <= start_s:
            raise ValueError("La fine del pezzo deve venire dopo l'inizio.")
        row = AcousticLabel(recording_id=rec.id, start_s=max(0.0, start_s), end_s=end,
                            label=label, labeler=labeler, notes=notes,
                            created_at=datetime.now(timezone.utc))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_label(self, label_id: str) -> None:
        row = self.db.get(AcousticLabel, label_id)
        if row is None:
            raise ValueError("not found")
        self.db.delete(row)
        self.db.commit()

    def label_summary(self) -> dict:
        counts: dict[str, dict] = {}
        for lbl, rec in (self.db.query(AcousticLabel, AudioRecording)
                         .join(AudioRecording, AcousticLabel.recording_id == AudioRecording.id).all()):
            c = counts.setdefault(lbl.label, {"label": lbl.label, "count": 0, "simulated": 0, "recordings": set()})
            c["count"] += 1
            c["simulated"] += int(rec.source == "simulation")
            c["recordings"].add(rec.id)
        out = []
        for c in counts.values():
            c["recordings"] = len(c["recordings"])
            out.append(c)
        return {"labels": sorted(out, key=lambda c: -c["count"]),
                "min_per_class_train": custom_classifier.MIN_PER_CLASS_TRAIN,
                "min_per_class_activate": custom_classifier.MIN_PER_CLASS_ACTIVATE}

    def export_dataset_csv(self) -> str:
        lines = ["label_id,recording_id,path,sample_rate,duration_s,source,label,start_s,end_s,labeler"]
        q = (self.db.query(AcousticLabel, AudioRecording)
             .join(AudioRecording, AcousticLabel.recording_id == AudioRecording.id)
             .order_by(AcousticLabel.created_at))
        for lbl, r in q.all():
            lines.append(f"{lbl.id},{r.id},{Path(r.path).name},{r.sample_rate},{r.duration_s},{r.source},"
                         f"{lbl.label},{lbl.start_s},{lbl.end_s if lbl.end_s is not None else r.duration_s},"
                         f"{lbl.labeler}")
        return "\n".join(lines) + "\n"

    # ---------- training (manual, versioned) ----------
    def train_custom_model(self, notes: str | None = None) -> MLModel:
        q = (self.db.query(AcousticLabel, AudioRecording)
             .join(AudioRecording, AcousticLabel.recording_id == AudioRecording.id))
        X, y, manifest = [], [], []
        versions: set[str] = set()
        cache: dict[str, tuple[np.ndarray, int]] = {}
        for lbl, rec in q.all():
            if rec.id not in cache:
                d, s = dsp.load_mono(rec.path)
                cache[rec.id] = dsp.resample(d, s, dsp.TARGET_SR)
            y16, sr16 = cache[rec.id]
            a = int(lbl.start_s * sr16)
            b = int((lbl.end_s if lbl.end_s is not None else rec.duration_s) * sr16)
            seg = y16[a:b]
            if len(seg) < sr16 * 0.2:
                continue
            vec, ver = features.best(seg, sr16)
            X.append(vec)
            versions.add(ver)
            y.append(lbl.label)
            manifest.append({"label_id": lbl.id, "recording_id": rec.id, "label": lbl.label,
                             "start_s": lbl.start_s, "end_s": lbl.end_s, "source": rec.source})
        if not X:
            raise ValueError("Non ci sono ancora registrazioni etichettate su cui allenare il modello.")

        if len(versions) != 1:  # Perch became unavailable mid-run: never mix feature spaces
            raise ValueError("Il modello di riconoscimento non è disponibile in questo momento. Riprova.")
        feature_version = versions.pop()
        result = custom_classifier.train(np.vstack(X), y, feature_version)
        result.metrics["contains_simulated_data"] = any(m["source"] == "simulation" for m in manifest)
        version = (max([m.version for m in self.db.query(MLModel).filter_by(kind="acoustic_custom").all()],
                       default=0) + 1)
        path = models_dir() / f"acoustic_custom_v{version}.joblib"
        custom_classifier.save(result.bundle, str(path))
        row = MLModel(kind="acoustic_custom", version=version, feature_version=feature_version,
                      status="trained", labels=result.labels, class_counts=result.class_counts,
                      n_samples=sum(result.class_counts.values()), metrics=result.metrics,
                      dataset_manifest=manifest, path=str(path), notes=notes,
                      created_at=datetime.now(timezone.utc))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def activate_model(self, model_id: str) -> MLModel:
        row = self.db.get(MLModel, model_id)
        if row is None:
            raise ValueError("model not found")
        if not row.metrics.get("can_activate"):
            raise PermissionError(f"Il modello non si può ancora attivare: servono {row.metrics.get('activation_rule')}.")
        for other in self.db.query(MLModel).filter_by(kind=row.kind, status="active").all():
            other.status = "archived"
        row.status = "active"
        self.db.commit()
        self.db.refresh(row)
        return row

    def deactivate_model(self, model_id: str) -> MLModel:
        row = self.db.get(MLModel, model_id)
        if row is None:
            raise ValueError("model not found")
        row.status = "archived"
        self.db.commit()
        self.db.refresh(row)
        return row
