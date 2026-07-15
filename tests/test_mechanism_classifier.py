"""Focused tests for findings/mechanism_classifier.py — six-category deterministic classification."""
from __future__ import annotations

import pytest

from core.models import Finding, VerifiedEvidence, Source, Study
from core.ids import stable_id
from findings.mechanism_classifier import (
    MechanismCategory,
    classify_finding,
    classify_all,
    CATEGORY_DECISION_STATUS,
    EVIDENCE_CEILING_NOTE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source() -> Source:
    return Source(
        source_id="CFPB-CCD-001",
        name="CFPB",
        source_type="public_consumer_complaint_database",
        base_url="https://cfpb.gov",
        jurisdiction="US",
        role="discovery",
        source_family="CFPB complaints",
    )


def _study() -> Study:
    return Study(
        study_id="GS-CF001-C",
        title="Credit Reporting Disputes",
        research_question="Test?",
        implemented=True,
    )


def _evidence(
    n: int,
    mechanism: str = "credit_report_dispute_investigation",
    *,
    operational: bool = True,
    software_addressable: bool = True,
    repeated_signal: bool = True,
    companies: list[str] | None = None,
) -> list[VerifiedEvidence]:
    companies = companies or [f"Company{i % 3}" for i in range(n)]
    items = []
    for i in range(n):
        items.append(
            VerifiedEvidence(
                evidence_id=stable_id("EVD", {"i": i, "mech": mechanism}),
                candidate_id=f"CAN-{i:03d}",
                study_id="GS-CF001-C",
                source_record_id=str(i),
                company_name=companies[i % len(companies)],
                verification_status="verified_candidate",
                operational=operational,
                traceable=True,
                software_addressable=software_addressable,
                repeated_signal=repeated_signal,
                independently_corrobored=False,
                mechanism=mechanism,
                reasoning_chain=["test"],
                supporting_candidate_ids=[f"CAN-{i:03d}"],
                missing_evidence=[],
                source_family="CFPB complaints",
                product="Credit reporting",
                issue="Incorrect information",
                date_received="2024-01-01",
            )
        )
    return items


def _finding(
    mechanism: str = "credit_report_dispute_investigation",
    evidence_count: int = 5,
    company_count: int = 3,
    status: str = "finding_supported_cfpb_only",
    companies: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> Finding:
    companies = companies or [f"Company{i}" for i in range(company_count)]
    evidence_ids = evidence_ids or [f"EVD-{i:03d}" for i in range(evidence_count)]
    return Finding(
        finding_id=stable_id("FND", {"m": mechanism, "ec": evidence_count}),
        study_id="GS-CF001-C",
        mechanism=mechanism,
        status=status,
        evidence_ids=evidence_ids,
        companies=companies,
        evidence_count=evidence_count,
        company_count=company_count,
        summary="Test finding",
        missing_evidence=[],
        reasoning_chain=["test"],
    )


# ---------------------------------------------------------------------------
# Category: noise
# ---------------------------------------------------------------------------

def test_classify_noise_when_zero_verified_items():
    finding = _finding(evidence_count=1, company_count=1)
    clf = classify_finding(finding, [])  # no evidence passed
    assert clf.category == "noise"
    assert clf.decision_status == "REJECTED"


def test_classify_noise_when_one_verified_item():
    finding = _finding(evidence_count=1, company_count=1)
    ev = _evidence(1, repeated_signal=False)
    clf = classify_finding(finding, ev)
    assert clf.category == "noise"
    assert clf.decision_status == "REJECTED"


# ---------------------------------------------------------------------------
# Category: non_operational_problem
# ---------------------------------------------------------------------------

def test_classify_non_operational_when_majority_not_operational():
    finding = _finding(evidence_count=3, company_count=2)
    ev = _evidence(3, operational=False)
    clf = classify_finding(finding, ev)
    assert clf.category == "non_operational_problem"
    assert clf.decision_status == "REJECTED"
    assert not clf.majority_operational


# ---------------------------------------------------------------------------
# Category: non_software_problem
# ---------------------------------------------------------------------------

def test_classify_non_software_when_not_software_addressable():
    finding = _finding(evidence_count=4, company_count=2)
    ev = _evidence(4, operational=True, software_addressable=False)
    clf = classify_finding(finding, ev)
    assert clf.category == "non_software_problem"
    assert clf.decision_status == "REJECTED"
    assert clf.majority_operational
    assert not clf.majority_software_addressable


# ---------------------------------------------------------------------------
# Category: commercially_weak
# ---------------------------------------------------------------------------

def test_classify_commercially_weak_single_company():
    finding = _finding(evidence_count=5, company_count=1, companies=["Solo Corp"])
    ev = _evidence(5, operational=True, software_addressable=True, companies=["Solo Corp"])
    clf = classify_finding(finding, ev)
    assert clf.category == "commercially_weak"
    assert clf.decision_status == "CONTINUE_RESEARCH"


def test_classify_commercially_weak_low_evidence_count():
    finding = _finding(evidence_count=2, company_count=2)
    ev = _evidence(2, operational=True, software_addressable=True)
    clf = classify_finding(finding, ev)
    assert clf.category == "commercially_weak"


def test_classify_commercially_weak_when_status_not_supported():
    finding = _finding(evidence_count=5, company_count=3, status="needs_more_evidence")
    ev = _evidence(5, operational=True, software_addressable=True)
    clf = classify_finding(finding, ev)
    assert clf.category == "commercially_weak"


# ---------------------------------------------------------------------------
# Category: candidate_needs_corroboration
# ---------------------------------------------------------------------------

def test_classify_candidate_needs_corroboration_all_repeated():
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, operational=True, software_addressable=True, repeated_signal=True)
    clf = classify_finding(finding, ev)
    assert clf.category == "candidate_needs_corroboration"
    assert clf.decision_status == "CONTINUE_RESEARCH"
    assert clf.all_repeated_signal
    assert "second independent source family" in clf.missing_for_upgrade[0]


# ---------------------------------------------------------------------------
# Category: verified_pain
# ---------------------------------------------------------------------------

def test_classify_verified_pain_not_all_repeated():
    finding = _finding(evidence_count=5, company_count=3)
    ev_repeated = _evidence(3, operational=True, software_addressable=True, repeated_signal=True)
    ev_single = _evidence(2, operational=True, software_addressable=True, repeated_signal=False)
    clf = classify_finding(finding, ev_repeated + ev_single)
    assert clf.category == "verified_pain"
    assert clf.decision_status == "CONTINUE_RESEARCH"
    assert not clf.all_repeated_signal


# ---------------------------------------------------------------------------
# Evidence ceiling note always present
# ---------------------------------------------------------------------------

def test_evidence_ceiling_note_always_present():
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, repeated_signal=True)
    clf = classify_finding(finding, ev)
    assert clf.evidence_ceiling_note == EVIDENCE_CEILING_NOTE
    assert "CONTINUE RESEARCH" in clf.evidence_ceiling_note
    assert "single source family" in clf.evidence_ceiling_note


