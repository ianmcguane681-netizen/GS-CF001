from __future__ import annotations

from core.ids import stable_id
from core.models import AccessDiagnostic, Finding, OpportunityHypothesis, ProofGateResult, SourceReliabilityAssessment, StudyVerdict, VerifiedEvidence

OUTCOME_RANK = {
    "REJECT": 0,
    "INSUFFICIENT EVIDENCE": 1,
    "PROCESS / POLICY PROBLEM": 2,
    "SATURATED MARKET": 2,
    "CONTINUE RESEARCH": 3,
    "BUILD CANDIDATE": 4,
}


def _status(condition: bool, weak_condition: bool = False) -> str:
    if condition:
        return "PASS"
    if weak_condition:
        return "WEAK"
    return "FAIL"


def _gate(
    gate_id: str,
    name: str,
    status: str,
    threshold: str,
    observed: str,
    evidence_ids: list[str],
    supporting: list[str],
    counter: list[str],
    confidence: float,
    missing: list[str],
    action: str,
    reasoning: list[str],
    constrains: bool = False,
) -> ProofGateResult:
    return ProofGateResult(
        gate_id=gate_id,
        gate_name=name,
        status=status,
        threshold=threshold,
        observed_value=observed,
        evidence_ids=evidence_ids,
        supporting_evidence=supporting,
        counter_evidence=counter,
        confidence=confidence,
        missing_evidence=missing,
        recommended_next_action=action,
        constrains_max_verdict=constrains,
        reasoning_chain=reasoning,
    )


