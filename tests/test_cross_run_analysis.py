"""Focused tests for core/cross_run_analysis.py — three-category mutation analysis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.cross_run_analysis import (
    CLASSIFICATION_INPUT_FIELDS,
    STABLE_BUSINESS_FIELDS,
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


def _raw_record(
    complaint_id: str,
    index: int = 0,
    narrative: str | None = None,
    product: str = "Credit reporting",
    issue: str = "Incorrect info",
    company: str = "ACME Corp",
    company_response: str = "Closed with explanation",
    retrieved_at: str = "2026-07-15T00:00:00Z",
) -> dict:
    """Build a realistic raw CFPB record with all field buckets present."""
    return {
        # CLASSIFICATION_INPUT_FIELDS
        "complaint_what_happened": narrative if narrative is not None else f"narrative {index}",
        "product": product,
        "sub_product": "Credit reporting",
        "issue": issue,
        "sub_issue": "Information belongs to someone else",
        # STABLE_BUSINESS_FIELDS
        "complaint_id": complaint_id,
        "company": company,
        "state": "CA",
        "zip_code": "90210",
        "tags": None,
        "submitted_via": "Web",
        "has_narrative": True,
        "date_received": "2024-01-01T00:00:00Z",
        # Volatile metadata (expected to differ between pulls)
        "company_response": company_response,
        "timely": "Yes",
        "date_sent_to_company": "2024-01-02T00:00:00Z",
        "company_public_response": "Company chose not to provide a public response",
        "_retrieved_at": retrieved_at,
        "_retrieval_url": "https://consumerfinance.gov/api",
        "_access_method": "official_cfpb_search_api",
        "_source_name": "CFPB Consumer Complaint Database",
        "_cfpb_hit_id": complaint_id,
        "_source_record_id": complaint_id,
    }


def _write_artifacts(
    tmp_path: Path,
    run_id: str,
    n_candidates: int = 3,
    complaint_ids: list[str] | None = None,
    narratives: dict[str, str] | None = None,
    companies: dict[str, str] | None = None,
    company_responses: dict[str, str] | None = None,
    retrieved_at: str = "2026-07-15T00:00:00Z",
) -> dict[str, str]:
    """Write minimal artifact files and return an artifact_paths dict."""
    exports = tmp_path / run_id / "exports"
    exports.mkdir(parents=True)
    raw_dir = tmp_path / run_id / "raw"
    raw_dir.mkdir()
    processed_dir = tmp_path / run_id / "processed"
    processed_dir.mkdir()

    if complaint_ids is None:
        complaint_ids = [f"COMPLAINT-{i:04d}" for i in range(n_candidates)]

    raw_records = [
        _raw_record(
            complaint_id=cid,
            index=i,
            narrative=(narratives or {}).get(cid),
            company=(companies or {}).get(cid, "ACME Corp"),
            company_response=(company_responses or {}).get(cid, "Closed with explanation"),
            retrieved_at=retrieved_at,
        )
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

    finding_companies = ["CompA", "CompB"] if n_candidates >= 2 else ["CompA"]
    findings = []
    for i in range(min(2, n_candidates)):
        findings.append({
            "finding_id": f"FND-{i:03d}",
            "mechanism": [
                "bureau_dispute_reinvestigation_failure",
                "furnisher_tradeline_data_error_persistence",
            ][i % 2],
            "companies": finding_companies,
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
# RunSnapshot — field bucket loading
# ---------------------------------------------------------------------------

def test_snapshot_loads_complaint_ids(tmp_path):
    ids = ["C-001", "C-002", "C-003"]
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=3, complaint_ids=ids)
    entry = _entry("RUN-001", artifact_paths=paths)
    snap = _load_run_snapshot(entry)
    assert snap.complaint_ids == ids


def test_snapshot_has_three_content_buckets(tmp_path):
    ids = ["C-001", "C-002"]
    paths = _write_artifacts(tmp_path, "RUN-001", n_candidates=2, complaint_ids=ids)
    snap = _load_run_snapshot(_entry("RUN-001", artifact_paths=paths))
    assert set(snap.classification_content_by_id.keys()) == set(ids)
    assert set(snap.business_content_by_id.keys()) == set(ids)
    assert set(snap.metadata_content_by_id.keys()) == set(ids)


def test_snapshot_classification_hash_covers_correct_fields(tmp_path):
    """Same classification fields → same hash regardless of metadata."""
    ids = ["C-001"]
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids,
                               company_responses={"C-001": "Closed with relief"},
                               retrieved_at="2026-07-15T10:00:00Z")
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids,
                               company_responses={"C-001": "Closed with explanation"},
                               retrieved_at="2026-07-15T11:00:00Z")
    snap_a = _load_run_snapshot(_entry("RUN-A", artifact_paths=paths_a))
    snap_b = _load_run_snapshot(_entry("RUN-B", artifact_paths=paths_b))
    # Classification hash must be identical (company_response and _retrieved_at are volatile)
    assert snap_a.classification_content_by_id["C-001"] == snap_b.classification_content_by_id["C-001"]
    # Metadata hash must differ
    assert snap_a.metadata_content_by_id["C-001"] != snap_b.metadata_content_by_id["C-001"]


def test_snapshot_complaint_id_set_hash_is_order_independent(tmp_path):
    ids_a = ["C-001", "C-002", "C-003"]
    ids_b = ["C-003", "C-001", "C-002"]
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids_a)
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids_b)
    snap_a = _load_run_snapshot(_entry("RUN-A", artifact_paths=paths_a))
    snap_b = _load_run_snapshot(_entry("RUN-B", artifact_paths=paths_b))
    assert snap_a.complaint_id_set_hash == snap_b.complaint_id_set_hash
    assert snap_a.complaint_ordering_hash != snap_b.complaint_ordering_hash


def test_snapshot_handles_missing_raw_artifact(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-NORAW")
    paths.pop("raw")
    snap = _load_run_snapshot(_entry("RUN-NORAW", artifact_paths=paths))
    assert snap.complaint_ids == []
    assert snap.classification_content_by_id == {}


# ---------------------------------------------------------------------------
# compare_runs — count-level
# ---------------------------------------------------------------------------

def test_compare_single_run(tmp_path):
    paths = _write_artifacts(tmp_path, "RUN-001")
    result = compare_runs([_entry("RUN-001", artifact_paths=paths)])
    assert result.run_count == 1


def test_compare_three_stable_runs_same_content(tmp_path):
    """Identical records across all runs → no mutation of any kind."""
    ids = [f"C-{i:04d}" for i in range(3)]
    entries = []
    for i in range(1, 4):
        rid = f"RUN-{i:03d}"
        paths = _write_artifacts(tmp_path, rid, complaint_ids=ids,
                                 retrieved_at="2026-07-15T00:00:00Z")
        entries.append(_entry(rid, artifact_paths=paths))
    result = compare_runs(entries)
    assert result.run_count == 3
    assert result.complaint_ids_identical
    assert result.jaccard_similarity == 1.0
    assert result.ordering_stable
    assert not result.classification_mutation_detected
    assert not result.business_mutation_detected
    assert not result.mutation_detected


# ---------------------------------------------------------------------------
# Three-category mutation analysis
# ---------------------------------------------------------------------------

def test_metadata_only_change_is_not_classified_as_mutation(tmp_path):
    """Volatile metadata changes (company_response, _retrieved_at) must NOT
    set classification_mutation_detected or business_mutation_detected."""
    ids = ["C-001", "C-002"]
    # Run A: one company_response value and one retrieved_at
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids,
                               company_responses={"C-001": "Closed with explanation",
                                                  "C-002": "Closed with explanation"},
                               retrieved_at="2026-07-15T10:00:00Z")
    # Run B: different company_response and retrieved_at (volatile fields)
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids,
                               company_responses={"C-001": "Closed with non-monetary relief",
                                                  "C-002": "Closed with monetary relief"},
                               retrieved_at="2026-07-15T11:00:00Z")
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    # Volatile metadata differs
    assert result.metadata_differs
    assert result.metadata_differs_count == 2
    # But classification and business fields are unchanged — NOT a mutation
    assert not result.classification_mutation_detected
    assert not result.business_mutation_detected
    assert not result.mutation_detected
    # Metadata differences must NOT penalise overall_stability
    assert result.overall_stability == "stable"


def test_classification_field_change_is_detected_as_classification_mutation(tmp_path):
    """Changing complaint_what_happened (a CLASSIFICATION_INPUT_FIELD) must
    set classification_mutation_detected=True."""
    ids = ["C-001", "C-002"]
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids,
                               narratives={"C-001": "original narrative", "C-002": "stable"})
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids,
                               narratives={"C-001": "mutated narrative", "C-002": "stable"})
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    assert result.classification_mutation_detected
    assert any("C-001" in d for d in result.classification_mutation_details)
    assert not any("C-002" in d for d in result.classification_mutation_details)
    # Classification mutation IS a stability issue
    assert result.overall_stability == "unstable"


def test_business_field_change_detected_not_classification(tmp_path):
    """Changing company (STABLE_BUSINESS_FIELD) must set business_mutation_detected
    but NOT classification_mutation_detected."""
    ids = ["C-001"]
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids,
                               companies={"C-001": "Company Alpha"})
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids,
                               companies={"C-001": "Company Beta"})
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    assert result.business_mutation_detected
    assert not result.classification_mutation_detected
    # mutation_detected summary is True (business mutation counts)
    assert result.mutation_detected
    # Business mutation is a mild stability issue (partially_stable at most)
    assert result.overall_stability in ("partially_stable", "unstable")


def test_mutation_detected_summary_excludes_metadata(tmp_path):
    """mutation_detected must be False when only volatile metadata differs."""
    ids = ["C-001"]
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids,
                               retrieved_at="2026-07-15T10:00:00Z")
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids,
                               retrieved_at="2026-07-15T11:00:00Z")
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    assert result.metadata_differs
    assert not result.mutation_detected


def test_compare_detects_source_mutation(tmp_path):
    """Original test updated: same complaint ID with different
    complaint_what_happened → classification_mutation_detected."""
    rid_a, rid_b = "RUN-MUT-A", "RUN-MUT-B"
    ids = ["C-001", "C-002"]

    paths_a = _write_artifacts(
        tmp_path, rid_a, complaint_ids=ids,
        narratives={"C-001": "original", "C-002": "stable content"},
    )
    paths_b = _write_artifacts(
        tmp_path, rid_b, complaint_ids=ids,
        narratives={"C-001": "original", "C-002": "mutated content"},
    )
    result = compare_runs([
        _entry(rid_a, artifact_paths=paths_a),
        _entry(rid_b, artifact_paths=paths_b),
    ])
    assert result.complaint_ids_identical
    assert result.classification_mutation_detected
    assert any("C-002" in d for d in result.classification_mutation_details)
    assert result.mutation_detected


# ---------------------------------------------------------------------------
# Complaint-ID overlap
# ---------------------------------------------------------------------------

def test_compare_detects_different_complaint_id_sets(tmp_path):
    paths_a = _write_artifacts(tmp_path, "RUN-A",
                               complaint_ids=["C-001", "C-002", "C-003"])
    paths_b = _write_artifacts(tmp_path, "RUN-B",
                               complaint_ids=["C-002", "C-003", "C-004"])
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    assert not result.complaint_ids_identical
    assert abs(result.jaccard_similarity - 0.5) < 0.01
    assert "Jaccard" in result.id_overlap_note


def test_compare_identical_ids_different_order(tmp_path):
    paths_a = _write_artifacts(tmp_path, "RUN-A",
                               complaint_ids=["C-001", "C-002", "C-003"])
    paths_b = _write_artifacts(tmp_path, "RUN-B",
                               complaint_ids=["C-003", "C-002", "C-001"])
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    assert result.complaint_ids_identical
    assert result.jaccard_similarity == 1.0
    assert not result.ordering_stable


def test_compare_exposes_id_set_hashes(tmp_path):
    ids = ["C-001", "C-002"]
    paths = _write_artifacts(tmp_path, "RUN-001", complaint_ids=ids)
    result = compare_runs([_entry("RUN-001", artifact_paths=paths)])
    assert len(result.id_set_hashes) == 1
    assert len(result.complaint_ordering_hashes) == 1
    assert all(len(h) > 10 for h in result.id_set_hashes)


# ---------------------------------------------------------------------------
# Retrieval stability
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
        paths = _write_artifacts(tmp_path, rid)
        entries.append(_entry(rid, ceiling="CONTINUE RESEARCH", artifact_paths=paths))
    result = compare_runs(entries)
    assert result.ceiling_consistent
    assert all(c == "CONTINUE RESEARCH" for c in result.evidence_ceilings)


def test_compare_raises_on_empty_list():
    with pytest.raises(ValueError, match="at least one"):
        compare_runs([])


# ---------------------------------------------------------------------------
# write_cross_run_report — three-category sections
# ---------------------------------------------------------------------------

def test_write_cross_run_report_has_three_mutation_sections(tmp_path):
    ids = ["C-001", "C-002"]
    # Run A: stable narrative, volatile metadata differs
    paths_a = _write_artifacts(tmp_path, "RUN-A", complaint_ids=ids,
                               retrieved_at="2026-07-15T10:00:00Z")
    # Run B: same narrative, different retrieved_at (metadata-only change)
    paths_b = _write_artifacts(tmp_path, "RUN-B", complaint_ids=ids,
                               retrieved_at="2026-07-15T11:00:00Z")
    result = compare_runs([
        _entry("RUN-A", artifact_paths=paths_a),
        _entry("RUN-B", artifact_paths=paths_b),
    ])
    out = tmp_path / "comparison.md"
    write_cross_run_report(result, out)
    md = out.read_text()
    # All three categories must appear
    assert "Classification-input mutation" in md
    assert "Stable-business-field mutation" in md
    assert "Volatile-metadata differences" in md
    # Metadata section must say "expected" or "informational"
    assert "expected" in md.lower() or "informational" in md.lower()


def test_write_cross_run_report_stable_run_shows_none_for_mutations(tmp_path):
    """When no mutations of any kind, report must show NONE for all three."""
    ids = ["C-001", "C-002"]
    paths = _write_artifacts(tmp_path, "RUN-001", complaint_ids=ids,
                             retrieved_at="2026-07-15T00:00:00Z")
    result = compare_runs([_entry("RUN-001", artifact_paths=paths)])
    out = tmp_path / "comparison.md"
    write_cross_run_report(result, out)
    md = out.read_text()
    assert "NONE" in md


def test_write_report_includes_id_overlap_and_ordering(tmp_path):
    ids = [f"C-{i:04d}" for i in range(5)]
    paths = _write_artifacts(tmp_path, "RUN-001", complaint_ids=ids)
    result = compare_runs([_entry("RUN-001", artifact_paths=paths)])
    out = tmp_path / "comparison.md"
    write_cross_run_report(result, out)
    md = out.read_text()
    assert "Jaccard" in md
    assert "Ordering" in md or "ordering" in md
