"""Federal court records as a second, independent source family.

CFPB complaints could never lift the evidence ceiling on their own, because every
CFPB distribution method is one source family. These tests pin the properties that
make dockets genuinely independent, and the deterministic rule that admits them.
"""
from __future__ import annotations

from typing import Any

from connectors.cfpb import cfpb_source
from connectors.courtlistener import (
    CourtListenerConnector,
    CourtListenerSearchAdapter,
    cites_fcra,
    courtlistener_source,
)
from core.normalization import normalise_court_record, normalise_court_records
from studies.definitions import get_study

STUDY = get_study("GS-CF001-C")


def docket(
    docket_id: str,
    case_name: str,
    cause: str = "15:1681 Fair Credit Reporting Act",
    suit_nature: str = "480 Other Statutes: Consumer Credit",
) -> dict[str, Any]:
    return {
        "docket_id": docket_id,
        "caseName": case_name,
        "case_name_full": case_name,
        "court": "District Court, E.D. Pennsylvania",
        "court_id": "paed",
        "docketNumber": f"2:26-cv-{docket_id}",
        "dateFiled": "2026-07-24",
        "dateTerminated": None,
        "cause": cause,
        "suitNature": suit_nature,
        "jurisdictionType": "Federal Question",
        "assignedTo": "A Judge",
        "party": ["A Plaintiff", case_name.split(" v. ")[-1]],
        "docket_absolute_url": f"/docket/{docket_id}/x/",
    }


def payload(*rows: dict[str, Any]) -> dict[str, Any]:
    return {"count": len(rows), "results": list(rows)}


def adapter_for(*rows: dict[str, Any]) -> CourtListenerSearchAdapter:
    return CourtListenerSearchAdapter(
        fetch_json=lambda _url: (payload(*rows), {"Content-Type": "application/json"}, "200")
    )


def test_court_records_are_a_different_source_family_from_cfpb():
    """This is the property that lifts the evidence ceiling."""
    assert courtlistener_source().source_family != cfpb_source().source_family
    assert courtlistener_source().source_family == "Federal court records"


def test_fcra_statute_admission_is_deterministic():
    assert cites_fcra("15:1681 Fair Credit Reporting Act") is True
    assert cites_fcra("", "480 Other Statutes: Consumer Credit 1681") is True
    assert cites_fcra("15:1692 Fair Debt Collection Practices Act") is False
    assert cites_fcra("", "") is False


def test_non_fcra_dockets_are_not_retrieved():
    adapter = adapter_for(
        docket("1", "A v. B", cause="15:1692 Fair Debt Collection Practices Act", suit_nature="890"),
        docket("2", "C v. TRANS UNION, LLC"),
    )

    _url, records, errors, _diag = adapter.retrieve(limit=10)

    assert errors == []
    assert [item["docket_id"] for item in records] == ["2"]


def test_non_fcra_docket_is_not_normalised():
    raw = {"docket_id": "9", "cause": "15:1692 Fair Debt Collection", "suit_nature": "890"}

    assert normalise_court_record(raw, courtlistener_source(), STUDY) is None


def test_normalisation_records_cause_and_defendant():
    _url, records, _errors, _diag = adapter_for(docket("5", "WILLIAMS v. EQUIFAX INFORMATION SERVICES LLC")).retrieve(10)

    candidate = normalise_court_record(records[0], courtlistener_source(), STUDY)

    assert candidate is not None
    assert candidate.parsed_fields["cause"] == "15:1681 Fair Credit Reporting Act"
    assert candidate.parsed_fields["company"] == "EQUIFAX INFORMATION SERVICES LLC"
    assert candidate.parsed_fields["docket_number"] == "2:26-cv-5"
    assert candidate.study.study_id == "GS-CF001-C"


def test_docket_metadata_carries_no_consumer_narrative():
    """A case caption is not a first-hand account and must not be mined as one."""
    _url, records, _errors, _diag = adapter_for(docket("6", "X v. TRANS UNION, LLC")).retrieve(10)

    candidate = normalise_court_record(records[0], courtlistener_source(), STUDY)

    assert candidate is not None
    assert candidate.parsed_fields["narrative"] == ""


def test_retrieval_attaches_reliability_assessment_and_diagnostics():
    connector = CourtListenerConnector(access_adapter=adapter_for(docket("7", "Y v. Z BANK")))

    result = connector.retrieve(limit=5)

    assert result.errors == []
    assert result.source_reliability is not None
    assert result.source_reliability.source_family == "Federal court records"
    assert "A filed complaint states allegations, not established facts." in (
        result.source_reliability.known_limitations
    )
    assert result.diagnostics and result.diagnostics[0].response_status == "200"
    assert result.records[0]["_retrieved_at"]


def test_transport_failure_becomes_a_diagnostic_not_an_exception():
    def failing(_url: str):
        raise TimeoutError("connection timed out")

    connector = CourtListenerConnector(
        access_adapter=CourtListenerSearchAdapter(fetch_json=failing)
    )

    result = connector.retrieve(limit=1)

    assert result.records == []
    assert result.errors and "connection timed out" in result.errors[0]
    assert result.diagnostics[0].response_status == "error"


def test_limit_is_respected():
    adapter = adapter_for(*[docket(str(index), f"P{index} v. TRANS UNION, LLC") for index in range(10)])

    _url, records, _errors, _diag = adapter.retrieve(limit=3)

    assert len(records) == 3


def test_two_source_families_lift_the_evidence_ceiling():
    from connectors.cfpb import cfpb_source as cfpb
    from core.normalization import normalise_cfpb_record
    from findings.engine import generate_findings
    from opportunity.assessment import assess_findings
    from proof_gates.evaluator import evaluate_proof_gates, make_verdict
    from verification.classifier import verify_candidates

    complaint = normalise_cfpb_record(
        {
            "complaint_id": "1",
            "product": "Credit reporting or other personal consumer reports",
            "issue": "Incorrect information on your report",
            "company": "A",
            "complaint_what_happened": (
                "My dispute investigation failed to remove inaccurate information."
            ),
            "_retrieval_url": "https://consumerfinance.gov/api",
            "_retrieved_at": "2026-07-25T00:00:00Z",
        },
        cfpb(),
        STUDY,
    )
    _url, rows, _errors, _diag = adapter_for(docket("8", "W v. TRANS UNION, LLC")).retrieve(10)
    dockets = normalise_court_records(rows, courtlistener_source(), STUDY)

    def ceiling(candidates):
        verified = verify_candidates(candidates)
        findings = generate_findings(verified)
        opportunities = assess_findings(findings)
        gates = evaluate_proof_gates(verified, findings, opportunities)
        verdict = make_verdict("GS-CF001-C", gates, findings, opportunities, verified)
        return verdict, gates

    cfpb_only, cfpb_gates = ceiling([complaint])
    combined, combined_gates = ceiling([complaint, *dockets])

    assert cfpb_only.evidence_ceiling == "CONTINUE RESEARCH"
    assert [g.status for g in cfpb_gates if g.gate_id == "PG-15"] == ["FAIL"]

    assert combined.independent_source_family_count == 2
    assert combined.evidence_ceiling == "BUILD CANDIDATE"
    assert [g.status for g in combined_gates if g.gate_id == "PG-15"] == ["PASS"]
    # Other gates still fail, so the verdict itself must not advance.
    assert combined.outcome == "CONTINUE RESEARCH"
