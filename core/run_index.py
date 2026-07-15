from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_RUN_INDEX_PATH = "data/exports/run_index.json"


def append_run_index(entry: dict[str, Any], path: str | Path = DEFAULT_RUN_INDEX_PATH) -> str:
    """Append one run's summary to the persistent, append-only run index.

    The index is a single JSON file holding a list of entries, one per
    pipeline run, in chronological order. Existing entries are never
    rewritten or removed by this function -- it only ever reads the current
    list and writes it back with the new entry appended, so a run index
    accumulates the full run history of the study over time.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []
        if not isinstance(existing, list):
            existing = []
    else:
        existing = []
    existing.append(entry)
    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(output_path)


def read_run_index(path: str | Path = DEFAULT_RUN_INDEX_PATH) -> list[dict[str, Any]]:
    index_path = Path(path)
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def build_run_index_entry(
    run_id: str,
    timestamp: str,
    study_id: str,
    verdict: str,
    evidence_ceiling: str,
    source_access_method: str,
    artifact_paths: dict[str, str],
    artifact_checksums: dict[str, str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "study_id": study_id,
        "verdict": verdict,
        "evidence_ceiling": evidence_ceiling,
        "source_access_method": source_access_method,
        "artifact_paths": artifact_paths,
        "artifact_checksums": artifact_checksums,
    }