# ---------------------------------------------------------------------------
# classify_all
# ---------------------------------------------------------------------------

def test_classify_all_returns_one_per_finding():
    findings = [
        _finding("mechanism_A", evidence_count=5, company_count=3),
        _finding("mechanism_B", evidence_count=1, company_count=1),
    ]
    ev_a = _evidence(5, mechanism="mechanism_A", repeated_signal=True)
    ev_b = _evidence(1, mechanism="mechanism_B")
    all_ev = ev_a + ev_b
    results = classify_all(findings, all_ev)
    assert len(results) == 2
    by_finding = {r.finding_id: r for r in results}
    assert by_finding[findings[0].finding_id].category == "candidate_needs_corroboration"
    assert by_finding[findings[1].finding_id].category == "noise"


def test_classify_all_empty_findings():
    results = classify_all([], [])
    assert results == []


# ---------------------------------------------------------------------------
# Determinism: same inputs → same output
# ---------------------------------------------------------------------------

def test_classification_is_deterministic():
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, repeated_signal=True)
    clf1 = classify_finding(finding, ev)
    clf2 = classify_finding(finding, ev)
    assert clf1.classification_id == clf2.classification_id
    assert clf1.category == clf2.category


# ---------------------------------------------------------------------------
# CATEGORY_DECISION_STATUS coverage
# ---------------------------------------------------------------------------

def test_all_categories_have_decision_status():
    all_cats = [
        "candidate_needs_corroboration",
        "verified_pain",
        "commercially_weak",
        "non_software_problem",
        "non_operational_problem",
        "noise",
    ]
    for cat in all_cats:
        assert cat in CATEGORY_DECISION_STATUS
        assert CATEGORY_DECISION_STATUS[cat] in ("CONTINUE_RESEARCH", "REJECTED")
