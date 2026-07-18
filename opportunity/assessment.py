from __future__ import annotations

from core.ids import stable_id
from core.models import Finding, OpportunityHypothesis

COMPONENT_BY_MECHANISM = {
    "bureau_dispute_reinvestigation_failure": "Dispute reinvestigation workflow component",
    "furnisher_tradeline_data_error_persistence": "Tradeline correction evidence workflow",
    "dispute_supporting_evidence_rejection": "Consumer dispute evidence intake component",
    "investigation_outcome_notification_failure": "Investigation outcome communication component",
    "unclassified_credit_reporting_complaint": "Unclassified mechanism - no supported component yet",
    # Historical labels remain readable in archived artifacts.
    "credit_report_dispute_investigation": "Dispute investigation workflow component",
    "incorrect_credit_report_information": "Credit report correction evidence workflow",
    "credit_report_documentation_handling": "Consumer evidence collection component",
    "credit_report_resolution_communication": "Resolution communication tracking component",
    "credit_reporting_dispute_handling": "Credit reporting dispute orchestration component",
}


def assess_finding(finding: Finding) -> OpportunityHypothesis:
    component = COMPONENT_BY_MECHANISM.get(finding.mechanism, "Consumer finance workflow component")
    missing = list(finding.missing_evidence)
    if finding.status != "finding_supported_cfpb_only":
        missing.append("supported finding")
    if finding.company_count < 2:
        missing.append("buyer pattern across multiple companies")
    missing.extend(["existing solution maturity research", "buyer willingness evidence", "commercial urgency evidence"])

    status = "hypothesis_only" if finding.status == "finding_supported_cfpb_only" else "unproven"
    reasoning = [
        f"Assessed finding {finding.finding_id} after finding generation.",
        f"Mapped mechanism {finding.mechanism} to component hypothesis: {component}.",
        "Opportunity assessment does not override missing evidence.",
    ]
    return OpportunityHypothesis(
        opportunity_id=stable_id("OPP", {"finding": finding.finding_id, "component": component}),
        finding_id=finding.finding_id,
        status=status,
        component_hypothesis=component,
        buyer_clarity="weak" if finding.company_count >= 2 else "unclear",
        commercial_relevance="unproven",
        existing_solution_maturity="unknown",
        component_reusability="plausible" if finding.evidence_count >= 3 else "unproven",
        market_saturation="unknown",
        implementation_leverage="unknown",
        user_clarity="plausible operations/compliance users, unverified",
        workflow_owner="unknown; likely disputes, compliance, servicing, or customer operations",
        regulatory_exposure="possible but unverified from CFPB complaints alone",
        operational_cost="unknown",
        integration_burden="unknown",
        cross_company_applicability="plausible" if finding.company_count >= 2 else "unproven",
        non_software_alternatives="process change, policy change, staffing, vendor tools, or training may address the mechanism",
        evidence_ids=finding.evidence_ids,
        missing_evidence=missing,
        reasoning_chain=reasoning,
    )


def assess_findings(findings: list[Finding]) -> list[OpportunityHypothesis]:
    return [assess_finding(finding) for finding in findings]
