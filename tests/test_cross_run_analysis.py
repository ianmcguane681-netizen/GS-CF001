"""Focused tests for core/cross_run_analysis.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.cross_run_analysis import (
    CrossRunComparison,
    compare_runs,
    write_cross_run_report,
    _load_run_snapshot,
)
from core.run_index import build_run_index_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    run_id: str,
    verdict: str = "CONTINUE RESEARCH",
    ceiling: str = "CONTINUE RESEARCH",
    timestamp: str = "20260715T000001000000Z",
    artifact_paths: dict | None = None,
    artifact_checksums: dict | None = None,
) -> dict:
    return build_run_index_entry(
        run_id=run_id,
        timestamp=timestamp,
        study_id="GS-CF001-C",
        verdict=verdict,
        evidence_ceiling=ceiling,
        source_access_method="official_cfpb_search_api",
        artifact_paths=artifact_paths or {},
        artifact_checksums=artifact_checksums or {},
    )


def _write_artifacts(tmp_path: Path, run_id: str, n_candidates: int = 3) -> dict[str, str]:
    """Write minimal artifact files and return an artifact_paths dict."""
    exports = tmp_path / run_id / "exports"
    exports.mkdir(parents=True)
    raw = tmp_path / run_id / "raw"
    raw.mkdir()
    processed = tmp_path / run_id / "processed"
    processed.mkdir()

    candidates = [{"candidate_id": f"CAN-{i:03d}"} for i in range(n_candidates)]
    (exports / "normalised_candidates.json").write_text(
        json.dumps(candidates), encoding="utf-8"
    )

    companies = ["CompA", "CompB"] if n_candidates >= 2 else ["CompA"]
    findings = []
    for i in range(min(2, n_candidates)):
        findings.append({
            "finding_id": f"FND-{i:03d}",
            "mechanism": ["credit_report_dispute_investigation", "incorrect_credit_report_information"][i % 2],
            "companies": companies[:2],
        })
    (exports / "findings.json").write_text(json.dumps(findings), encoding="utf-8")

    opps = [{"opportunity_id": f"OPP-{i:03d}"} for i in range(min(1, n_candidates))]
    (exports / "opportunities.json").write_text(json.dumps(opps), encoding="utf-8")

    gates = [
        {"gate_id": f"PG-{i:02d}", "status": "PASS", "constrains_max_verdict": i == 15}
        for i in range(1, 17)
    ]
    (exports / "proof_gate_results.json").write_text(json.dumps(gates), encoding="utf-8")

    proc = {
        "verified_evidence": [{"evidence_id": f"EVD-{i:03d}"} for i in range(n_candidates)]
    }
    (processed / "gs_cf001_c_processed.json").write_text(
        json.dumps(proc), encoding="utf-8"
    )

    return {
        "normalised_candidates": str(exports / "normalised_candidates.json"),
        "findings": str(exports / "findings.json"),
        "opportunities": str(exports / "opportunities.json"),
        "proof_gate_results": str(exports / "proof_gate_results.json"),
        "processed": str(processed / "gs_cf001_c_processed.json"),
    }


# ---------------------------------------------------------------------------
# _load_run_snapshot
# ---------------------------------------------------------------------------

def test_load_snapshot_reads_artifact_counts(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=3)
    entry = _entry("RUN-001", artifact_paths=paths)
    snap = _load_run_snapshot(entry)
    assert snap.run_id == "RUN-001"
    assert snap.candidate_count == 3
    assert snap.finding_count == 2
    assert snap.opportunity_count == 1
    assert len(snap.mechanisms) >= 1
    assert len(snap.gate_statuses) == 16


def test_load_snapshot_handles_missing_files_gracefully(tmp_path):
    entry = _entry("RUN-EMPTY", artifact_paths={})
    snap = _load_run_snapshot(entry)
    assert snap.candidate_count == 0
    assert snap.finding_count == 0
    assert snap.gate_statuses == {}


# ---------------------------------------------------------------------------
# compare_runs
# ---------------------------------------------------------------------------

def test_compare_single_run(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=3)
    entry = _entry("RUN-001", artifact_paths=paths)
    result = compare_runs([entry])
    assert result.run_count == 1
    assert result.run_ids == ["RUN-001"]


def test_compare_three_stable_runs(tmp_path):
    entries = []
    for i in range(1, 4):
        rid = f"RUN-{i:03d}"
        paths = _write_artifacts(tmp_path, rid, n_candidates=3)
        entries.append(_entry(rid, artifact_paths=paths))

    result = compare_runs(entries)
    assert result.run_count == 3
    assert result.ceiling_consistent
    assert all(c == "CONTINUE RESEARCH" for c in result.evidence_ceilings)
    assert result.verdict_consistent


def test_compare_detects_retrieval_zero(tmp_path):
    paths_ok = _write_artifacts(tmp_path, "RUN-001", n_candidates=5)
    paths_empty = _write_artifacts(tmp_path, "RUN-002", n_candidates=0)
    entries = [
        _entry("RUN-001", verdict="CONTINUE RESEARCH", artifact_paths=paths_ok),
        _entry("RUN-002", verdict="REJECT", artifact_paths=paths_empty),
    ]
    result = compare_runs(entries)
    assert not result.retrieval_stable
    assert 0 in result.candidate_counts


def test_compare_ceiling_always_continue_research(tmp_path):
    entries = []
    for i in range(1, 4):
        rid = f"RUN-{i:03d}"
        paths = _write_artifacts(tmp_path, rid, n_candidates=3)
        entries.append(_entry(rid, ceiling="CONTINUE RESEARCH", artifact_paths=paths))
    result = compare_runs(entries)
    assert result.ceiling_consistent
    assert all(c == "CONTINUE RESEARCH" for c in result.evidence_ceilings)


def test_compare_raises_on_empty_list():
    with pytest.raises(ValueError, match="at least one"):
        compare_runs([])


def test_compare_returns_common_mechanisms(tmp_path):
    entries = []
    for i in range(1, 3):
        rid = f"RUN-{i:03d}"
        paths = _write_artifacts(tmp_path, rid, n_candidates=3)
        entries.append(_entry(rid, artifact_paths=paths))
    result = compare_runs(entries)
    assert isinstance(result.common_mechanisms, list)
    assert isinstance(result.any_run_mechanisms, list)


def test_compare_overall_stability_stable(tmp_path):
    entries = []
    for i in range(1, 4):
        rid = f"RUN-{i:03d}"
        paths = _write_artifacts(tmp_path, rid, n_candidates=5)
        entries.append(_entry(rid, artifact_paths=paths))
    result = compare_runs(entries)
    # With consistent ceiling and verdicts, should be stable or partially_stable
    assert result.overall_stability in ("stable", "partially_stable")


# ---------------------------------------------------------------------------
# write_cross_run_report
# ---------------------------------------------------------------------------

def test_write_cross_run_report_produces_markdown(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=3)
    entry = _entry("RUN-001", artifact_paths=paths)
    result = compare_runs([entry])
    out = tmp_path / "comparison.md"
    write_cross_run_report(result, out)
    md = out.read_text()
    assert "Cross-Run Comparison Report" in md
    assert "RUN-001" in md
    assert "CONTINUE RESEARCH" in md
    assert "Evidence Ceiling" in md
