"""BirdNET bird-species identification — OPTIONAL module.

License: BirdNET models are CC BY-NC-SA 4.0 (non-commercial). Disabled unless
BIRDNET_ENABLED=true and `birdnetlib` is installed. Location and date are used
by BirdNET to restrict candidates to species plausible for that place/season.
"""
from __future__ import annotations

from datetime import datetime

LICENSE = "BirdNET model: CC BY-NC-SA 4.0 — non-commercial use only"

_analyzer = None
_error: str | None = None


def _load() -> bool:
    global _analyzer, _error
    if _analyzer is not None:
        return True
    if _error is not None:
        return False
    try:
        from birdnetlib.analyzer import Analyzer  # type: ignore
        _analyzer = Analyzer()
        return True
    except Exception as exc:
        _error = f"{type(exc).__name__}: {exc}"
        return False


def status(enabled: bool) -> dict:
    if not enabled:
        return {"available": False, "enabled": False, "license": LICENSE,
                "error": "disabled (set BIRDNET_ENABLED=true and pip install birdnetlib)"}
    ok = _load()
    return {"available": ok, "enabled": True, "license": LICENSE, "error": _error}


def analyze(path: str, lat: float | None, lon: float | None, when: datetime | None,
            min_conf: float = 0.25) -> dict:
    if not _load():
        return {"available": False, "error": _error, "license": LICENSE}
    from birdnetlib import Recording  # type: ignore

    kwargs = {"min_conf": min_conf}
    if lat is not None and lon is not None:
        kwargs.update(lat=lat, lon=lon)
    if when is not None:
        kwargs["date"] = when
    rec = Recording(_analyzer, path, **kwargs)
    rec.analyze()
    dets = sorted(rec.detections, key=lambda d: d["confidence"], reverse=True)
    return {
        "available": True,
        "license": LICENSE,
        "location_filter": lat is not None and lon is not None,
        "detections": [{
            "common_name": d.get("common_name"),
            "scientific_name": d.get("scientific_name"),
            "start_s": d.get("start_time"), "end_s": d.get("end_time"),
            "confidence": round(float(d.get("confidence", 0.0)), 4),
        } for d in dets[:10]],
    }
