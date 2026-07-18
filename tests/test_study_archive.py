"""Focused tests for the study-archive generator (tools.build_study_archive)."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from tools.build_study_archive import (
    REDACTION_MARKER,
    build_archive,
    find_run_entry,
    redact_artifact,
    sha256_file,
    stable_hash_text,
)
from core.run_index import append_run_index, build_run_index_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data) -> str:
    """Write *data* as JSON to *path* (creating parents). Returns stable_hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2)
    path.write_text(text, encoding="utf-8")
    return stable_hash_text(text)


def _make_run_entry(tmp_path: Path) -> dict:
    """Create a minimal but realistic set of pipeline artifact files under
    tmp_path and return a run-index entry that points to them."""
    exports = tmp_path / "data" / "exports"
    raw_dir = tmp_path / "data" / "raw"

    raw_records = [
        {
            "complaint_id": "1001",
            "product": "Credit reporting or other personal consumer reports",
            "complaint_what_happened": "I had a problem with my credit report.",
            "company": "Acme Credit",
            "issue": "Incorrect information on your report",
        }
    ]
    raw_data = {"records": raw_records}
    raw_cksum = _write_json(raw_dir / "cfpb_raw_20260714T000000Z.json", raw_data)

    candidates = [
        {
            "candidate_id": "CAN-001",
            "raw_record": {
                "complaint_id": "1001",
                "complaint_what_happened": "I had a problem with my credit report.",
            },
            "parsed_fields": {
                "narrative": "I had a problem.",
                "issue": "Incorrect information on your report",
            },
        }
    ]
    cand_cksum = _write_json(exports / "normalised_candidates_20260714T000000Z.json", candidates)

    findings = [{"finding_id": "F-001", "description": "Repeated dispute failures"}]
    find_cksum = _write_json(exports / "findings_20260714T000000Z.json", findings)

    opportunities = [{"opportunity_id": "OPP-001", "description": "Workflow component"}]
    opp_cksum = _write_json(exports / "opportunities_20260714T000000Z.json", opportunities)

    manifest = {
        "run_id": "RUN-TEST001",
        "study_id": "GS-CF001-C",
        "final_verdict": "CONTINUE RESEARCH",
        "evidence_ceiling": "CONTINUE RESEARCH",
    }
    man_cksum = _write_json(exports / "run_manifest_20260714T000000Z.json", manifest)

    diag = [{"diagnostic_id": "ADIAG-1", "status": "200"}]
    diag_cksum = _write_json(exports / "access_diagnostics_20260714T000000Z.json", diag)

    reliability = [{"source_id": "CFPB-CCD-001", "authority": "regulatory"}]
    rel_cksum = _write_json(exports / "source_reliability_20260714T000000Z.json", reliability)

    verification = [{"candidate_id": "CAN-001", "status": "VERIFIED"}]
    ver_cksum = _write_json(exports / "verification_artifacts_20260714T000000Z.json", verification)

    gates = [{"gate_id": "PG-01", "status": "PASS"}]
    gate_cksum = _write_json(exports / "proof_gate_results_20260714T000000Z.json", gates)

    audit = [{"event": "normalised", "candidate_id": "CAN-001"}]
    audit_cksum = _write_json(exports / "audit_trail_20260714T000000Z.json", audit)

    report_json_data = {
        "verdict": "CONTINUE RESEARCH",
        "records": [{"complaint_what_happened": "I had a problem."}],
    }
    rep_json_cksum = _write_json(exports / "gs_cf001_c_report_20260714T000000Z.json", report_json_data)

    report_md = exports / "gs_cf001_c_report_20260714T000000Z.md"
    report_md.write_text("# Report\n\nVerdict: CONTINUE RESEARCH\n", encoding="utf-8")
    rep_md_cksum = stable_hash_text(report_md.read_text(encoding="utf-8"))

    artifact_paths = {
        "raw": str(raw_dir / "cfpb_raw_20260714T000000Z.json"),
        "normalised_candidates": str(exports / "normalised_candidates_20260714T000000Z.json"),
        "findings": str(exports / "findings_20260714T000000Z.json"),
        "opportunities": str(exports / "opportunities_20260714T000000Z.json"),
        "run_manifest": str(exports / "run_manifest_20260714T000000Z.json"),
        "access_diagnostics": str(exports / "access_diagnostics_20260714T000000Z.json"),
        "source_reliability": str(exports / "source_reliability_20260714T000000Z.json"),
        "verification_artifacts": str(exports / "verification_artifacts_20260714T000000Z.json"),
        "proof_gate_results": str(exports / "proof_gate_results_20260714T000000Z.json"),
        "audit_trail": str(exports / "audit_trail_20260714T000000Z.json"),
        "report_json": str(exports / "gs_cf001_c_report_20260714T000000Z.json"),
        "report_markdown": str(exports / "gs_cf001_c_report_20260714T000000Z.md"),
    }
    artifact_checksums = {
        artifact_paths["raw"]: raw_cksum,
        artifact_paths["normalised_candidates"]: cand_cksum,
        artifact_paths["findings"]: find_cksum,
        artifact_paths["opportunities"]: opp_cksum,
        artifact_paths["run_manifest"]: man_cksum,
        artifact_paths["access_diagnostics"]: diag_cksum,
        artifact_paths["source_reliability"]: rel_cksum,
        artifact_paths["verification_artifacts"]: ver_cksum,
        artifact_paths["proof_gate_results"]: gate_cksum,
        artifact_paths["audit_trail"]: audit_cksum,
        artifact_paths["report_json"]: rep_json_cksum,
        artifact_paths["report_markdown"]: rep_md_cksum,
    }
    return build_run_index_entry(
        run_id="RUN-TEST001",
        timestamp="20260714T000000000000Z",
        study_id="GS-CF001-C",
        verdict="CONTINUE RESEARCH",
        evidence_ceiling="CONTINUE RESEARCH",
        source_access_method="official_cfpb_search_api",
        artifact_paths=artifact_paths,
        artifact_checksums=artifact_checksums,
    )


