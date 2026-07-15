"""Focused tests for core.run_index append-only semantics and edge cases."""

from __future__ import annotations

import json

import pytest

from core.run_index import append_run_index, build_run_index_entry, read_run_index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(run_id: str, n: int = 1) -> dict:
    return build_run_index_entry(
        run_id=run_id,
        timestamp=f"20260714T0000{n:02d}000000Z",
        study_id="GS-CF001-C",
        verdict="CONTINUE RESEARCH",
        evidence_ceiling="CONTINUE RESEARCH",
        source_access_method="official_cfpb_search_api",
        artifact_paths={"report_json": f"/data/exports/report_{n}.json"},
        artifact_checksums={f"/data/exports/report_{n}.json": f"abc{n:03d}"},
    )


# ---------------------------------------------------------------------------
# append_run_index
# ---------------------------------------------------------------------------

def test_first_append_creates_file(tmp_path):
    index_path = tmp_path / "run_index.json"
    assert not index_path.exists()

    append_run_index(_entry("RUN-001"), path=index_path)

    assert index_path.exists()
    data = json.loads(index_path.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["run_id"] == "RUN-001"


def test_second_append_grows_list_preserving_first_entry(tmp_path):
    index_path = tmp_path / "run_index.json"
    append_run_index(_entry("RUN-001", 1), path=index_path)
    append_run_index(_entry("RUN-002", 2), path=index_path)

    data = json.loads(index_path.read_text())
    assert len(data) == 2
    # Order is chronological: first appended is index 0.
    assert data[0]["run_id"] == "RUN-001"
    assert data[1]["run_id"] == "RUN-002"
    # First entry was not modified.
    assert data[0]["artifact_paths"]["report_json"] == "/data/exports/report_1.json"


def test_many_appends_never_lose_entries(tmp_path):
    index_path = tmp_path / "run_index.json"
    for i in range(1, 11):
        append_run_index(_entry(f"RUN-{i:03d}", i), path=index_path)

    data = json.loads(index_path.read_text())
    assert len(data) == 10
    assert [e["run_id"] for e in data] == [f"RUN-{i:03d}" for i in range(1, 11)]


def test_corrupt_file_treated_as_empty_list(tmp_path):
    index_path = tmp_path / "run_index.json"
    index_path.write_text("this is not json", encoding="utf-8")

    # Should not raise; should degrade gracefully.
    append_run_index(_entry("RUN-001"), path=index_path)

    data = json.loads(index_path.read_text())
    assert len(data) == 1
    assert data[0]["run_id"] == "RUN-001"


def test_non_list_json_treated_as_empty(tmp_path):
    index_path = tmp_path / "run_index.json"
    index_path.write_text(json.dumps({"stray": "object"}), encoding="utf-8")

    append_run_index(_entry("RUN-001"), path=index_path)

    data = json.loads(index_path.read_text())
    assert len(data) == 1


def test_missing_parent_directory_is_created(tmp_path):
    index_path = tmp_path / "deep" / "nested" / "run_index.json"
    append_run_index(_entry("RUN-001"), path=index_path)
    assert index_path.exists()


# ---------------------------------------------------------------------------
# read_run_index
# ---------------------------------------------------------------------------

def test_read_returns_empty_list_for_missing_file(tmp_path):
    assert read_run_index(tmp_path / "nonexistent.json") == []


def test_read_returns_empty_list_for_corrupt_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("oops", encoding="utf-8")
    assert read_run_index(bad) == []


def test_read_returns_entries_in_order(tmp_path):
    index_path = tmp_path / "run_index.json"
    for i in range(1, 4):
        append_run_index(_entry(f"RUN-{i:03d}", i), path=index_path)

    entries = read_run_index(index_path)
    assert [e["run_id"] for e in entries] == ["RUN-001", "RUN-002", "RUN-003"]


# ---------------------------------------------------------------------------
# build_run_index_entry field contract
# ---------------------------------------------------------------------------

def test_entry_contains_all_required_fields():
    entry = _entry("RUN-XYZ")
    required = {
        "run_id", "timestamp", "study_id", "verdict",
        "evidence_ceiling", "source_access_method",
        "artifact_paths", "artifact_checksums",
    }
    assert required.issubset(entry.keys())
    assert entry["run_id"] == "RUN-XYZ"
    assert entry["study_id"] == "GS-CF001-C"
    assert entry["verdict"] == "CONTINUE RESEARCH"
    assert entry["evidence_ceiling"] == "CONTINUE RESEARCH"
