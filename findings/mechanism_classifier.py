"""mechanism_classifier.py — Deterministic six-category classification of findings.

Each Finding produced by findings/engine.py is classified into exactly one of:

    candidate_needs_corroboration — strongest CFPB-supported signal: repeated,
        multi-company, operational, software-addressable, all items have
        repeated_signal=True. The only remaining blocker for BUILD CANDIDATE is
        an independent source family. Evidence ceiling: CONTINUE RESEARCH.

    verified_pain — repeated, multi-company, operational, software-addressable;
        not all evidence items have repeated_signal=True (some are singletons
        within the mechanism). Pain is confirmed within CFPB. Ceiling: CONTINUE
        RESEARCH.

    commercially_weak — operational and software-addressable but insufficient
        scale for a commercial assessment: fewer than 3 evidence items or fewer
        than 2 companies. Cannot support a finding yet.

    non_software_problem — operational complaint pattern exists but no
        software-addressable mechanism is present across the majority of
        evidence. Likely a policy, staffing, or regulatory-compliance issue.

    non_operational_problem — complaint volume exists but the majority of
        evidence items are not operational (no operational mechanism detected).
        Could be perception, terminology, or misclassification.

    noise — fewer than 2 verified_candidate evidence items. Insufficient signal
        to classify as a finding type.

All rules are deterministic. No AI, no probabilistic scoring, no overrides.
The classification is reproducible given the same set of VerifiedEvidence and
the same Finding object.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from core.ids import stable_id
from core.models import Finding, VerifiedEvidence

MechanismCategory = Literal[
    "candidate_needs_corroboration",
    "verified_pain",
    "commercially_weak",
    "non_software_problem",
    "non_operational_problem",
    "noise",
]

# Decision status each category produces in the ODR.
CATEGORY_DECISION_STATUS: dict[str, str] = {
    "candidate_needs_corroboration": "CONTINUE_RESEARCH",
    "verified_pain": "CONTINUE_RESEARCH",
    "commercially_weak": "CONTINUE_RESEARCH",
    "non_software_problem": "REJECTED",
    "non_operational_problem": "REJECTED",
    "noise": "REJECTED",
}

# Human-readable label for reports.
CATEGORY_LABEL: dict[str, str] = {
    "candidate_needs_corroboration": "Candidate — needs independent corroboration",
    "verified_pain": "Verified pain (CFPB-limited)",
    "commercially_weak": "Commercially weak — insufficient scale",
    "non_software_problem": "Non-software problem",
    "non_operational_problem": "Non-operational problem",
    "noise": "Noise — insufficient signal",
}

EVIDENCE_CEILING_NOTE = (
    "Evidence ceiling: CONTINUE RESEARCH. CFPB complaint data is a single source "
    "family. Proof Gates PG-15 and PG-16 cap the maximum verdict at CONTINUE RESEARCH "
    "regardless of record volume. BUILD CANDIDATE requires an independent source family "
    "(regulatory, enforcement, judicial, audit, or company-examination evidence)."
)


@dataclass(frozen=True)
class MechanismClassification:
    """Deterministic six-category classification of one Finding.

    Produced by classify_finding(). Immutable once created.
    """
    classification_id: str
    finding_id: str
    mechanism: str
    category: MechanismCategory
    category_label: str
    decision_status: str          # CONTINUE_RESEARCH | REJECTED
    evidence_ceiling_note: str
    evidence_count: int
    company_count: int
    companies: list[str]
    evidence_ids: list[str]
    all_repeated_signal: bool     # True if every evidence item has repeated_signal=True
    majority_operational: bool
    majority_software_addressable: bool
    classification_reasoning: list[str]
    missing_for_upgrade: list[str]  # what would move this to a higher category

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _majority(items: list[VerifiedEvidence], attr: str) -> bool:
    """Return True if >50 % of *items* have the boolean attribute *attr* True."""
    if not items:
        return False
    count = sum(1 for item in items if getattr(item, attr, False))
    return count > len(items) / 2


def classify_finding(
    finding: Finding,
    evidence_for_finding: list[VerifiedEvidence],
) -> MechanismClassification:
    """Classify *finding* into one of six deterministic categories.

    Parameters
    ----------
    finding:
        The Finding object produced by findings/engine.py.
    evidence_for_finding:
        The VerifiedEvidence items that belong to this finding (same mechanism,
        verification_status == "verified_candidate").

    Returns
    -------
    MechanismClassification with full deterministic reasoning chain.
    """
    ec = finding.evidence_count
    cc = finding.company_count
    verified_items = [
        e for e in evidence_for_finding
        if e.verification_status == "verified_candidate"
    ]
    verified_count = len(verified_items)

    all_repeated = bool(verified_items) and all(e.repeated_signal for e in verified_items)
    maj_operational = _majority(verified_items, "operational")
    maj_sw = _majority(verified_items, "software_addressable")
    is_finding_supported = finding.status == "finding_supported_cfpb_only"

    # ---- Deterministic category decision tree (most restrictive first) -----

    reasoning: list[str] = []
    missing_for_upgrade: list[str] = []

    if verified_count < 2:
        category: MechanismCategory = "noise"
        reasoning = [
            f"Finding {finding.finding_id} has {verified_count} verified_candidate evidence item(s) — below the minimum of 2.",
            "Insufficient signal to assess mechanism type or commercial relevance.",
            "Classified as noise.",
        ]
        missing_for_upgrade = ["at least 2 verified_candidate evidence items"]

    elif not maj_operational:
        category = "non_operational_problem"
        reasoning = [
            f"Finding {finding.finding_id} has {verified_count} verified items but fewer than half are operational.",
            "The complaint pattern does not indicate an operational workflow failure.",
            "Likely reflects misunderstanding, terminology, or a non-operational grievance.",
            "Classified as non_operational_problem.",
        ]
        missing_for_upgrade = [
            "majority of evidence items must have operational=True",
            "at least one OPERATIONAL_TERMS match in complaint text",
        ]

    elif not maj_sw:
        category = "non_software_problem"
        reasoning = [
            f"Finding {finding.finding_id} is operational (majority operational=True) but fewer than half of evidence items are software-addressable.",
            "The mechanism may be a policy, regulatory-compliance, staffing, or process issue rather than a software-addressable workflow gap.",
            "Non-software alternatives (process change, staffing, vendor tools, regulatory change) likely dominate.",
            "Classified as non_software_problem.",
        ]
        missing_for_upgrade = [
            "majority of evidence items must have software_addressable=True",
            "mechanism must include SOFTWARE_ADDRESSABLE_TERMS matches",
        ]

    elif not is_finding_supported or ec < 3 or cc < 2:
        category = "commercially_weak"
        reasons = []
        if not is_finding_supported:
            reasons.append(f"finding status is '{finding.status}' (not 'finding_supported_cfpb_only')")
        if ec < 3:
            reasons.append(f"evidence_count={ec} < 3")
        if cc < 2:
            reasons.append(f"company_count={cc} < 2")
        reasoning = [
            f"Finding {finding.finding_id} is operational and software-addressable but: {'; '.join(reasons)}.",
            "Insufficient scale or finding maturity for a commercial assessment.",
            "Classified as commercially_weak.",
        ]
        missing_for_upgrade = []
        if not is_finding_supported:
            missing_for_upgrade.append("finding status must be finding_supported_cfpb_only")
        if ec < 3:
            missing_for_upgrade.append("at least 3 verified evidence items")
        if cc < 2:
            missing_for_upgrade.append("evidence across at least 2 distinct companies")

    elif all_repeated:
        category = "candidate_needs_corroboration"
        reasoning = [
            f"Finding {finding.finding_id}: evidence_count={ec} ≥ 3, company_count={cc} ≥ 2, status=finding_supported_cfpb_only.",
            "All verified evidence items have repeated_signal=True — the mechanism repeats consistently across complaints.",
            "Operational and software-addressable criteria met.",
            "All internal CFPB proof-gate criteria met. The only remaining blocker for BUILD CANDIDATE is an independent source family.",
            f"Evidence ceiling enforced: CONTINUE RESEARCH (PG-15 source_families=1, PG-16 ceiling applied).",
            "Classified as candidate_needs_corroboration — highest priority for corroboration effort.",
        ]
        missing_for_upgrade = [
            "second independent source family (regulatory, enforcement, judicial, audit, or company-examination evidence)",
        ]

    else:
        category = "verified_pain"
        reasoning = [
            f"Finding {finding.finding_id}: evidence_count={ec} ≥ 3, company_count={cc} ≥ 2, status=finding_supported_cfpb_only.",
            "Majority of evidence items are operational and software-addressable.",
            f"Not all evidence items have repeated_signal=True ({sum(1 for e in verified_items if e.repeated_signal)}/{verified_count} do) — some are single-occurrence within this mechanism.",
            "Pain is confirmed within CFPB data. Evidence ceiling: CONTINUE RESEARCH.",
            "Classified as verified_pain.",
        ]
        missing_for_upgrade = [
            "all verified evidence items must have repeated_signal=True (to reach candidate_needs_corroboration)",
            "second independent source family (to remove evidence ceiling)",
        ]

    classification_id = stable_id(
        "CLF",
        {"finding_id": finding.finding_id, "category": category},
    )
    return MechanismClassification(
        classification_id=classification_id,
        finding_id=finding.finding_id,
        mechanism=finding.mechanism,
        category=category,
        category_label=CATEGORY_LABEL[category],
        decision_status=CATEGORY_DECISION_STATUS[category],
        evidence_ceiling_note=EVIDENCE_CEILING_NOTE,
        evidence_count=ec,
        company_count=cc,
        companies=list(finding.companies),
        evidence_ids=list(finding.evidence_ids),
        all_repeated_signal=all_repeated,
        majority_operational=maj_operational,
        majority_software_addressable=maj_sw,
        classification_reasoning=reasoning,
        missing_for_upgrade=missing_for_upgrade,
    )


def classify_all(
    findings: list[Finding],
    all_evidence: list[VerifiedEvidence],
) -> list[MechanismClassification]:
    """Classify every finding in *findings*.

    Builds a mechanism → evidence lookup from *all_evidence* so each finding
    receives only the evidence items that belong to it.
    """
    from collections import defaultdict
    evidence_by_mechanism: dict[str, list[VerifiedEvidence]] = defaultdict(list)
    for ev in all_evidence:
        if ev.verification_status == "verified_candidate":
            evidence_by_mechanism[ev.mechanism].append(ev)

    return [
        classify_finding(finding, evidence_by_mechanism[finding.mechanism])
        for finding in findings
    ]
