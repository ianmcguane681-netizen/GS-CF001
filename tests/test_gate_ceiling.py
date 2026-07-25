"""The all-gates-pass rule must be enforced, not merely asserted in prose.

make_verdict's reasoning chain has always claimed that no positive build decision
is permitted unless every proof gate passes, but nothing inspected the gate
statuses. The rule held only because the unconstrained outcome never exceeded
CONTINUE RESEARCH. These tests pin the rule to the gate statuses directly, so a
future change to the unconstrained path cannot bypass it silently.
"""
from __future__ import annotations

from dataclasses import replace

from proof_gates.evaluator import gate_ceiling, make_verdict
from tests.test_opportunity_and_proof_gates import pipeline_objects


def all_passing(gates):
    return [replace(gate, status="PASS", constrains_max_verdict=False) for gate in gates]


def test_gate_ceiling_caps_when_a_gate_fails():
    _v, _f, _o, gates, _verdict = pipeline_objects()

    ceiling, reasons = gate_ceiling(gates)

    assert ceiling == "CONTINUE RESEARCH"
    assert any("not passing" in reason for reason in reasons)


def test_gate_ceiling_lifts_only_when_every_gate_passes_and_none_constrain():
    _v, _f, _o, gates, _verdict = pipeline_objects()

    ceiling, reasons = gate_ceiling(all_passing(gates))

    assert ceiling == "BUILD CANDIDATE"
    assert reasons == []


def test_a_constraining_gate_caps_even_when_all_gates_pass():
    _v, _f, _o, gates, _verdict = pipeline_objects()
    passing = all_passing(gates)
    passing[-1] = replace(passing[-1], constrains_max_verdict=True)

    ceiling, reasons = gate_ceiling(passing)

    assert ceiling == "CONTINUE RESEARCH"
    assert any("constraining" in reason for reason in reasons)


def test_verdict_records_why_the_gate_ceiling_applied():
    _v, findings, opportunities, gates, _verdict = pipeline_objects()

    verdict = make_verdict("GS-CF001-C", gates, findings, opportunities)

    assert verdict.outcome == "CONTINUE RESEARCH"
    assert any("not passing" in line for line in verdict.reasoning_chain)


def test_failing_gates_cap_the_verdict_even_with_two_source_families():
    """Two source families lift the evidence ceiling; failing gates must still cap."""
    verified, findings, opportunities, gates, _verdict = pipeline_objects()
    multi_family = [
        replace(item, source_family="CFPB complaints" if index % 2 else "State regulator")
        for index, item in enumerate(verified)
    ]

    verdict = make_verdict("GS-CF001-C", gates, findings, opportunities, multi_family)

    assert verdict.evidence_ceiling == "BUILD CANDIDATE"
    assert verdict.outcome == "CONTINUE RESEARCH"