def evaluate_proof_gates(
    evidence: list[VerifiedEvidence],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
    source_reliability: list[SourceReliabilityAssessment] | None = None,
    access_diagnostics: list[AccessDiagnostic] | None = None,
) -> list[ProofGateResult]:
    source_reliability = source_reliability or []
    access_diagnostics = access_diagnostics or []
    evidence_ids = [item.evidence_id for item in evidence]
    verified = [item for item in evidence if item.verification_status == "verified_candidate"]
    supported_findings = [finding for finding in findings if finding.status == "finding_supported_cfpb_only"]
    supported_opportunities = [opportunity for opportunity in opportunities if opportunity.status == "hypothesis_only"]
    source_families = sorted({item.source_family for item in evidence if item.source_family})
    company_count = max([finding.company_count for finding in findings], default=0)
    repeated = bool(supported_findings)
    preserved = bool(evidence) or bool(access_diagnostics)
    normalised = bool(evidence)
    any_access_error = any(diagnostic.response_status not in {"200", "local_file_read"} for diagnostic in access_diagnostics)

    return [
        _gate("PG-01", "Source Authenticity", _status(bool(source_reliability)), "Source reliability assessment present", str(bool(source_reliability)), [], [item.source_id for item in source_reliability], [], 1.0 if source_reliability else 0.0, [] if source_reliability else ["source reliability assessment"], "Create or review source reliability assessment.", ["Source authenticity is assessed from source metadata."]),
        _gate("PG-02", "Raw Record Preservation", _status(preserved), "Raw retrieval artifact or diagnostic exists", str(preserved), evidence_ids, ["raw artifacts", "access diagnostics"] if preserved else [], [], 1.0 if preserved else 0.0, [] if preserved else ["raw preservation artifact"], "Do not normalise until raw retrieval or access failure is preserved.", ["Raw records or access failure diagnostics must exist."]),
        _gate("PG-03", "Normalisation Integrity", _status(normalised), "Normalised candidate records exist", str(normalised), evidence_ids, [item.candidate_id for item in evidence], [], 0.9 if normalised else 0.0, [] if normalised else ["normalised evidence candidates"], "Resolve source access or normalisation before verification.", ["Normalisation is deterministic."]),
        _gate("PG-04", "Study Classification Integrity", _status(all(item.study_id == "GS-CF001-C" for item in evidence) and bool(evidence)), "All evidence maps to GS-CF001-C", str(all(item.study_id == "GS-CF001-C" for item in evidence) and bool(evidence)), evidence_ids, ["GS-CF001-C deterministic product mapping"] if evidence else [], [], 0.9 if evidence else 0.0, [] if evidence else ["classified evidence candidates"], "Classify retrieved records into the implemented study only.", ["Only Credit Reporting Disputes is implemented."]),
        _gate("PG-05", "Repetition", _status(repeated), "Minimum repeated mechanism finding", str(repeated), [evidence_id for finding in findings for evidence_id in finding.evidence_ids], [finding.finding_id for finding in supported_findings], [], 0.75 if repeated else 0.0, [] if repeated else ["repeated mechanism across CFPB records"], "Collect more CFPB records until repeated mechanisms are present.", ["Repetition is within source family only."]),
        _gate("PG-06", "Cross-Company Evidence", _status(company_count >= 2), "At least 2 company references", str(company_count), [evidence_id for finding in findings for evidence_id in finding.evidence_ids], [company for finding in findings for company in finding.companies], [], 0.75 if company_count >= 2 else 0.0, [] if company_count >= 2 else ["evidence across at least 2 companies"], "Collect records spanning multiple companies.", ["Company spread supports repetition but not independent corroboration."]),
        _gate("PG-07", "Operational Specificity", _status(bool(supported_findings)), "Finding includes operational mechanism definition", str(bool(supported_findings)), [evidence_id for finding in findings for evidence_id in finding.evidence_ids], [finding.mechanism for finding in supported_findings], [], 0.7 if supported_findings else 0.0, [] if supported_findings else ["operational mechanism definition"], "Extract trigger, step, failure mode, consequence, and expected process.", ["Findings represent mechanisms, not keywords."]),
        _gate("PG-08", "Software-Addressability", _status(bool(supported_opportunities), bool(opportunities)), "Opportunity assessment exists", str(bool(supported_opportunities)), [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids], [opportunity.component_hypothesis for opportunity in opportunities], [opportunity.non_software_alternatives for opportunity in opportunities], 0.45 if supported_opportunities else 0.2 if opportunities else 0.0, [] if supported_opportunities else ["software-addressability evidence"], "Assess workflow detail and non-software alternatives.", ["Opportunity assessment is separate from verification."]),
        _gate("PG-09", "Independent Corroboration", _status(False), "At least 2 independent source families", str(len(source_families)), evidence_ids, source_families, ["CFPB alone is one source family"], 0.0, ["independent regulatory, enforcement, judicial, audit, company, or examination evidence"], "Add a genuinely independent source family before BUILD CANDIDATE.", ["CFPB complaints alone cannot independently corroborate allegations."], True),
        _gate("PG-10", "Buyer Clarity", _status(False, bool(supported_opportunities)), "Confirmed buyer evidence", "unverified", [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids], [opportunity.buyer_clarity for opportunity in opportunities], ["CFPB identifies companies, not buyers."], 0.25 if supported_opportunities else 0.0, ["confirmed buyer", "budget owner", "procurement context"], "Research buyer role after independent corroboration.", ["Buyer clarity cannot be established from CFPB complaints alone."]),
        _gate("PG-11", "Existing Solution Assessment", _status(False), "Existing solution maturity evidence", "unknown", [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids], [], ["No solution-market research integrated."], 0.0, ["existing solution maturity research"], "Research current solutions before commercial conclusion.", ["No market saturation claim is allowed yet."]),
        _gate("PG-12", "Commercial Relevance", _status(False, bool(supported_opportunities)), "Commercial urgency evidence", "unproven", [evidence_id for opportunity in opportunities for evidence_id in opportunity.evidence_ids], [], ["CFPB complaints do not prove commercial demand."], 0.25 if supported_opportunities else 0.0, ["commercial urgency", "economic impact", "market evidence"], "Do not promote commercial claims without source evidence.", ["Commercial relevance remains hypothesis-only."]),
        _gate("PG-13", "Counter-Evidence", _status(False), "Counter-evidence reviewed", "not reviewed", evidence_ids, [], ["No independent counter-evidence source integrated."], 0.0, ["counter-evidence review"], "Add contradiction and counter-evidence analysis before build decision.", ["Contradictions cannot be assessed from CFPB-only data."]),
        _gate("PG-14", "Reproducibility", _status(not any_access_error and preserved, preserved), "Run preserves artifacts and diagnostics", str(preserved), evidence_ids, ["artifact preservation", "diagnostics"] if preserved else [], [diagnostic.diagnostic_id for diagnostic in access_diagnostics if diagnostic.response_status not in {"200", "local_file_read"}], 0.8 if preserved and not any_access_error else 0.4 if preserved else 0.0, [] if preserved and not any_access_error else ["successful repeatable official retrieval"], "Preserve run manifest, diagnostics, and raw official records.", ["Access failures are reproducible diagnostics, not evidence records."]),
        _gate("PG-15", "Source Independence", _status(len(source_families) >= 2), "Independent source family count >= 2", str(len(source_families)), evidence_ids, source_families, ["Multiple CFPB complaints remain one source family."], 1.0 if len(source_families) >= 2 else 0.0, [] if len(source_families) >= 2 else ["second independent source family"], "Add independent corroborating source family.", ["Different URLs do not automatically mean independent sources."], True),
        _gate("PG-16", "Evidence Ceiling Compliance", "PASS", "If source families < 2, maximum verdict is CONTINUE RESEARCH", f"source families={len(source_families)}", evidence_ids, ["deterministic evidence ceiling rule"], [], 1.0, [] if len(source_families) >= 2 else ["evidence required to remove CONTINUE RESEARCH ceiling"], "Apply deterministic ceiling before final verdict.", ["AI, user settings, and reports cannot override the evidence ceiling."], len(source_families) < 2),
    ]


