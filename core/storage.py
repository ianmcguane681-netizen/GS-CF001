from __future__ import annotations

import json
from core.ids import stable_hash
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ids import utc_now


def run_timestamp() -> str:
    """Filesystem-safe UTC timestamp, shared across every artifact of one run.

    Generating this once per pipeline run (rather than once per artifact)
    guarantees all files produced by the same run carry the same stamp, so a
    run's artifacts can be found and grouped by that stamp alone. Includes
    microseconds (unlike core.ids.utc_now, which is second-resolution and
    used for human-facing timestamps) so that two runs started within the
    same second -- e.g. back-to-back pipeline invocations in tests or rapid
    manual reruns -- still get distinct filenames and never collide.
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "Z"


def write_json_artifact(payload: Any, directory: str | Path, prefix: str, timestamp: str | None = None) -> str:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or run_timestamp()
    path = output_dir / f"{prefix}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)


def file_checksum(path: str | Path) -> str:
    target = Path(path)
    if not target.exists():
        return ""
    return stable_hash(target.read_text(encoding="utf-8", errors="ignore"))
