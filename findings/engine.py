from __future__ import annotations

from collections import defaultdict

from core.evidence_states import CFPB_LIMITED_EVIDENCE, FINDING_ELIGIBLE, transition
from core.ids import stable_id
from core.models import Finding, VerifiedEvidence


MECHANISM_DEFINITIONS = {
    "bureau_dispute_reinvestigation_failure": {
        "trigger": "Consumer disputes credit-report information.",
        "operational_step": "Credit bureau dispute intake and reinvestigation.",
        "failure_mode": "The complaint alleges that reinvestigation did not correct or resolve the disputed information.",
        "expected_process": "Receive the dispute, assess supplied information, reinvestigate, and communicate the outcome.",
        "software_addressability_hypothesis": "A dispute-intake, evidence-routing, deadline, and outcome-tracking component may support the workflow.",
    },
    "furnisher_tradeline_data_error_persistence": {
        "trigger": "Consumer identifies allegedly inaccurate or unrecognised tradeline data.",
        "operational_step": "Data-furnisher verification and credit-report correction.",
        "failure_mode": "The complaint alleges that disputed tradeline data persisted after a correction request.",
        "expected_process": "Route the disputed data to the responsible party, investigate it, and update or explain the result.",
        "software_addressability_hypothesis": "A correction-case routing and evidence reconciliation component may support the workflow.",
    },
    "dispute_supporting_evidence_rejection": {
        "trigger": "Consumer supplies documents or other evidence for a dispute.",
        "operational_step": "Supporting-evidence intake, matching, and investigation routing.",
        "failure_mode": "The complaint alleges that supporting evidence was rejected, ignored, or not considered.",
        "expected_process": "Receive, identify, preserve, and route supporting evidence into the investigation.",
        "software_addressability_hypothesis": "An evidence-intake, matching, and audit-trail component may support the workflow.",
    },
    "investigation_outcome_notification_failure": {
        "trigger": "A consumer awaits the status or outcome of a dispute investigation.",
        "operational_step": "Investigation status and outcome communication.",
        "failure_mode": "The complaint alleges that required status or outcome communication was absent or inadequate.",
        "expected_process": "Track the investigation and communicate status and outcome through a traceable channel.",
        "software_addressability_hypothesis": "A deadline-aware notification and communication-record component may support the workflow.",
    },
    "unclassified_credit_reporting_complaint": {
        "trigger": "Consumer reports a credit-reporting concern.",
        "operational_step": "A specific operational step has not yet been established.",
        "failure_mode": "A specific repeated failure mode has not yet been established.",
        "expected_process": "Further evidence is required to define the expected process.",
        "software_addressability_hypothesis": "No component hypothesis should be treated as supported until the mechanism is classified.",
    },
}


def _mechanism_definition(
    mechanism: str, items: list[VerifiedEvidence], evidence_count: int, company_count: int
) -> dict[str, str]:
    definition = dict(MECHANISM_DEFINITIONS.get(mechanism, MECHANISM_DEFINITIONS["unclassified_credit_reporting_complaint"]))
    narrative_count = sum(item.narrative_available for item in items)
    taxonomy_count = sum(
        item.operational_basis == "explicit_cfpb_taxonomy_process_failure" for item in items
    )
    if narrative_count:
        observed = (
            f"{narrative_count} public consumer narrative(s) contain the process-and-failure "
            "language recorded in the supporting evidence artifacts."
        )
        if taxonomy_count:
            observed += f" {taxonomy_count} additional record(s) qualify from explicit CFPB taxonomy."
    else:
        observed = (
            "Qualification is based only on explicit CFPB issue/sub-issue taxonomy; "
            "no public consumer narrative supports a more specific alleged deviation."
        )
    definition.update(
        {
            "affected_account_or_dispute_type": "Credit reporting dispute.",
            "consumer_consequence": "The consumer reports an unresolved credit-reporting concern.",
            "observed_alleged_deviation": observed,
            "repeat_pattern": (
                f"Observed in {evidence_count} CFPB record(s) across {company_count} company reference(s)."
                if evidence_count > 1
                else "Observed in one CFPB record; repetition is not established."
            ),
            "evidence_status": "CFPB-limited.",
            "required_corroboration": "Independent regulatory, enforcement, judicial, audit, company, or examination evidence showing the same mechanism.",
        }
    )
    return definition


