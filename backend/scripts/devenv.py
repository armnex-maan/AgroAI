"""Shared dev-mode environment defaults (SQLite + local media)."""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent


def apply() -> None:
    os.chdir(BACKEND)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{(ROOT / 'agroai-dev.db').as_posix()}")
    os.environ.setdefault("MEDIA_ROOT", str(BACKEND / "media"))
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    os.environ.setdefault("DEVICE_HMAC_SECRET", "dev-device-secret")
    os.environ.setdefault("SIMULATION_INTERVAL_SECONDS", "5")
    os.environ.setdefault("TFHUB_CACHE_DIR", str(BACKEND / "media" / "models" / "tfhub"))
