"""Core DSP: load, FFT, dominant frequencies, SNR, spectrogram image."""
from __future__ import annotations

import io
import threading

import numpy as np
import soundfile as sf
from scipy.signal import spectrogram as sp_spectrogram, welch, find_peaks


TARGET_SR = 16000
_MPL_LOCK = threading.Lock()


def load_mono(path: str) -> tuple[np.ndarray, int]:
    data, sr = sf.read(path, always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), int(sr)


def resample(data: np.ndarray, sr: int, target: int = TARGET_SR) -> tuple[np.ndarray, int]:
    if sr == target:
        return data, sr
    # Simple linear resample — fine for feature extraction, not for playback quality.
    n_out = int(round(len(data) * target / sr))
    x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False, dtype=np.float32)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False, dtype=np.float32)
    return np.interp(x_new, x_old, data).astype(np.float32), target


def dominant_frequencies(data: np.ndarray, sr: int, top_k: int = 5,
                         fmin: float = 20.0, fmax: float | None = None) -> list[dict]:
    if fmax is None:
        fmax = sr / 2
    n = min(len(data), 1 << 16)
    seg = data[:n] * np.hanning(n)
    spectrum = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, d=1 / sr)
    mask = (freqs >= fmin) & (freqs <= fmax)
    spectrum = spectrum[mask]
    freqs = freqs[mask]
    if spectrum.size == 0:
        return []
    # distinct peaks: at least ~1/6 octave apart, so one broad peak is not listed several times
    bin_hz = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    peaks, _ = find_peaks(spectrum, distance=max(1, int(30.0 / bin_hz)))
    peaks = [p for p in peaks if not any(abs(freqs[p] - freqs[q]) < freqs[q] * 0.12
                                         for q in peaks if spectrum[q] > spectrum[p])]
    if not peaks:
        peaks = [int(np.argmax(spectrum))]
    idx = sorted(peaks, key=lambda i: spectrum[i], reverse=True)[:top_k]
    peak = float(spectrum[idx[0]]) or 1e-9
    return [
        {"frequency_hz": round(float(freqs[i]), 2),
         "magnitude": round(float(spectrum[i]), 4),
         "relative": round(float(spectrum[i] / peak), 4)}
        for i in idx
    ]


BANDS = [
    ("Bassissime 20–200 Hz (vibrazioni del terreno, motori)", 20, 200),
    ("Basse 200–1000 Hz (voci, animali grandi)", 200, 1000),
    ("Medie 1–2 kHz", 1000, 2000),
    ("Medio-alte 2–4 kHz (molti canti di uccelli)", 2000, 4000),
    ("Alte 4–8 kHz (insetti, richiami acuti)", 4000, 8000),
]


def band_energy(data: np.ndarray, sr: int) -> list[dict]:
    f, pxx = welch(data, fs=sr, nperseg=min(2048, len(data)))
    total = float(pxx.sum()) or 1e-12
    return [{"band": name, "fraction": round(float(pxx[(f >= lo) & (f < hi)].sum() / total), 4)}
            for name, lo, hi in BANDS]


def spectrum_curve(data: np.ndarray, sr: int, points: int = 240) -> dict:
    """Welch PSD resampled on a log frequency axis, for the FFT chart."""
    f, pxx = welch(data, fs=sr, nperseg=min(4096, len(data)))
    db = 10.0 * np.log10(pxx + 1e-14)
    grid = np.geomspace(20.0, sr / 2, points)
    vals = np.interp(grid, f, db)
    return {"freqs": [round(float(x), 1) for x in grid], "db": [round(float(v), 2) for v in vals]}


def snr_estimate_db(data: np.ndarray) -> float:
    """Rough SNR: peak magnitude vs. median magnitude of the spectrum."""
    if data.size == 0:
        return 0.0
    spec = np.abs(np.fft.rfft(data * np.hanning(len(data))))
    med = float(np.median(spec)) or 1e-9
    peak = float(spec.max()) or 1e-9
    return round(20.0 * float(np.log10(peak / med)), 2)


def spectrogram_png(data: np.ndarray, sr: int) -> bytes:
    """Render a log-magnitude spectrogram as a small PNG using matplotlib.
    Returns PNG bytes. pyplot is not thread-safe, so rendering is serialised."""
    with _MPL_LOCK:
        return _spectrogram_png(data, sr)


def _spectrogram_png(data: np.ndarray, sr: int) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f, t, Sxx = sp_spectrogram(data, fs=sr, nperseg=1024, noverlap=512, scaling="spectrum")
    Sxx_db = 10.0 * np.log10(Sxx + 1e-10)

    fig, ax = plt.subplots(figsize=(8, 3), dpi=110)
    ax.pcolormesh(t, f, Sxx_db, shading="auto", cmap="magma")
    ax.set_ylabel("Hz")
    ax.set_xlabel("s")
    ax.set_facecolor("#0a1410")
    fig.patch.set_facecolor("#0a1410")
    ax.tick_params(colors="#93a99b")
    for s in ax.spines.values():
        s.set_color("#1d3a2d")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def waveform_downsample(data: np.ndarray, buckets: int = 1000) -> list[float]:
    """Produce min/max pairs per bucket so the frontend can draw a waveform
    without transferring the whole file."""
    if len(data) == 0:
        return []
    bucket_size = max(1, len(data) // buckets)
    truncated = data[: bucket_size * buckets]
    reshaped = truncated.reshape(-1, bucket_size)
    peak = float(np.max(np.abs(reshaped))) or 1e-9
    out: list[float] = []
    for row in reshaped:
        out.append(round(float(row.min() / peak), 4))
        out.append(round(float(row.max() / peak), 4))
    return out
