"""Focused tests for findings/mechanism_classifier.py — six-category deterministic classification."""
from __future__ import annotations

import pytest

from core.ids import stable_id
from core.models import Finding, VerifiedEvidence
from findings.mechanism_classifier import (
    CATEGORY_DECISION_STATUS,
    EVIDENCE_CEILING_NOTE,
    MechanismCategory,
    classify_all,
    classify_finding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evidence(
    n: int,
    mechanism: str = "bureau_dispute_reinvestigation_failure",
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
            )
        )
    return items


def _finding(
    mechanism: str = "bureau_dispute_reinvestigation_failure",
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
    clf = classify_finding(finding, [])
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
# Category: non_software_problem — reachable now that software_addressable
# is not a gate on verified_candidate status (Correction 5)
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
# Category: repeated_complaint_signal (renamed from candidate_needs_corroboration)
# ---------------------------------------------------------------------------

def test_classify_repeated_complaint_signal_all_repeated():
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, operational=True, software_addressable=True, repeated_signal=True)
    clf = classify_finding(finding, ev)
    assert clf.category == "repeated_complaint_signal"
    assert clf.decision_status == "CONTINUE_RESEARCH"
    assert clf.all_repeated_signal


def test_repeated_complaint_signal_does_not_claim_verified_operational_reality():
    """Correction 1: the label and reasoning must not positively claim verified operational fact."""
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, repeated_signal=True)
    clf = classify_finding(finding, ev)
    # Category name must not contain "verified" as a positive claim
    assert clf.category == "repeated_complaint_signal"
    assert "verified_pain" not in clf.category
    # Label must not say "Verified pain" or "Verified [positive claim]"
    # (saying "unverified" in parens is fine — that's the caveat)
    label_lower = clf.category_label.lower()
    assert not label_lower.startswith("verified")
    assert "verified pain" not in label_lower
    # Reasoning must include the unverified-allegation caveat
    reasoning_text = " ".join(clf.classification_reasoning).lower()
    assert "unverified" in reasoning_text or "allegations" in reasoning_text


def test_repeated_complaint_signal_missing_for_upgrade_is_comprehensive():
    """Correction 3: missing_for_upgrade must cover all 7 advance requirements."""
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, repeated_signal=True)
    clf = classify_finding(finding, ev)
    combined = " ".join(clf.missing_for_upgrade).lower()
    # Check all 7 categories are represented
    assert "independent corroboration" in combined or "non-cfpb" in combined
    assert "buyer" in combined
    assert "cost" in combined or "financial" in combined
    assert "competitive" in combined or "existing solution" in combined
    assert "non-software" in combined
    assert "market" in combined
    assert "commercial" in combined or "willingness to pay" in combined


def test_repeated_complaint_signal_no_only_remaining_blocker_language():
    """Correction 2: 'only remaining blocker' language must not appear anywhere."""
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, repeated_signal=True)
    clf = classify_finding(finding, ev)
    full_text = (
        " ".join(clf.classification_reasoning)
        + " ".join(clf.missing_for_upgrade)
        + clf.evidence_ceiling_note
    )
    assert "only remaining blocker" not in full_text.lower()


# ---------------------------------------------------------------------------
# Category: partial_complaint_signal (renamed from verified_pain)
# ---------------------------------------------------------------------------

def test_classify_partial_complaint_signal_not_all_repeated():
    finding = _finding(evidence_count=5, company_count=3)
    ev_repeated = _evidence(3, operational=True, software_addressable=True, repeated_signal=True)
    ev_single = _evidence(2, operational=True, software_addressable=True, repeated_signal=False)
    clf = classify_finding(finding, ev_repeated + ev_single)
    assert clf.category == "partial_complaint_signal"
    assert clf.decision_status == "CONTINUE_RESEARCH"
    assert not clf.all_repeated_signal


def test_partial_complaint_signal_does_not_claim_verified_pain():
    """Correction 1: 'verified_pain' name is gone; label must not claim verified pain."""
    finding = _finding(evidence_count=5, company_count=3)
    ev_repeated = _evidence(3, repeated_signal=True)
    ev_single = _evidence(2, repeated_signal=False)
    clf = classify_finding(finding, ev_repeated + ev_single)
    assert clf.category == "partial_complaint_signal"
    label_lower = clf.category_label.lower()
    assert not label_lower.startswith("verified")
    assert "verified pain" not in label_lower


# ---------------------------------------------------------------------------
# Evidence ceiling note — Correction 1 tightened wording
# ---------------------------------------------------------------------------

