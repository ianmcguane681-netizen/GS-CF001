"""No gate may pass on placeholder values.

The review board raised this twice. First G7 passed on competitor records that
said "not assessed". Then PG-09 passed because an adjudication and a complaint
matched each other on *both being unclassified* -- two records agreeing that
neither had been classified, counted as corroboration. Tests were green both
times, because every test supplied realistic data.

That is the shape of the bug: a sentinel value meaning "we do not know" gets
compared, counted, or truthiness-checked as though it were an answer. It cannot
be caught by tests that only ever feed good input, so this module feeds the
worst input the pipeline can legitimately produce -- a complete run in which
nothing was ever classified -- and asserts what must not pass.

Adding a gate means adding it here. A gate that passes on this dataset is
either wrong or has to justify itself in EXPECTED_PASS below.
"""
from __future__ import annotations

from core.models import VerifiedEvidence
from findings.engine import generate_findings
from opportunity.assessment import assess_findings
from proof_gates.evaluator import evaluate_proof_gates, make_verdict
from verification.rules import DEFAULT_MECHANISM

# Gates that may legitimately pass with nothing classified, and why. Each entry
# is a claim that the gate does not depend on classification at all.
EXPECTED_PASS = {
    "PG-01": "Source reliability assessments exist per connector, independent of any record's content.",
    "PG-02": "Preservation is satisfied by raw artefacts or by diagnostics; preserving a failed retrieval is the point.",
    "PG-03": "Normalised candidates exist. Whether they classify is a later question.",
    "PG-04": "Every record maps to the implemented study. Study mapping is not mechanism classification.",
    "PG-06": "Company names are real values read from source records, not placeholders.",
    "PG-14": "Reproducibility depends on artefacts and diagnostics, not on record content.",
    "PG-15": "Source family is assigned by the connector and is a real value; independence of origin does not depend on whether a record classified.",
    "PG-16": "The ceiling rule reports itself as applied; it is a rule, not an assessment.",
}


def unclassified(index: int, company: str) -> VerifiedEvidence:
    """A record that verified cleanly and classified to nothing.

    Every field a gate might read is populated and plausible. Only the mechanism
    is the fallback -- which is exactly the live three-source run.
    """

    return VerifiedEvidence(
        evidence_id=f"EVD-{index}",
        candidate_id=f"CAN-{index}",
        study_id="GS-CF001-C",
        source_record_id=f"REC-{index}",
        company_name=company,
        verification_status="verified_candidate",
        operational=True,
        traceable=True,
        software_addressable=True,
        repeated_signal=True,
        independently_corrobored=False,
        mechanism=DEFAULT_MECHANISM,
        reasoning_chain=[],
        supporting_candidate_ids=[f"CAN-{index}"],
        missing_evidence=[],
        source_family="CFPB complaints" if index % 2 else "Federal court records",
        date_received=f"2026-01-{index:02d}",
    )


def all_placeholder_run():
    evidence = [unclassified(index, f"Company {index % 3}") for index in range(1, 9)]
    findings = generate_findings(evidence)
    opportunities = assess_findings(findings)
    return evidence, findings, opportunities


def test_no_gate_passes_on_a_wholly_unclassified_run():
    """The systemic guard. Every unexplained PASS here is a bug."""
    evidence, findings, opportunities = all_placeholder_run()

    gates = evaluate_proof_gates(evidence, findings, opportunities)
    passed = {gate.gate_id for gate in gates if gate.status == "PASS"}

    unexplained = sorted(passed - set(EXPECTED_PASS))
    assert not unexplained, (
        f"gates passed with nothing classified: {unexplained}. "
        "Either the gate reads a placeholder as an answer, or it belongs in EXPECTED_PASS."
    )


def test_the_three_gates_the_board_would_have_been_shown():
    """PG-05, PG-07 and PG-08 all read finding status, so one placeholder
    finding passed all three at once: repetition of nothing in particular, an
    'operational mechanism definition' reading "Unclassified mechanism", and a
    component hypothesis reading "no supported component yet"."""
    evidence, findings, opportunities = all_placeholder_run()

    gates = {gate.gate_id: gate for gate in evaluate_proof_gates(evidence, findings, opportunities)}

    assert gates["PG-05"].status == "FAIL"
    assert gates["PG-07"].status == "FAIL"
    assert gates["PG-08"].status != "PASS"


def test_an_unclassified_group_is_not_a_supported_finding():
    """Fixed at the source: a finding is a claim about a mechanism."""
    _evidence, findings, opportunities = all_placeholder_run()

    assert findings and all(item.status == "needs_more_evidence" for item in findings)
    assert all("an identified operational mechanism" in item.missing_evidence for item in findings)
    assert all(item.status == "unproven" for item in opportunities)


def test_the_verdict_cannot_reach_build_candidate_on_placeholders():
    evidence, findings, opportunities = all_placeholder_run()

    verdict = make_verdict(
        "GS-CF001-C", evaluate_proof_gates(evidence, findings, opportunities), findings, opportunities, evidence
    )

    assert verdict.outcome == "CONTINUE RESEARCH"
    assert verdict.occurrence_established_count == 0


def test_a_classified_run_still_passes_the_same_gates():
    """The guard must not work by making everything fail."""
    evidence = [
        VerifiedEvidence(
            **{
                **unclassified(index, f"Company {index % 3}").__dict__,
                "mechanism": "bureau_dispute_reinvestigation_failure",
            }
        )
        for index in range(1, 9)
    ]
    findings = generate_findings(evidence)
    gates = {
        gate.gate_id: gate.status
        for gate in evaluate_proof_gates(evidence, findings, assess_findings(findings))
    }

    assert findings[0].status == "finding_supported_cfpb_only"
    assert gates["PG-05"] == "PASS"
    assert gates["PG-07"] == "PASS"
    assert gates["PG-08"] == "PASS"
