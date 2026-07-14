from __future__ import annotations

from collections import defaultdict

from core.evidence_states import CFPB_LIMITED_EVIDENCE, FINDING_ELIGIBLE, transition
from core.ids import stable_id
from core.models import Finding, VerifiedEvidence


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
        summary = (
            f"{mechanism} repeats within CFPB records across {company_count} company reference(s). "
            "This is CFPB-limited and requires independent corroboration."
        )
        finding_id = stable_id("FND", {"mechanism": mechanism, "evidence": evidence_ids})
        mechanism_definition = {
            "trigger": "Consumer disputes credit reporting information.",
            "affected_account_or_dispute_type": "Credit reporting dispute.",
            "operational_step": "Dispute intake, investigation, evidence routing, and response.",
            "failure_mode": "Alleged failure to correct, investigate, match evidence, communicate status, or resolve disputed information.",
            "consumer_consequence": "Consumer reports continued unresolved or allegedly inaccurate information.",
            "expected_process": "Receive dispute, assess evidence, investigate, communicate outcome, and update/report resolution.",
            "observed_alleged_deviation": "CFPB complaint narratives allege the process did not resolve the disputed credit report issue.",
            "repeat_pattern": f"Observed in {evidence_count} CFPB record(s) across {company_count} company reference(s).",
            "software_addressability_hypothesis": "A reusable dispute orchestration, evidence collection, deadline tracking, and audit trail component may address parts of the workflow.",
            "evidence_status": "CFPB-limited.",
            "required_corroboration": "Independent regulatory, enforcement, judicial, audit, company, or examination evidence showing the same mechanism.",
        }
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