def _minimum_outcome(outcome: str, ceiling: str) -> str:
    return outcome if OUTCOME_RANK[outcome] <= OUTCOME_RANK[ceiling] else ceiling


def make_verdict(
    study_id: str,
    gates: list[ProofGateResult],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
    evidence: list[VerifiedEvidence] | None = None,
) -> StudyVerdict:
    evidence = evidence or []
    all_missing = sorted({item for gate in gates for item in gate.missing_evidence})
    evidence_ids = sorted({evidence_id for gate in gates for evidence_id in gate.evidence_ids})
    source_family_count = len({item.source_family for item in evidence if item.source_family})
    evidence_ceiling = "CONTINUE RESEARCH" if source_family_count < 2 else "BUILD CANDIDATE"
    ceiling_reason = (
        "Only one independent source family is present." if source_family_count == 1
        else "No independent source family evidence is present." if source_family_count == 0
        else "At least two independent source families are present."
    )
    required_next = [] if source_family_count >= 2 else [
        "Independent regulatory, enforcement, examination, judicial, audit, company, or equivalent evidence corroborating the same operational mechanism."
    ]

    if any(gate.gate_id == "PG-05" and gate.status == "PASS" for gate in gates) and opportunities:
        unconstrained = "CONTINUE RESEARCH"
    elif evidence_ids:
        unconstrained = "CONTINUE RESEARCH"
    else:
        unconstrained = "REJECT"

    final = _minimum_outcome(unconstrained, evidence_ceiling)
    return StudyVerdict(
        verdict_id=stable_id("VER", {"study": study_id, "gates": [gate.to_dict() for gate in gates], "ceiling": evidence_ceiling}),
        study_id=study_id,
        outcome=final,
        unconstrained_outcome=unconstrained,
        evidence_ceiling=evidence_ceiling,
        final_permitted_outcome=final,
        evidence_ceiling_reason=ceiling_reason,
        evidence_required_to_remove_ceiling=required_next,
        independent_source_family_count=source_family_count,
        proof_gates=gates,
        evidence_ids=evidence_ids,
        finding_ids=[finding.finding_id for finding in findings],
        opportunity_ids=[opportunity.opportunity_id for opportunity in opportunities],
        missing_evidence=all_missing,
        reasoning_chain=[
            "Verdict generated from deterministic proof gate statuses.",
            "No positive build decision is allowed unless every proof gate passes.",
            "Evidence ceiling applied after unconstrained assessment.",
        ],
    )
