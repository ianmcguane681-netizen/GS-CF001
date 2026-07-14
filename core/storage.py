from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.ids import utc_now


def write_json_artifact(payload: Any, directory: str | Path, prefix: str) -> str:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "").replace("-", "")
    path = output_dir / f"{prefix}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)