# ---------------------------------------------------------------------------
# Redaction unit tests
# ---------------------------------------------------------------------------

def test_redact_non_empty_narrative_field():
    data = {"complaint_what_happened": "Sensitive text here."}
    result = redact_artifact(data)
    assert result["complaint_what_happened"] == REDACTION_MARKER


def test_redact_empty_narrative_field_is_left_as_is():
    """Empty strings represent 'no narrative provided' and are not redacted —
    their presence or absence is itself provenance information."""
    data = {"complaint_what_happened": ""}
    result = redact_artifact(data)
    assert result["complaint_what_happened"] == ""


def test_redact_nested_raw_record_and_parsed_fields():
    data = {
        "candidate_id": "CAN-001",
        "raw_record": {"complaint_what_happened": "Private text."},
        "parsed_fields": {"narrative": "Also private.", "issue": "Kept"},
    }
    result = redact_artifact(data)
    assert result["raw_record"]["complaint_what_happened"] == REDACTION_MARKER
    assert result["parsed_fields"]["narrative"] == REDACTION_MARKER
    assert result["parsed_fields"]["issue"] == "Kept"
    assert result["candidate_id"] == "CAN-001"


def test_redact_preserves_non_narrative_fields():
    data = {
        "complaint_id": "9999997",
        "product": "Credit reporting",
        "company": "Acme Corp",
        "complaint_what_happened": "Some narrative.",
    }
    result = redact_artifact(data)
    assert result["complaint_id"] == "9999997"
    assert result["product"] == "Credit reporting"
    assert result["company"] == "Acme Corp"
    assert result["complaint_what_happened"] == REDACTION_MARKER


def test_redact_list_of_records():
    records = [
        {"complaint_what_happened": "Text A", "id": "1"},
        {"complaint_what_happened": "", "id": "2"},
        {"complaint_what_happened": "Text C", "id": "3"},
    ]
    result = redact_artifact(records)
    assert result[0]["complaint_what_happened"] == REDACTION_MARKER
    assert result[1]["complaint_what_happened"] == ""
    assert result[2]["complaint_what_happened"] == REDACTION_MARKER
    # IDs untouched.
    assert [r["id"] for r in result] == ["1", "2", "3"]


