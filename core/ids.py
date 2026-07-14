from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_id(prefix: str, payload: object, length: int = 12) -> str:
    return f"{prefix}-{stable_hash(payload)[:length].upper()}"