def generate_findings(evidence: list[VerifiedEvidence]) -> list[Finding]:
    grouped: dict[str, list[VerifiedEvidence]] = defaultdict(list)
    for item in evidence:
        if item.verification_status == "verified_candidate" and item.operational and item.traceable:
            grouped[item.mechanism].append(item)

    findings: list[Finding] = []
    for mechanism, items in grouped.items():
        companies = sorted({item.company_name for item in items if item.company_name})
        evidence_ids = [item.evidence_id for item in items]
        dates = sorted({item.date_received for item in items if item.date_received})
        evidence_count = len(items)
        company_count = len(companies)
        missing = []
        if evidence_count < 3:
            missing.append("minimum 3 verified evidence items")
        if company_count < 2:
            missing.append("evidence across at least 2 companies")
        if any(not item.repeated_signal for item in items):
            missing.append("repeated signal across independent complaints")
        if not any(item.independently_corrobored for item in items):
            missing.append("independent non-CFPB corroboration")

        threshold_missing = [item for item in missing if item != "independent non-CFPB corroboration"]
        status = "finding_supported_cfpb_only" if not threshold_missing else "needs_more_evidence"
        maximum_permitted_verdict = "CONTINUE RESEARCH"
        if evidence_count > 1:
            summary = (
                f"{mechanism} appears in {evidence_count} CFPB records across "
                f"{company_count} company reference(s). This is CFPB-limited and requires "
                "independent corroboration."
            )
        else:
            summary = (
                f"{mechanism} appears in one CFPB record. Repetition is not established, "
                "and independent corroboration is required."
            )
        finding_id = stable_id("FND", {"mechanism": mechanism, "evidence": evidence_ids})
        mechanism_definition = _mechanism_definition(
            mechanism, items, evidence_count, company_count
        )
        state_transition = transition(
            finding_id,
            CFPB_LIMITED_EVIDENCE,
            FINDING_ELIGIBLE if status == "finding_supported_cfpb_only" else CFPB_LIMITED_EVIDENCE,
            "Findings V1 repeated mechanism grouping",
            evidence_ids,
            status,
            0.7 if status == "finding_supported_cfpb_only" else 0.35,
            ["Finding remains CFPB-limited and cannot support BUILD CANDIDATE without independent corroboration."],
        )
        findings.append(
            Finding(
                finding_id=finding_id,
                study_id=items[0].study_id,
                mechanism=mechanism,
                status=status,
                evidence_ids=evidence_ids,
                companies=companies,
                evidence_count=evidence_count,
                company_count=company_count,
                summary=summary,
                missing_evidence=missing,
                reasoning_chain=[
                    f"Grouped verified evidence by operational mechanism {mechanism}.",
                    "Finding remains limited because CFPB is currently the only source.",
                    state_transition.transition_id,
                ],
                date_range=f"{dates[0]} to {dates[-1]}" if dates else "unknown",
                product_issue_mappings=sorted({f"{item.product} / {item.issue}" for item in items}),
                mechanism_definition=mechanism_definition,
                verification_status="CFPB-limited Finding",
                alternative_explanations=[
                    "Similar CFPB complaints may reflect reporting behaviour or company size rather than a shared root cause.",
                    "Consumer allegations may be incomplete, inaccurate, or unresolved in the public record.",
                    "The same taxonomy may group operationally different cases.",
                ],
                source_limitations=sorted({limitation for item in items for limitation in item.source_limitations}),
                maximum_permitted_verdict=maximum_permitted_verdict,
            )
        )
    return findings
