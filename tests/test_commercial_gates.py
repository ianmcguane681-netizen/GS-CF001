"""PG-11 and PG-12 compute, and the wall between market and study evidence holds.

Both were pinned FAIL constants, like PG-09 and PG-13 before them. A pinned gate
cannot tell a study holding competitor research from one holding none, so it
enforces nothing and would pass silently if anyone flipped the constant.

The harder requirement is the separation. Market and buyer material answers "who
already solves this and who would pay". Study evidence answers "does this failure
occur". They arrive as separate parameters precisely so market material can never
reach the independent source family count and lift the evidence ceiling.
"""
from __future__ import annotations

from core.models import VerifiedEvidence
from proof_gates.evaluator import evaluate_proof_gates, make_verdict
from verification.rules import DEFAULT_MECHANISM


def study_evidence(index: int, family: str = "CFPB complaints") -> VerifiedEvidence:
    return VerifiedEvidence(
        evidence_id=f"EVD-{index}",
        candidate_id=f"CAN-{index}",
        study_id="GS-CF001-C",
        source_record_id=f"REC-{index}",
        company_name=f"Company {index}",
        verification_status="verified_candidate",
        operational=True,
        traceable=True,
        software_addressable=True,
        repeated_signal=True,
        independently_corrobored=False,
        mechanism="bureau_dispute_reinvestigation_failure",
        reasoning_chain=[],
        supporting_candidate_ids=[],
        missing_evidence=[],
        source_family=family,
    )


def gate(gates, gate_id):
    return next(item for item in gates if item.gate_id == gate_id)


IDENTIFIED_ONLY = {
    "competitor_id": "PRC-EXAMPLE",
    "name": "Example Vendor",
    "strengths": [],
    "weaknesses": [],
    "differentiation": "",
    "pricing": "published, not transcribed",
}
ASSESSED = {
    **IDENTIFIED_ONLY,
    "strengths": ["Established install base among credit repair firms"],
    "weaknesses": ["No audit trail on dispute handling"],
}
WILLING_BUYER = {
    "evidence_id": "BUY-1",
    "stated_willingness": "Would switch for a traceable evidence trail",
    "holds_budget_authority": True,
}


# --- PG-11: identification is not assessment ---------------------------------


def test_pg11_fails_with_no_competitor_research():
    gates = evaluate_proof_gates([study_evidence(1)], [], [])

    assert gate(gates, "PG-11").status == "FAIL"


def test_pg11_is_weak_when_an_incumbent_is_named_but_not_assessed():
    """A pricing observation identifies a vendor. It does not assess one."""
    gates = evaluate_proof_gates([study_evidence(1)], [], [], competitors=[IDENTIFIED_ONLY])

    result = gate(gates, "PG-11")
    assert result.status == "WEAK"
    assert "not assessing one" in " ".join(result.counter_evidence)


def test_pg11_passes_on_a_real_comparative_assessment():
    gates = evaluate_proof_gates([study_evidence(1)], [], [], competitors=[ASSESSED])

    assert gate(gates, "PG-11").status == "PASS"


def test_placeholder_comparative_fields_do_not_assess_anything():
    """The failure the board raised against G7, guarded here at the outset."""
    placeholders = {
        **IDENTIFIED_ONLY,
        "strengths": ["not assessed from regulatory filings"],
        "weaknesses": ["unknown"],
        "differentiation": "TBD",
    }

    gates = evaluate_proof_gates([study_evidence(1)], [], [], competitors=[placeholders])

    assert gate(gates, "PG-11").status == "WEAK"


def test_a_nameless_competitor_record_is_not_an_incumbent():
    gates = evaluate_proof_gates([study_evidence(1)], [], [], competitors=[{"name": "  "}])

    assert gate(gates, "PG-11").status == "FAIL"


# --- PG-12: a list price is not a willing buyer -------------------------------


def test_published_pricing_alone_does_not_pass_commercial_relevance():
    """Vendors charging money proves a market exists, not that anyone would move."""
    priced = {**ASSESSED, "pricing": "179.00 USD/month"}

    gates = evaluate_proof_gates([study_evidence(1)], [], [], competitors=[priced])

    result = gate(gates, "PG-12")
    assert result.status == "FAIL"
    assert "not that anyone would switch" in " ".join(result.counter_evidence)


def test_pg12_passes_only_on_a_budget_holding_buyer_stating_willingness():
    gates = evaluate_proof_gates([study_evidence(1)], [], [], buyer_evidence=[WILLING_BUYER])

    assert gate(gates, "PG-12").status == "PASS"


def test_a_buyer_without_budget_authority_is_not_commercial_relevance():
    without_budget = {**WILLING_BUYER, "holds_budget_authority": False}

    gates = evaluate_proof_gates([study_evidence(1)], [], [], buyer_evidence=[without_budget])

    assert gate(gates, "PG-12").status == "WEAK"


def test_a_placeholder_willingness_does_not_pass():
    vague = {**WILLING_BUYER, "stated_willingness": "unknown"}

    gates = evaluate_proof_gates([study_evidence(1)], [], [], buyer_evidence=[vague])

    assert gate(gates, "PG-12").status == "WEAK"


# --- The wall ------------------------------------------------------------------


def test_competitor_and_buyer_material_never_lift_the_evidence_ceiling():
    """The separation that makes the parameters separate.

    A study with one source family stays capped at CONTINUE RESEARCH no matter how
    much market and buyer material it holds, because neither answers whether the
    operational failure occurs.
    """
    evidence = [study_evidence(index) for index in range(1, 4)]

    gates = evaluate_proof_gates(
        evidence, [], [], competitors=[ASSESSED], buyer_evidence=[WILLING_BUYER]
    )
    verdict = make_verdict("GS-CF001-C", gates, [], [], evidence)

    assert verdict.independent_source_family_count == 1
    assert verdict.evidence_ceiling == "CONTINUE RESEARCH"
    assert verdict.outcome == "CONTINUE RESEARCH"
    assert gate(gates, "PG-11").status == "PASS"
    assert gate(gates, "PG-12").status == "PASS"


def test_market_material_cannot_be_smuggled_in_as_study_evidence():
    """It has no source_family and is not VerifiedEvidence, so there is no route."""
    from market.pricing import PricingObservation

    assert "source_family" not in PricingObservation.__dataclass_fields__
    assert not issubclass(PricingObservation, VerifiedEvidence)


def test_the_commercial_gates_do_not_depend_on_mechanism_classification():
    """They answer market questions, so an unclassified study is irrelevant to them."""
    unclassified = [
        VerifiedEvidence(
            **{**study_evidence(1).__dict__, "mechanism": DEFAULT_MECHANISM}
        )
    ]

    gates = evaluate_proof_gates(
        unclassified, [], [], competitors=[ASSESSED], buyer_evidence=[WILLING_BUYER]
    )

    assert gate(gates, "PG-11").status == "PASS"
    assert gate(gates, "PG-12").status == "PASS"
    assert gate(gates, "PG-09").status == "FAIL"
