"""Focused tests for core/opportunity_decision_register.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.ids import stable_id
from core.models import Finding, OpportunityHypothesis
from core.opportunity_decision_register import (
    ODREntry,
    OpportunityDecisionRegister,
    build_odr,
    build_odr_entry,
    write_odr_json,
    write_odr_markdown,
)
from findings.mechanism_classifier import (
    EVIDENCE_CEILING_NOTE,
    MechanismClassification,
    classify_finding,
)
from core.models import VerifiedEvidence, Source, Study


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(
    mechanism: str = "credit_report_dispute_investigation",
    evidence_count: int = 5,
    company_count: int = 3,
    status: str = "finding_supported_cfpb_only",
) -> Finding:
    companies = [f"Co{i}" for i in range(company_count)]
    evidence_ids = [f"EVD-{i:03d}" for i in range(evidence_count)]
    return Finding(
        finding_id=stable_id("FND", {"m": mechanism, "ec": evidence_count}),
        study_id="GS-CF001-C",
        mechanism=mechanism,
        status=status,
        evidence_ids=evidence_ids,
        companies=companies,
        evidence_count=evidence_count,
        company_count=company_count,
        summary="Test",
        missing_evidence=[],
        reasoning_chain=["test"],
    )


def _opportunity(finding_id: str) -> OpportunityHypothesis:
    return OpportunityHypothesis(
        opportunity_id=stable_id("OPP", {"fid": finding_id}),
        finding_id=finding_id,
        status="hypothesis_only",
        component_hypothesis="Dispute workflow component",
        buyer_clarity="weak",
        commercial_relevance="unproven",
        existing_solution_maturity="unknown",
        component_reusability="plausible",
        market_saturation="unknown",
        implementation_leverage="unknown",
    )


def _evidence_for(finding: Finding, repeated: bool = True) -> list[VerifiedEvidence]:
    items = []
    for i, eid in enumerate(finding.evidence_ids):
        items.append(VerifiedEvidence(
            evidence_id=eid,
            candidate_id=f"CAN-{i:03d}",
            study_id="GS-CF001-C",
            source_record_id=str(i),
            company_name=finding.companies[i % len(finding.companies)],
            verification_status="verified_candidate",
            operational=True,
            traceable=True,
            software_addressable=True,
            repeated_signal=repeated,
            independently_corrobored=False,
            mechanism=finding.mechanism,
            reasoning_chain=["test"],
            supporting_candidate_ids=[f"CAN-{i:03d}"],
            missing_evidence=[],
        ))
    return items


def _classification(finding: Finding, repeated: bool = True) -> MechanismClassification:
    ev = _evidence_for(finding, repeated=repeated)
    return classify_finding(finding, ev)


# ---------------------------------------------------------------------------
# build_odr_entry
# ---------------------------------------------------------------------------

def test_odr_entry_has_required_fields():
    f = _finding()
    opp = _opportunity(f.finding_id)
    clf = _classification(f)
    entry = build_odr_entry(f, opp, clf)

    assert entry.odr_id
    assert entry.mechanism == f.mechanism
    assert entry.finding_id == f.finding_id
    assert entry.opportunity_id == opp.opportunity_id
    assert entry.evidence_count == f.evidence_count
    assert entry.company_count == f.company_count
    assert entry.evidence_ceiling_note == EVIDENCE_CEILING_NOTE
    assert entry.decision_status in ("REJECTED", "CONTINUE_RESEARCH")
    assert len(entry.decision_rationale) > 0


def test_odr_entry_decision_status_continue_research_for_candidate():
    f = _finding(evidence_count=5, company_count=3)
    opp = _opportunity(f.finding_id)
    clf = _classification(f, repeated=True)
    entry = build_odr_entry(f, opp, clf)
    assert entry.decision_status == "CONTINUE_RESEARCH"


def test_odr_entry_decision_status_rejected_for_noise():
    f = _finding(evidence_count=1, company_count=1)
    opp = _opportunity(f.finding_id)
    clf = classify_finding(f, [])  # no evidence → noise
    entry = build_odr_entry(f, opp, clf)
    assert entry.decision_status == "REJECTED"


def test_odr_entry_is_deterministic():
    f = _finding()
    opp = _opportunity(f.finding_id)
    clf = _classification(f)
    e1 = build_odr_entry(f, opp, clf)
    e2 = build_odr_entry(f, opp, clf)
    assert e1.odr_id == e2.odr_id
    assert e1.decision_status == e2.decision_status


# ---------------------------------------------------------------------------
# build_odr
# ---------------------------------------------------------------------------

def test_build_odr_empty_run():
    odr = build_odr("GS-CF001-C", "RUN-TEST", [], [], [])
    assert odr.entry_count == 0
    assert odr.rejected_count == 0
    assert odr.continue_research_count == 0
    assert odr.methodology_note
    assert "CONTINUE RESEARCH" in odr.evidence_ceiling_note


def test_build_odr_counts_correctly():
    f1 = _finding("mech_A", 5, 3)
    f2 = _finding("mech_B", 1, 1, status="needs_more_evidence")
    opp1 = _opportunity(f1.finding_id)
    opp2 = _opportunity(f2.finding_id)
    clf1 = _classification(f1, repeated=True)
    clf2 = classify_finding(f2, [])

    odr = build_odr("GS-CF001-C", "RUN-TEST", [f1, f2], [opp1, opp2], [clf1, clf2])
    assert odr.entry_count == 2
    assert odr.continue_research_count == 1
    assert odr.rejected_count == 1


def test_build_odr_contains_evidence_ceiling():
    f = _finding()
    opp = _opportunity(f.finding_id)
    clf = _classification(f)
    odr = build_odr("GS-CF001-C", "RUN-TEST", [f], [opp], [clf])
    assert odr.evidence_ceiling == "CONTINUE RESEARCH"
    assert "single source family" in odr.evidence_ceiling_note


def test_build_odr_no_ai_methodology_note():
    odr = build_odr("GS-CF001-C", "RUN-TEST", [], [], [])
    assert "No AI" in odr.methodology_note
    assert "deterministic" in odr.methodology_note.lower()


def test_build_odr_entries_have_evidence_references():
    f = _finding()
    opp = _opportunity(f.finding_id)
    clf = _classification(f)
    odr = build_odr("GS-CF001-C", "RUN-TEST", [f], [opp], [clf])
    assert odr.entries[0].evidence_references == f.evidence_ids


# ---------------------------------------------------------------------------
# write_odr_json
# ---------------------------------------------------------------------------

def test_write_odr_json_is_valid_json(tmp_path):
    f = _finding()
    opp = _opportunity(f.finding_id)
    clf = _classification(f)
    odr = build_odr("GS-CF001-C", "RUN-TEST", [f], [opp], [clf])
    path = tmp_path / "odr.json"
    write_odr_json(odr, path)
    data = json.loads(path.read_text())
    assert data["study_id"] == "GS-CF001-C"
    assert "entries" in data
    assert data["evidence_ceiling"] == "CONTINUE RESEARCH"


# ---------------------------------------------------------------------------
# write_odr_markdown
# ---------------------------------------------------------------------------

def test_write_odr_markdown_contains_required_sections(tmp_path):
    f = _finding()
    opp = _opportunity(f.finding_id)
    clf = _classification(f)
    odr = build_odr("GS-CF001-C", "RUN-TEST", [f], [opp], [clf])
    path = tmp_path / "odr.md"
    write_odr_markdown(odr, path)
    md = path.read_text()
    assert "Opportunity Decision Register" in md
    assert "Evidence Ceiling" in md
    assert "CONTINUE RESEARCH" in md
    assert "Methodology note" in md
    assert "No AI" in md
    assert "Decision table" in md
    assert odr.entries[0].odr_id in md


def test_write_odr_markdown_empty_run(tmp_path):
    odr = build_odr("GS-CF001-C", "RUN-TEST", [], [], [])
    path = tmp_path / "odr_empty.md"
    write_odr_markdown(odr, path)
    md = path.read_text()
    assert "No ODR entries" in md
