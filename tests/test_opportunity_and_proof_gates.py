from connectors.cfpb import cfpb_source
from core.normalization import normalise_cfpb_record
from findings.engine import generate_findings
from opportunity.assessment import assess_findings
from proof_gates.evaluator import evaluate_proof_gates, make_verdict
from reports.report_generator import render_markdown_report
from studies.definitions import get_study
from verification.classifier import verify_candidates


def candidate(complaint_id: str, company: str):
    return normalise_cfpb_record(
        {
            "complaint_id": complaint_id,
            "product": "Credit reporting or other personal consumer reports",
            "issue": "Incorrect information on your report",
            "company": company,
            "complaint_what_happened": "My dispute investigation failed to remove inaccurate information from my credit report.",
            "_retrieval_url": "https://consumerfinance.gov/api",
            "_retrieved_at": "2026-07-14T00:00:00Z",
        },
        cfpb_source(),
        get_study("GS-CF001-C"),
    )


def pipeline_objects():
    verified = verify_candidates([candidate("1", "A"), candidate("2", "B"), candidate("3", "C")])
    findings = generate_findings(verified)
    opportunities = assess_findings(findings)
    gates = evaluate_proof_gates(verified, findings, opportunities)
    verdict = make_verdict("GS-CF001-C", gates, findings, opportunities)
    return verified, findings, opportunities, gates, verdict


def test_opportunity_assessment_is_separate_and_remains_hypothesis_only():
    _verified, findings, opportunities, _gates, _verdict = pipeline_objects()

    assert findings[0].status == "finding_supported_cfpb_only"
    assert opportunities[0].status == "hypothesis_only"
    assert opportunities[0].commercial_relevance == "unproven"
    assert "existing solution maturity research" in opportunities[0].missing_evidence


def test_proof_gates_explain_status_confidence_missing_evidence_and_next_action():
    _verified, _findings, _opportunities, gates, verdict = pipeline_objects()

    evidence_quality = gates[0]
    assert evidence_quality.gate_name == "Evidence quality"
    assert evidence_quality.status == "WEAK"
    assert evidence_quality.evidence_ids
    assert evidence_quality.confidence > 0
    assert evidence_quality.missing_evidence
    assert evidence_quality.recommended_next_action
    assert verdict.outcome == "CONTINUE RESEARCH"


def test_markdown_report_links_statements_to_evidence_ids():
    verified, findings, opportunities, _gates, verdict = pipeline_objects()

    markdown = render_markdown_report(verdict, verified, findings, opportunities)

    assert verdict.outcome in markdown
    assert verified[0].evidence_id in markdown
    assert findings[0].finding_id in markdown
    assert opportunities[0].opportunity_id in markdown