def test_redact_none_value_is_unchanged():
    data = {"complaint_what_happened": None, "narrative": None}
    result = redact_artifact(data)
    assert result["complaint_what_happened"] is None
    assert result["narrative"] is None


# ---------------------------------------------------------------------------
# Archive structure tests
# ---------------------------------------------------------------------------

def test_archive_creates_expected_files(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"

    archive_dir = build_archive(entry, archive_root=archive_root)

    assert archive_dir.exists()
    assert (archive_dir / "run_manifest.json").exists()
    assert (archive_dir / "raw_records_redacted.json").exists()
    assert (archive_dir / "normalised_candidates_redacted.json").exists()
    assert (archive_dir / "findings.json").exists()
    assert (archive_dir / "opportunities.json").exists()
    assert (archive_dir / "report.json").exists()
    assert (archive_dir / "report.md").exists()
    assert (archive_dir / "access_diagnostics.json").exists()
    assert (archive_dir / "source_reliability_assessment.json").exists()
    assert (archive_dir / "verification_artifacts.json").exists()
    assert (archive_dir / "proof_gate_results.json").exists()
    assert (archive_dir / "audit_trail.json").exists()
    assert (archive_dir / "archive_metadata.json").exists()
    assert (archive_dir / "README.md").exists()
    assert (archive_dir / "checksums.txt").exists()


def test_archive_directory_name_encodes_study_run_and_timestamp(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_dir = build_archive(entry, archive_root=archive_root)
    assert "GS-CF001-C" in archive_dir.name
    assert "RUN-TEST001" in archive_dir.name
    assert "20260714T000000000000Z" in archive_dir.name


def test_archive_refuses_to_overwrite_existing(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    build_archive(entry, archive_root=archive_root)  # first build succeeds

    with pytest.raises(FileExistsError, match="already exists"):
        build_archive(entry, archive_root=archive_root)  # second must fail


def test_archive_redacts_narrative_in_raw_records(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_dir = build_archive(entry, archive_root=archive_root)

    raw = json.loads((archive_dir / "raw_records_redacted.json").read_text(encoding="utf-8"))
    for rec in raw.get("records", [raw]):
        assert rec.get("complaint_what_happened") != "I had a problem with my credit report."
        if rec.get("complaint_what_happened"):
            assert rec["complaint_what_happened"] == REDACTION_MARKER


def test_archive_redacts_narrative_in_candidates(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_dir = build_archive(entry, archive_root=archive_root)

    candidates = json.loads(
        (archive_dir / "normalised_candidates_redacted.json").read_text(encoding="utf-8")
    )
    for c in candidates:
        raw_rec = c.get("raw_record", {})
        parsed = c.get("parsed_fields", {})
        if raw_rec.get("complaint_what_happened"):
            assert raw_rec["complaint_what_happened"] == REDACTION_MARKER
        if parsed.get("narrative"):
            assert parsed["narrative"] == REDACTION_MARKER


def test_archive_metadata_contains_run_fields(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_dir = build_archive(entry, archive_root=archive_root)

    meta = json.loads((archive_dir / "archive_metadata.json").read_text(encoding="utf-8"))
    assert meta["run_id"] == "RUN-TEST001"
    assert meta["study_id"] == "GS-CF001-C"
    assert meta["verdict"] == "CONTINUE RESEARCH"
    assert meta["evidence_ceiling"] == "CONTINUE RESEARCH"
    assert meta["source_access_method"] == "official_cfpb_search_api"
    assert "archive_files" in meta
    assert "redaction_policy" in meta


def test_checksums_txt_is_sha256sum_verifiable(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_dir = build_archive(entry, archive_root=archive_root)

    checksums_text = (archive_dir / "checksums.txt").read_text(encoding="utf-8")
    for line in checksums_text.strip().splitlines():
        digest, fname = line.split("  ", 1)
        target = archive_dir / fname
        # checksums.txt itself is not listed (written after checksums are computed)
        if fname == "checksums.txt":
            continue
        assert target.exists(), f"checksums.txt references non-existent file: {fname}"
        h = hashlib.sha256()
        with target.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        assert h.hexdigest() == digest, f"Checksum mismatch for {fname}"


def test_archive_detects_tampered_source_artifact(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"

    # Tamper with a source artifact after the checksums were recorded.
    raw_path = Path(entry["artifact_paths"]["raw"])
    raw_path.write_text("tampered content", encoding="utf-8")

    with pytest.raises(ValueError, match="Checksum mismatch"):
        build_archive(entry, archive_root=archive_root)

    # Partial archive must have been cleaned up.
    for child in (tmp_path / "study_archives").iterdir():
        assert False, f"Partial archive left behind: {child}"


def test_tamper_detection_leaves_no_partial_archive(tmp_path):
    """After a checksum failure the study_archives/ directory stays empty."""
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_root.mkdir()

    raw_path = Path(entry["artifact_paths"]["run_manifest"])
    raw_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError):
        build_archive(entry, archive_root=archive_root)

    # Nothing left in archive root.
    assert list(archive_root.iterdir()) == []


def test_readme_contains_required_sections(tmp_path):
    entry = _make_run_entry(tmp_path)
    archive_root = tmp_path / "study_archives"
    archive_dir = build_archive(entry, archive_root=archive_root)

    readme = (archive_dir / "README.md").read_text(encoding="utf-8")
    assert "RUN-TEST001" in readme
    assert "CONTINUE RESEARCH" in readme
    assert "Evidence Ceiling" in readme
    assert "Redaction policy" in readme
    assert "How a run becomes an archive" in readme
    assert "Independent verification" in readme
    assert "sha256sum -c checksums.txt" in readme


# ---------------------------------------------------------------------------
# find_run_entry tests
# ---------------------------------------------------------------------------

def test_find_latest_returns_last_entry(tmp_path):
    index_path = tmp_path / "run_index.json"
    for i in range(1, 4):
        append_run_index(
            build_run_index_entry(
                run_id=f"RUN-{i:03d}", timestamp=f"20260714T00000{i}Z",
                study_id="GS-CF001-C", verdict="CONTINUE RESEARCH",
                evidence_ceiling="CONTINUE RESEARCH",
                source_access_method="official_cfpb_search_api",
                artifact_paths={}, artifact_checksums={},
            ),
            path=index_path,
        )
    entry = find_run_entry(index_path, latest=True)
    assert entry["run_id"] == "RUN-003"


def test_find_by_run_id(tmp_path):
    index_path = tmp_path / "run_index.json"
    for i in range(1, 4):
        append_run_index(
            build_run_index_entry(
                run_id=f"RUN-{i:03d}", timestamp=f"20260714T00000{i}Z",
                study_id="GS-CF001-C", verdict="CONTINUE RESEARCH",
                evidence_ceiling="CONTINUE RESEARCH",
                source_access_method="official_cfpb_search_api",
                artifact_paths={}, artifact_checksums={},
            ),
            path=index_path,
        )
    entry = find_run_entry(index_path, run_id="RUN-002")
    assert entry["run_id"] == "RUN-002"


def test_find_missing_run_id_raises(tmp_path):
    index_path = tmp_path / "run_index.json"
    append_run_index(
        build_run_index_entry(
            run_id="RUN-001", timestamp="20260714T000001Z",
            study_id="GS-CF001-C", verdict="CONTINUE RESEARCH",
            evidence_ceiling="CONTINUE RESEARCH",
            source_access_method="official_cfpb_search_api",
            artifact_paths={}, artifact_checksums={},
        ),
        path=index_path,
    )
    with pytest.raises(ValueError, match="No run with run_id"):
        find_run_entry(index_path, run_id="RUN-999")


def test_find_on_empty_index_raises(tmp_path):
    index_path = tmp_path / "run_index.json"
    index_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        find_run_entry(index_path, latest=True)


def test_find_on_missing_index_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_run_entry(tmp_path / "nonexistent.json", latest=True)