def test_evidence_ceiling_note_includes_unverified_allegation_caveat():
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, repeated_signal=True)
    clf = classify_finding(finding, ev)
    note = clf.evidence_ceiling_note
    assert "unverified" in note.lower() or "allegations" in note.lower()
    assert "CONTINUE RESEARCH" in note
    assert "single source family" in note


# ---------------------------------------------------------------------------
# No "only remaining blocker" language anywhere (Correction 2)
# ---------------------------------------------------------------------------

def test_no_only_remaining_blocker_in_any_category():
    banned = "only remaining blocker"
    categories = [
        (_finding(evidence_count=5, company_count=3), _evidence(5, repeated_signal=True)),
        (_finding(evidence_count=5, company_count=3), _evidence(3, repeated_signal=True) + _evidence(2, repeated_signal=False)),
        (_finding(evidence_count=4, company_count=2, status="needs_more_evidence"), _evidence(4)),
        (_finding(evidence_count=4, company_count=2), _evidence(4, software_addressable=False)),
    ]
    for finding, ev in categories:
        clf = classify_finding(finding, ev)
        full = " ".join(clf.classification_reasoning + clf.missing_for_upgrade + [clf.evidence_ceiling_note])
        assert banned not in full.lower(), f"Found '{banned}' in {clf.category}"


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
    results = classify_all(findings, ev_a + ev_b)
    assert len(results) == 2
    by_finding = {r.finding_id: r for r in results}
    assert by_finding[findings[0].finding_id].category == "repeated_complaint_signal"
    assert by_finding[findings[1].finding_id].category == "noise"


def test_classify_all_empty_findings():
    assert classify_all([], []) == []


# ---------------------------------------------------------------------------
# Determinism
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

def test_borderline_note_emitted_when_majority_vote_within_10pp():
    """F-04 audit fix: borderline_note must be populated when the operational or
    software_addressable vote is within 10 percentage points of 50%."""
    # 5 items: 3 operational (60%) + 2 not → ratio = 0.60 → borderline band is 40-60%
    # 3/5 = 60% which is exactly at the boundary; let's use 4/9 = 44% for cleaner test
    finding = _finding(evidence_count=9, company_count=3)
    # 4 operational, 5 not → ratio = 4/9 ≈ 44% → within 10pp of 50% → borderline
    ev_op = _evidence(4, operational=True, software_addressable=False, repeated_signal=True)
    ev_no = _evidence(5, operational=False, software_addressable=False, repeated_signal=False)
    clf = classify_finding(finding, ev_op + ev_no)
    assert clf.category == "non_operational_problem"
    assert clf.borderline_note != ""
    assert "borderline" in clf.borderline_note.lower()
    assert "operational" in clf.borderline_note.lower()


def test_borderline_note_empty_when_clear_majority():
    """When vote is far from 50%, borderline_note must be empty."""
    finding = _finding(evidence_count=5, company_count=3)
    ev = _evidence(5, operational=True, software_addressable=True, repeated_signal=True)
    clf = classify_finding(finding, ev)
    # 5/5 = 100% operational, 100% software_addressable — far from borderline
    assert clf.borderline_note == ""


def test_borderline_note_for_software_addressable_vote():
    """borderline_note must mention software_addressable when that vote is borderline."""
    finding = _finding(evidence_count=9, company_count=3)
    # All operational; 4/9 ≈ 44% software_addressable → borderline sw vote
    ev_sw = _evidence(4, operational=True, software_addressable=True, repeated_signal=True)
    ev_no = _evidence(5, operational=True, software_addressable=False, repeated_signal=True)
    clf = classify_finding(finding, ev_sw + ev_no)
    assert clf.category == "non_software_problem"
    assert clf.borderline_note != ""
    assert "software_addressable" in clf.borderline_note.lower()


def test_all_categories_have_decision_status():
    all_cats = [
        "repeated_complaint_signal",
        "partial_complaint_signal",
        "commercially_weak",
        "non_software_problem",
        "non_operational_problem",
        "noise",
    ]
    for cat in all_cats:
        assert cat in CATEGORY_DECISION_STATUS
        assert CATEGORY_DECISION_STATUS[cat] in ("CONTINUE_RESEARCH", "REJECTED")


def test_rejected_categories():
    assert CATEGORY_DECISION_STATUS["non_software_problem"] == "REJECTED"
    assert CATEGORY_DECISION_STATUS["non_operational_problem"] == "REJECTED"
    assert CATEGORY_DECISION_STATUS["noise"] == "REJECTED"
