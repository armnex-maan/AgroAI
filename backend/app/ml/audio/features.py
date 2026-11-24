"""Fixed-length acoustic feature vector for the trainable classifier.

Bump FEATURE_VERSION whenever the vector layout changes: models trained on an
older version are refused at prediction time.
"""
from __future__ import annotations

import numpy as np
import librosa

FEATURE_VERSION = "f1"
SR = 16000
N_MFCC = 20


PERCH_FEATURE_VERSION = "perch2-emb"


def best(y: np.ndarray, sr: int = SR) -> tuple[np.ndarray, str]:
    """Perch 2.0 embedding when available (far better for learning from few examples),
    otherwise the hand-made MFCC vector."""
    from app.config import settings
    if settings.perch_enabled:
        from app.ml.audio import perch
        emb = perch.embed(y, sr)
        if emb is not None:
            return emb.astype(np.float32), PERCH_FEATURE_VERSION
    return extract(y, sr), FEATURE_VERSION


def for_version(y: np.ndarray, sr: int, version: str) -> np.ndarray | None:
    if version == PERCH_FEATURE_VERSION:
        from app.ml.audio import perch
        emb = perch.embed(y, sr)
        return None if emb is None else emb.astype(np.float32)
    return extract(y, sr)


def feature_names() -> list[str]:
    names = [f"mfcc{i}_mean" for i in range(N_MFCC)]
    names += [f"mfcc{i}_std" for i in range(N_MFCC)]
    names += [f"dmfcc{i}_absmean" for i in range(N_MFCC)]
    for k in ("centroid", "bandwidth", "rolloff", "flatness", "zcr"):
        names += [f"{k}_mean", f"{k}_std"]
    names += ["rms_mean", "rms_std", "rms_peak_ratio", "onset_rate", "low_band_ratio"]
    return names


def extract(y: np.ndarray, sr: int = SR) -> np.ndarray:
    if sr != SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=SR)
    min_len = SR // 2
    if len(y) < min_len:
        y = np.pad(y, (0, min_len - len(y)))
    y = y.astype(np.float32)
    peak = float(np.max(np.abs(y))) or 1e-9
    y = y / peak  # loudness depends on mic distance, not on the animal

    hop, nfft = 256, 1024
    mfcc = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=N_MFCC, n_fft=nfft, hop_length=hop, fmin=20)
    dmfcc = librosa.feature.delta(mfcc) if mfcc.shape[1] >= 9 else np.zeros_like(mfcc)
    nyq = SR / 2
    centroid = librosa.feature.spectral_centroid(y=y, sr=SR, n_fft=nfft, hop_length=hop)[0] / nyq
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=SR, n_fft=nfft, hop_length=hop)[0] / nyq
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=SR, n_fft=nfft, hop_length=hop)[0] / nyq
    flatness = librosa.feature.spectral_flatness(y=y, n_fft=nfft, hop_length=hop)[0]
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=nfft, hop_length=hop)[0]
    rms = librosa.feature.rms(y=y, frame_length=nfft, hop_length=hop)[0]
    onsets = librosa.onset.onset_detect(y=y, sr=SR, hop_length=hop)
    duration = len(y) / SR

    spec = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    freqs = np.fft.rfftfreq(len(y), 1 / SR)
    low_band_ratio = float(spec[freqs < 400].sum() / (spec.sum() + 1e-12))

    vec = np.concatenate([
        mfcc.mean(axis=1), mfcc.std(axis=1), np.abs(dmfcc).mean(axis=1),
        [centroid.mean(), centroid.std(), bandwidth.mean(), bandwidth.std(),
         rolloff.mean(), rolloff.std(), flatness.mean(), flatness.std(),
         zcr.mean(), zcr.std()],
        [rms.mean(), rms.std(), float(rms.max() / (rms.mean() + 1e-9)),
         len(onsets) / duration, low_band_ratio],
    ]).astype(np.float32)
    return np.nan_to_num(vec)
