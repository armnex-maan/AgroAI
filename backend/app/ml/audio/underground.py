"""Experimental underground-activity analysis.

Returns pattern evidence, NEVER a species label. It extracts:
- bandpass energy in the 20-400 Hz window where ground vibrations dominate
- onset detection via rectified envelope
- periodicity via autocorrelation of the envelope
- repetition count

Output categories:
- repetitive_low_freq_pattern  — periodic bursts above noise floor
- transient_low_freq           — one-off burst, insufficient evidence
- noise                        — energy present but no structure
- unknown                      — signal quality too low to decide
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt, find_peaks


def _bandpass(data: np.ndarray, sr: int, low: float, high: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2
    low_n = max(1e-4, low / nyq)
    high_n = min(0.9999, high / nyq)
    if high_n <= low_n:
        return data
    sos = butter(order, [low_n, high_n], btype="band", output="sos")
    return sosfiltfilt(sos, data).astype(np.float32)


def _envelope(data: np.ndarray, sr: int, win_ms: float = 25.0) -> tuple[np.ndarray, int]:
    win = max(1, int(sr * win_ms / 1000.0))
    rect = np.abs(data)
    kernel = np.ones(win, dtype=np.float32) / win
    env = np.convolve(rect, kernel, mode="same")
    return env, win


def _autocorr_periodicity(env: np.ndarray, sr: int,
                          min_period_s: float = 0.2,
                          max_period_s: float = 3.0) -> dict:
    if len(env) < sr:
        return {"period_s": None, "strength": 0.0}
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    ac /= (ac[0] + 1e-9)
    lo = int(min_period_s * sr)
    hi = min(len(ac) - 1, int(max_period_s * sr))
    if hi <= lo + 10:
        return {"period_s": None, "strength": 0.0}
    window = ac[lo:hi]
    peak_rel = int(np.argmax(window))
    peak_val = float(window[peak_rel])
    period_s = (lo + peak_rel) / sr
    return {"period_s": round(period_s, 3), "strength": round(peak_val, 3)}


def analyze(data: np.ndarray, sr: int) -> dict:
    """Return the detection dict for the experimental module."""
    if len(data) < sr * 0.5:
        return {
            "category": "unknown",
            "confidence": 0.0,
            "signal_quality": 0.0,
            "evidence": {"reason": "registrazione più corta di mezzo secondo"},
        }

    band = _bandpass(data, sr, 20.0, 400.0)
    band_energy = float(np.mean(band ** 2))
    rest_energy = float(np.mean(data ** 2) - band_energy)
    energy_ratio = band_energy / max(rest_energy, 1e-9)

    env, _ = _envelope(band, sr)
    median_env = float(np.median(env)) or 1e-9
    threshold = median_env * 4.0
    peaks, _ = find_peaks(env, height=threshold, distance=int(0.2 * sr))
    repetitions = int(len(peaks))

    periodicity = _autocorr_periodicity(env, sr)

    # signal quality: ratio of low-band energy to broadband energy, clipped
    signal_quality = min(1.0, energy_ratio / 2.0)

    evidence = {
        "band_hz": [20, 400],
        "band_energy": round(band_energy, 6),
        "band_vs_rest_ratio": round(energy_ratio, 3),
        "envelope_peaks": repetitions,
        "periodicity": periodicity,
        "note": "indica solo un andamento ripetuto, non riconosce la specie dell'animale",
    }

    if signal_quality < 0.1:
        return {"category": "unknown", "confidence": 0.0,
                "signal_quality": round(signal_quality, 3), "evidence": evidence}

    if repetitions >= 4 and periodicity["strength"] >= 0.25:
        confidence = min(0.9, 0.3 + 0.1 * repetitions + periodicity["strength"] * 0.5)
        return {"category": "repetitive_low_freq_pattern",
                "confidence": round(float(confidence), 3),
                "signal_quality": round(signal_quality, 3),
                "evidence": evidence}

    if repetitions >= 1:
        return {"category": "transient_low_freq",
                "confidence": round(0.2 + 0.05 * repetitions, 3),
                "signal_quality": round(signal_quality, 3),
                "evidence": evidence}

    return {"category": "noise", "confidence": 0.1,
            "signal_quality": round(signal_quality, 3), "evidence": evidence}
