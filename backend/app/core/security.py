import hmac
import hashlib
import time
from fastapi import Header, HTTPException, status

from app.config import settings

MAX_CLOCK_SKEW_SECONDS = 300


def compute_hmac(body: bytes, timestamp: str, secret: str | None = None) -> str:
    key = (secret or settings.device_hmac_secret).encode()
    msg = timestamp.encode() + b"." + body
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_device_hmac(
    body: bytes,
    x_agroai_timestamp: str,
    x_agroai_signature: str,
    secret: str | None = None,
) -> None:
    try:
        ts = int(x_agroai_timestamp)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid timestamp") from exc
    now = int(time.time())
    if abs(now - ts) > MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "timestamp skew")
    expected = compute_hmac(body, x_agroai_timestamp, secret)
    if not hmac.compare_digest(expected, x_agroai_signature or ""):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")


async def device_auth_dependency(
    x_agroai_timestamp: str = Header(default=""),
    x_agroai_signature: str = Header(default=""),
    x_agroai_source: str = Header(default="device"),
) -> dict:
    return {
        "timestamp": x_agroai_timestamp,
        "signature": x_agroai_signature,
        "source": x_agroai_source,
    }
