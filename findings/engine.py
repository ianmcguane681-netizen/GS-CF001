from __future__ import annotations

from collections import defaultdict

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
        summary = (
            f"{mechanism} appears in {evidence_count} verified CFPB candidate(s) across "
            f"{company_count} company reference(s)."
        )
        finding_id = stable_id("FND", {"mechanism": mechanism, "evidence": evidence_ids})
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
                ],
            )
        )
    return findings
