"""Focused tests for core/cross_run_analysis.py — including Correction 4 (complaint-ID overlap)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.cross_run_analysis import (
    CrossRunComparison,
    RunSnapshot,
    _load_run_snapshot,
    compare_runs,
    write_cross_run_report,
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


def _write_artifacts(
    tmp_path: Path,
    run_id: str,
    n_candidates: int = 3,
    complaint_ids: list[str] | None = None,
) -> dict[str, str]:
    """Write minimal artifact files and return an artifact_paths dict."""
    exports = tmp_path / run_id / "exports"
    exports.mkdir(parents=True)
    raw_dir = tmp_path / run_id / "raw"
    raw_dir.mkdir()
    processed_dir = tmp_path / run_id / "processed"
    processed_dir.mkdir()

    # Default complaint IDs
    if complaint_ids is None:
        complaint_ids = [f"COMPLAINT-{i:04d}" for i in range(n_candidates)]

    # Raw records — includes complaint_id field for ID-overlap analysis
    raw_records = [
        {
            "complaint_id": cid,
            "product": "Credit reporting",
            "issue": "Incorrect info",
            "narrative": f"narrative {i}",
        }
        for i, cid in enumerate(complaint_ids)
    ]
    raw_payload = {"records": raw_records, "source": {}}
    (raw_dir / "cfpb_credit_reporting_raw.json").write_text(
        json.dumps(raw_payload), encoding="utf-8"
    )

    candidates = [{"candidate_id": f"CAN-{i:03d}"} for i in range(n_candidates)]
    (exports / "normalised_candidates.json").write_text(
        json.dumps(candidates), encoding="utf-8"
    )

    companies = ["CompA", "CompB"] if n_candidates >= 2 else ["CompA"]
    findings = []
    for i in range(min(2, n_candidates)):
        findings.append({
            "finding_id": f"FND-{i:03d}",
            "mechanism": [
                "bureau_dispute_reinvestigation_failure",
                "furnisher_tradeline_data_error_persistence",
            ][i % 2],
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
    (processed_dir / "gs_cf001_c_processed.json").write_text(
        json.dumps(proc), encoding="utf-8"
    )

    return {
        "raw": str(raw_dir / "cfpb_credit_reporting_raw.json"),
        "normalised_candidates": str(exports / "normalised_candidates.json"),
        "findings": str(exports / "findings.json"),
        "opportunities": str(exports / "opportunities.json"),
        "proof_gate_results": str(exports / "proof_gate_results.json"),
        "processed": str(processed_dir / "gs_cf001_c_processed.json"),
    }


# ---------------------------------------------------------------------------
# RunSnapshot — Correction 4 fields
# ---------------------------------------------------------------------------

def test_snapshot_loads_complaint_ids(tmp_path):
    ids = ["C-001", "C-002", "C-003"]
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=3, complaint_ids=ids)
    entry = _entry("RUN-001", artifact_paths=paths)
    snap = _load_run_snapshot(entry)
    assert snap.complaint_ids == ids


def test_snapshot_complaint_id_set_hash_is_order_independent(tmp_path):
    """Same IDs in different order → same set hash, different ordering hash."""
    ids_a = ["C-001", "C-002", "C-003"]
    ids_b = ["C-003", "C-001", "C-002"]
    paths_a = _write_artifacts(tmp_path, "RUN-A", n_candidates=3, complaint_ids=ids_a)
    paths_b = _write_artifacts(tmp_path, "RUN-B", n_candidates=3, complaint_ids=ids_b)
    snap_a = _load_run_snapshot(_entry("RUN-A", artifact_paths=paths_a))
    snap_b = _load_run_snapshot(_entry("RUN-B", artifact_paths=paths_b))

    assert snap_a.complaint_id_set_hash == snap_b.complaint_id_set_hash
    assert snap_a.complaint_ordering_hash != snap_b.complaint_ordering_hash


def test_snapshot_handles_missing_raw_artifact(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-NORAW", n_candidates=3)
    paths.pop("raw")
    entry = _entry("RUN-NORAW", artifact_paths=paths)
    snap = _load_run_snapshot(entry)
    assert snap.complaint_ids == []
    assert snap.record_content_by_id == {}


# ---------------------------------------------------------------------------
# compare_runs — count-level (preserved)
# ---------------------------------------------------------------------------

def test_compare_single_run(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=3)
    entry = _entry("RUN-001", artifact_paths=paths)
    result = compare_runs([entry])
    assert result.run_count == 1


def test_compare_three_stable_runs_same_ids(tmp_path):
    ids = [f"C-{i:04d}" for i in range(3)]
    entries = []
    for i in range(1, 4):
        rid = f"RUN-{i:03d}"
        paths = _write_artifacts(tmp_path, rid, n_candidates=3, complaint_ids=ids)
        entries.append(_entry(rid, artifact_paths=paths))
    result = compare_runs(entries)
    assert result.run_count == 3
    assert result.complaint_ids_identical
    assert result.jaccard_similarity == 1.0
    assert result.ordering_stable
    assert not result.mutation_detected


# ---------------------------------------------------------------------------
# Complaint-ID overlap analysis (Correction 4)
# ---------------------------------------------------------------------------

def test_compare_detects_different_complaint_id_sets(tmp_path):
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=["C-001", "C-002", "C-003"])
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=["C-002", "C-003", "C-004"])
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    assert not result.complaint_ids_identical
    # Jaccard = |{C-002,C-003}| / |{C-001,C-002,C-003,C-004}| = 2/4 = 0.5
    assert abs(result.jaccard_similarity - 0.5) < 0.01
    assert "Jaccard" in result.id_overlap_note


def test_compare_identical_ids_different_order_detects_ordering_instability(tmp_path):
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=["C-001", "C-002", "C-003"])
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=["C-003", "C-002", "C-001"])
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    # Same IDs → identical sets → complaint_ids_identical=True
    assert result.complaint_ids_identical
    assert result.jaccard_similarity == 1.0
    # Different ordering → ordering_stable=False
    assert not result.ordering_stable


def test_compare_detects_source_mutation(tmp_path):
    """Correction 4: same complaint ID with different content → mutation_detected."""
    # Write two runs with the same IDs but different content for one record
    rid_a, rid_b = "RUN-MUT-A", "RUN-MUT-B"
    exports_a = tmp_path / rid_a / "exports"
    exports_b = tmp_path / rid_b / "exports"
    raw_a = tmp_path / rid_a / "raw"
    raw_b = tmp_path / rid_b / "raw"
    for d in [exports_a, exports_b, raw_a, raw_b,
              tmp_path / rid_a / "processed", tmp_path / rid_b / "processed"]:
        d.mkdir(parents=True)

    shared_ids = ["C-001", "C-002"]

    def make_raw(extra_field: str) -> dict:
        return {
            "records": [
                {"complaint_id": "C-001", "narrative": "original"},
                {"complaint_id": "C-002", "narrative": extra_field},  # mutated
            ],
            "source": {},
        }

    (raw_a / "cfpb_credit_reporting_raw.json").write_text(
        json.dumps(make_raw("stable content")), encoding="utf-8"
    )
    (raw_b / "cfpb_credit_reporting_raw.json").write_text(
        json.dumps(make_raw("mutated content")), encoding="utf-8"
    )
    for rid, exp, pr in [(rid_a, exports_a, tmp_path / rid_a / "processed"),
                          (rid_b, exports_b, tmp_path / rid_b / "processed")]:
        (exp / "normalised_candidates.json").write_text("[]", encoding="utf-8")
        (exp / "findings.json").write_text("[]", encoding="utf-8")
        (exp / "opportunities.json").write_text("[]", encoding="utf-8")
        (exp / "proof_gate_results.json").write_text("[]", encoding="utf-8")
        (pr / "gs_cf001_c_processed.json").write_text("{}", encoding="utf-8")

    paths_a = {
        "raw": str(raw_a / "cfpb_credit_reporting_raw.json"),
        "normalised_candidates": str(exports_a / "normalised_candidates.json"),
        "findings": str(exports_a / "findings.json"),
        "opportunities": str(exports_a / "opportunities.json"),
        "proof_gate_results": str(exports_a / "proof_gate_results.json"),
        "processed": str(tmp_path / rid_a / "processed" / "gs_cf001_c_processed.json"),
    }
    paths_b = {k: v.replace(rid_a, rid_b) for k, v in paths_a.items()}

    result = compare_runs([
        _entry(rid_a, artifact_paths=paths_a),
        _entry(rid_b, artifact_paths=paths_b),
    ])
    assert result.complaint_ids_identical
    assert result.mutation_detected
    assert any("C-002" in d for d in result.mutation_details)


# ---------------------------------------------------------------------------
# Complaint-ID hash fields present in CrossRunComparison
# ---------------------------------------------------------------------------

def test_compare_exposes_id_set_hashes(tmp_path):
    ids = ["C-001", "C-002"]
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=2, complaint_ids=ids)
    result = compare_runs([_entry("RUN-001", artifact_paths=paths)])
    assert len(result.id_set_hashes) == 1
    assert len(result.complaint_ordering_hashes) == 1
    # Hashes are non-empty strings
    assert all(len(h) > 10 for h in result.id_set_hashes)


# ---------------------------------------------------------------------------
# compare_runs — verdict / ceiling (preserved)
# ---------------------------------------------------------------------------

def test_compare_detects_retrieval_zero(tmp_path):
    paths_ok = _write_artifacts(tmp_path, "RUN-001", n_candidates=5)
    paths_empty = _write_artifacts(tmp_path, "RUN-002", n_candidates=0)
    result = compare_runs([
        _entry("RUN-001", verdict="CONTINUE RESEARCH", artifact_paths=paths_ok),
        _entry("RUN-002", verdict="REJECT", artifact_paths=paths_empty),
    ])
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


# ---------------------------------------------------------------------------
# write_cross_run_report — Correction 4 fields appear in report
# ---------------------------------------------------------------------------

def test_write_cross_run_report_includes_id_overlap_section(tmp_path):
    ids = [f"C-{i:04d}" for i in range(5)]
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=5, complaint_ids=ids)
    result = compare_runs([_entry("RUN-001", artifact_paths=paths)])
    out = tmp_path / "comparison.md"
    write_cross_run_report(result, out)
    md = out.read_text()
    assert "Complaint-ID overlap" in md or "complaint-ID" in md.lower() or "ID-set hash" in md
    assert "Jaccard" in md
    assert "Ordering" in md or "ordering" in md
    assert "mutation" in md.lower()
