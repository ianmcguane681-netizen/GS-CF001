"""End-to-end test: rejection harness produces genuine REJECTED ODR outcomes.

Correction 5 of the methodology-validation review: the ODR must produce
genuine REJECTED outcomes. This test runs the full pipeline with the
RejectionHarnessConnector and asserts:

  1. Pipeline completes without error.
  2. All harness records have verified_candidate status (operational=True,
     traceable=True) — they pass the verification gate.
  3. Majority of verified evidence items are NOT software-addressable
     (software_addressable=False), confirming the test data is well-formed.
  4. At least one finding is classified as non_software_problem.
  5. The ODR contains at least one REJECTED entry.
  6. Evidence ceiling is CONTINUE RESEARCH (unchanged by rejection harness).
  7. Mechanism names use the trigger-process-failure-consequence format
     (Correction 6).
"""
from __future__ import annotations

import pytest

from connectors.rejection_harness import RejectionHarnessConnector, _HARNESS_RECORDS
from core.pipeline import run_credit_reporting_proof
from findings.mechanism_classifier import classify_all
from verification.classifier import verify_candidates
from verification.rules import OPERATIONAL_TERMS, SOFTWARE_ADDRESSABLE_TERMS, contains_any
from core.normalization import normalise_cfpb_records
from connectors.cfpb import cfpb_source
from studies.definitions import get_study


# ---------------------------------------------------------------------------
# Verify the harness records have the expected operational/software properties
# ---------------------------------------------------------------------------

def test_harness_records_are_operational():
    """All harness records must contain OPERATIONAL_TERMS."""
    for rec in _HARNESS_RECORDS:
        text = " ".join([
            str(rec.get("product") or ""),
            str(rec.get("sub_product") or ""),
            str(rec.get("issue") or ""),
            str(rec.get("sub_issue") or ""),
            str(rec.get("company") or ""),
            str(rec.get("company_response") or ""),
            str(rec.get("complaint_what_happened") or ""),
        ])
        assert contains_any(text, OPERATIONAL_TERMS), (
            f"Harness record {rec['complaint_id']} is not operational — "
            f"adjust text to include at least one OPERATIONAL_TERM."
        )


def test_harness_records_are_not_software_addressable():
    """All harness records must NOT contain SOFTWARE_ADDRESSABLE_TERMS.

    This ensures the harness produces software_addressable=False items so the
    resulting finding is classified as non_software_problem → REJECTED.
    """
    for rec in _HARNESS_RECORDS:
        text = " ".join([
            str(rec.get("product") or ""),
            str(rec.get("sub_product") or ""),
            str(rec.get("issue") or ""),
            str(rec.get("sub_issue") or ""),
            str(rec.get("company") or ""),
            str(rec.get("company_response") or ""),
            str(rec.get("complaint_what_happened") or ""),
        ])
        matched_terms = [t for t in SOFTWARE_ADDRESSABLE_TERMS if t in text.lower()]
        assert not matched_terms, (
            f"Harness record {rec['complaint_id']} matched SOFTWARE_ADDRESSABLE_TERMS "
            f"{matched_terms} — adjust text so it contains no software-addressable terms."
        )


# ---------------------------------------------------------------------------
# Verification stage
# ---------------------------------------------------------------------------

def test_harness_records_produce_verified_candidates(tmp_path):
    connector = RejectionHarnessConnector()
    retrieval = connector.retrieve()
    study = get_study("GS-CF001-C")
    candidates = normalise_cfpb_records(retrieval.records, retrieval.source, study)
    verified = verify_candidates(candidates)

    verified_candidates = [v for v in verified if v.verification_status == "verified_candidate"]
    assert len(verified_candidates) >= 3, (
        "Need at least 3 verified_candidates to form a supported finding."
    )
    # All verified should be operational
    for v in verified_candidates:
        assert v.operational is True
    # All verified should be NOT software-addressable (confirming the harness design)
    for v in verified_candidates:
        assert v.software_addressable is False, (
            f"Expected software_addressable=False for harness record {v.source_record_id}"
        )


# ---------------------------------------------------------------------------
# Full pipeline run
# ---------------------------------------------------------------------------

def test_rejection_harness_pipeline_produces_rejected_odr_entries(tmp_path):
    """Full pipeline run with harness connector produces REJECTED ODR entries."""
    connector = RejectionHarnessConnector()
    result = run_credit_reporting_proof(
        limit=len(_HARNESS_RECORDS),
        connector=connector,
        data_dir=tmp_path,
    )

    # Pipeline completed
    assert result.verdict is not None

    # Evidence ceiling is still CONTINUE RESEARCH
    assert result.verdict.evidence_ceiling == "CONTINUE RESEARCH"

    # At least one mechanism classification must be non_software_problem
    non_sw = [
        c for c in result.mechanism_classifications
        if c.category == "non_software_problem"
    ]
    assert len(non_sw) >= 1, (
        f"Expected at least one non_software_problem classification; "
        f"got: {[c.category for c in result.mechanism_classifications]}"
    )

    # ODR must contain at least one REJECTED entry
    rejected = [e for e in result.odr_entries if e.decision_status == "REJECTED"]
    assert len(rejected) >= 1, (
        f"Expected at least one REJECTED ODR entry; "
        f"all entries: {[e.decision_status for e in result.odr_entries]}"
    )


def test_rejection_harness_pipeline_ceiling_unchanged(tmp_path):
    """Evidence ceiling must remain CONTINUE RESEARCH regardless of rejection outcomes."""
    connector = RejectionHarnessConnector()
    result = run_credit_reporting_proof(
        limit=len(_HARNESS_RECORDS),
        connector=connector,
        data_dir=tmp_path,
    )
    assert result.verdict is not None
    assert result.verdict.evidence_ceiling == "CONTINUE RESEARCH"


def test_rejection_harness_mechanism_names_use_trigger_process_failure_format(tmp_path):
    """Correction 6: mechanism names must not use old broad-label format."""
    connector = RejectionHarnessConnector()
    result = run_credit_reporting_proof(
        limit=len(_HARNESS_RECORDS),
        connector=connector,
        data_dir=tmp_path,
    )
    old_names = {
        "credit_report_dispute_investigation",
        "incorrect_credit_report_information",
        "credit_report_documentation_handling",
        "credit_report_resolution_communication",
        "credit_reporting_dispute_handling",
    }
    for clf in result.mechanism_classifications:
        assert clf.mechanism not in old_names, (
            f"Old mechanism name '{clf.mechanism}' still in use — "
            "update MECHANISM_RULES in verification/rules.py."
        )


def test_rejection_harness_odr_entries_have_evidence_references(tmp_path):
    connector = RejectionHarnessConnector()
    result = run_credit_reporting_proof(
        limit=len(_HARNESS_RECORDS),
        connector=connector,
        data_dir=tmp_path,
    )
    for entry in result.odr_entries:
        assert len(entry.evidence_references) > 0


def test_rejection_harness_connector_access_method():
    connector = RejectionHarnessConnector()
    retrieval = connector.retrieve()
    assert retrieval.access_method == "rejection_harness_fixture"
    assert len(retrieval.records) == len(_HARNESS_RECORDS)
