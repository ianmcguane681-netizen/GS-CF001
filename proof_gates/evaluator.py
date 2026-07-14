from __future__ import annotations

from core.ids import stable_id
from core.models import Finding, OpportunityHypothesis, ProofGateResult, StudyVerdict, VerifiedEvidence


def _gate(
    name: str,
    status: str,
    evidence_ids: list[str],
    confidence: float,
    missing: list[str],
    action: str,
    reasoning: list[str],
) -> ProofGateResult:
    return ProofGateResult(name, status, evidence_ids, confidence, missing, action, reasoning)


def evaluate_proof_gates(
    evidence: list[VerifiedEvidence],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
) -> list[ProofGateResult]:
    evidence_ids = [item.evidence_id for item in evidence]
    verified = [item for item in evidence if item.verification_status == "verified_candidate"]
    supported_findings = [finding for finding in findings if finding.status == "finding_supported_cfpb_only"]
    supported_opportunities = [opportunity for opportunity in opportunities if opportunity.status == "hypothesis_only"]

    return [
        _gate(
            "Evidence quality",
            "WEAK" if verified else "FAIL",
            evidence_ids,
            0.45 if verified else 0.0,
            ["independent non-CFPB corroboration"] if verified else ["verified CFPB evidence"],
            "Add corroborating source types before accepting a build candidate.",
            ["Verified CFPB evidence exists." if verified else "No verified evidence exists."],
        ),
        _gate(
            "Verification quality",
            "WEAK" if verified else "FAIL",
            evidence_ids,
            0.5 if verified else 0.0,
            ["regulatory, enforcement, court, or company-response verification"],
            "Do not treat CFPB discovery records as independently verified.",
            ["Verification is currently limited to CFPB-derived records."],
        ),
        _gate(
            "Repeatability",
            "PASS" if supported_findings else "WEAK" if findings else "FAIL",
            [evidence_id for finding in findings for evidence_id in finding.evidence_ids],
            0.7 if supported_findings else 0.25 if findings else 0.0,
            [] if supported_findings else ["minimum repeated mechanism across multiple complaints and companies"],
            "Continue collecting evidence until repeated operational mechanisms are demonstrated.",
            ["Finding engine grouped evidence by mechanism."],
        ),
        _gate(
            "Software addressability",
            "WEAK" if supported_opportunities else "FAIL",
            [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids],
            0.45 if supported_opportunities else 0.0,
            ["workflow detail and implementation leverage evidence"],
            "Assess whether the pain is workflow-driven rather than policy-only.",
            ["Opportunity assessment mapped mechanisms to reusable component hypotheses."],
        ),
        _gate(
            "Buyer clarity",
            "WEAK" if supported_opportunities else "FAIL",
            [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids],
            0.25 if supported_opportunities else 0.0,
            ["confirmed buyer", "budget owner", "procurement context"],
            "Research buyer role before build decision.",
            ["CFPB complaints identify companies, not buyers."],
        ),
        _gate(
            "Commercial relevance",
            "WEAK" if supported_opportunities else "FAIL",
            [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids],
            0.25 if supported_opportunities else 0.0,
            ["commercial urgency", "market saturation", "existing solution maturity"],
            "Run commercial relevance research after evidence corroboration.",
            ["No commercial claims are accepted from CFPB data alone."],
        ),
    ]


def make_verdict(
    study_id: str,
    gates: list[ProofGateResult],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
) -> StudyVerdict:
    all_missing = sorted({item for gate in gates for item in gate.missing_evidence})
    evidence_ids = sorted({evidence_id for gate in gates for evidence_id in gate.evidence_ids})
    if gates and all(gate.status == "PASS" for gate in gates):
        outcome = "BUILD CANDIDATE"
    elif any(gate.evidence_ids for gate in gates):
        outcome = "CONTINUE RESEARCH"
    else:
        outcome = "REJECT"
    return StudyVerdict(
        verdict_id=stable_id("VER", {"study": study_id, "gates": [gate.to_dict() for gate in gates]}),
        study_id=study_id,
        outcome=outcome,
        proof_gates=gates,
        evidence_ids=evidence_ids,
        finding_ids=[finding.finding_id for finding in findings],
        opportunity_ids=[opportunity.opportunity_id for opportunity in opportunities],
        missing_evidence=all_missing,
        reasoning_chain=[
            "Verdict generated from proof gate statuses.",
            "No positive build decision is allowed unless every proof gate passes.",
        ],
    )

