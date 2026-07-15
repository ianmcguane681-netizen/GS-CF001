"""mechanism_classifier.py — Deterministic six-category classification of findings.

Each Finding is classified into exactly one of six categories. The names are
chosen to reflect what the CFPB evidence actually establishes — which is a
complaint signal, not a verified operational fact:

    repeated_complaint_signal
        Multiple CFPB complaints about the same mechanism across multiple
        companies. All evidence items have repeated_signal=True. The complaint
        pattern is consistent. IMPORTANT: CFPB complaints are unverified
        consumer allegations; this category does NOT confirm that an
        operational failure occurred, does NOT confirm software addressability
        of the root cause, and does NOT imply commercial viability. Multiple
        independent research streams are required before any of those
        conclusions can be drawn. Evidence ceiling: CONTINUE RESEARCH.

    partial_complaint_signal
        Multiple CFPB complaints about the same mechanism across multiple
        companies, but not all evidence items have repeated_signal=True (some
        are singletons within the mechanism). Same caveats as
        repeated_complaint_signal. Evidence ceiling: CONTINUE RESEARCH.

    commercially_weak
        Operational and software-addressable complaint signal exists but
        insufficient scale or finding maturity for even a preliminary commercial
        assessment: fewer than 3 evidence items or fewer than 2 companies.

    non_software_problem
        Majority of verified evidence items are operational (describe a workflow
        failure) but NOT software-addressable (the failure mode is more
        plausibly addressed by policy, staffing, regulation, or legal action).
        Decision: REJECTED.

    non_operational_problem
        Evidence items exist but the majority are NOT operational — the
        complaint pattern does not describe a specific workflow failure.
        Could be perception, taxonomy mismatch, or educational need.
        Decision: REJECTED.

    noise
        Fewer than 2 verified evidence items. Insufficient signal to classify.
        Decision: REJECTED.

All rules are deterministic. No AI, no probabilistic scoring, no overrides.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from core.ids import stable_id
from core.models import Finding, VerifiedEvidence

MechanismCategory = Literal[
    "repeated_complaint_signal",
    "partial_complaint_signal",
    "commercially_weak",
    "non_software_problem",
    "non_operational_problem",
    "noise",
]

# Decision status each category produces in the ODR.
CATEGORY_DECISION_STATUS: dict[str, str] = {
    "repeated_complaint_signal": "CONTINUE_RESEARCH",
    "partial_complaint_signal": "CONTINUE_RESEARCH",
    "commercially_weak": "CONTINUE_RESEARCH",
    "non_software_problem": "REJECTED",
    "non_operational_problem": "REJECTED",
    "noise": "REJECTED",
}

# Human-readable label for reports.
CATEGORY_LABEL: dict[str, str] = {
    "repeated_complaint_signal": "Repeated complaint signal (operational reality unverified)",
    "partial_complaint_signal": "Partial complaint signal (operational reality unverified)",
    "commercially_weak": "Commercially weak — insufficient scale",
    "non_software_problem": "Non-software problem",
    "non_operational_problem": "Non-operational problem",
    "noise": "Noise — insufficient signal",
}

EVIDENCE_CEILING_NOTE = (
    "Evidence ceiling: CONTINUE RESEARCH. CFPB complaint data is a single source "
    "family. Proof Gates PG-15 and PG-16 cap the maximum verdict at CONTINUE RESEARCH "
    "regardless of record volume. CFPB complaints are unverified consumer allegations "
    "and do not independently confirm operational failure, software addressability, or "
    "commercial viability. Multiple independent research streams are required before any "
    "of those conclusions can be drawn."
)

# Full list of what must be established before a CONTINUE_RESEARCH finding can
# advance toward BUILD CANDIDATE. Used in missing_for_upgrade for the two
# top-tier categories.
_ADVANCE_REQUIREMENTS = [
    "Independent corroboration of operational reality from a non-CFPB source "
    "(regulatory findings, enforcement actions, judicial records, audit reports, "
    "or company-examination evidence) confirming the mechanism exists as described.",
    "Named buyer persona with confirmed purchasing authority, demonstrated budget "
    "cycle, and organisational context (role, company size, purchase trigger).",
    "Measurable operational or financial cost attributable to the mechanism "
    "(documented dollar amount, labour hours lost, SLA breach rate, or equivalent "
    "quantifiable harm — not inferred from complaint volume).",
    "Competitive landscape assessment: named existing solutions, their current "
    "maturity level, and a sourced explanation of why they fail or are unavailable "
    "to the identified buyer.",
    "Non-software alternatives assessment: explicit evaluation of why process change, "
    "staffing, regulatory compliance, or vendor-contract modification cannot solve "
    "this more cost-effectively than software.",
    "Addressable market size estimate with sourced revenue-potential basis "
    "(not a top-down TAM — a bottoms-up count of named buyers with stated willingness "
    "to pay or comparable purchase evidence).",
    "Commercial signal: at least one instance of stated or implied willingness to pay, "
    "a deal-cycle or procurement reference, or a comparable competitive sale.",
]


@dataclass(frozen=True)
class MechanismClassification:
    """Deterministic six-category classification of one Finding."""
    classification_id: str
    finding_id: str
    mechanism: str
    category: MechanismCategory
    category_label: str
    decision_status: str
    evidence_ceiling_note: str
    evidence_count: int
    company_count: int
    companies: list[str]
    evidence_ids: list[str]
    all_repeated_signal: bool
    majority_operational: bool
    majority_software_addressable: bool
    classification_reasoning: list[str]
    missing_for_upgrade: list[str]
    # Audit note: populated when a majority vote driving classification is within
    # 10 percentage points of 50% (i.e. 40%–60%). A borderline vote means a small
    # evidence change could flip the category. Empty string when not borderline.
    borderline_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _majority(items: list[VerifiedEvidence], attr: str) -> bool:
    if not items:
        return False
    count = sum(1 for item in items if getattr(item, attr, False))
    return count > len(items) / 2


def _majority_ratio(items: list[VerifiedEvidence], attr: str) -> float:
    """Return the fraction of items where attr is True (0.0 if empty)."""
    if not items:
        return 0.0
    return sum(1 for item in items if getattr(item, attr, False)) / len(items)


_BORDERLINE_BAND = 0.10   # within 10pp of 50% → borderline


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
        The VerifiedEvidence items for this finding (same mechanism,
        verification_status == "verified_candidate").
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

    reasoning: list[str] = []
    missing_for_upgrade: list[str] = []

    if verified_count < 2:
        category: MechanismCategory = "noise"
        reasoning = [
            f"Finding {finding.finding_id} has {verified_count} verified_candidate "
            f"evidence item(s) — below the minimum of 2.",
            "Insufficient signal to assess mechanism type or commercial relevance.",
            "Classified as noise.",
        ]
        missing_for_upgrade = ["at least 2 verified_candidate evidence items"]

    elif not maj_operational:
        category = "non_operational_problem"
        reasoning = [
            f"Finding {finding.finding_id} has {verified_count} verified items "
            f"but fewer than half have operational=True.",
            "The complaint pattern does not describe a specific operational workflow failure.",
            "Likely reflects educational need, taxonomy mismatch, or general dissatisfaction.",
            "Classified as non_operational_problem.",
        ]
        missing_for_upgrade = [
            "majority of evidence items must describe a specific operational workflow failure (operational=True)",
            "at least one OPERATIONAL_TERMS match per item",
        ]

    elif not maj_sw:
        category = "non_software_problem"
        reasoning = [
            f"Finding {finding.finding_id}: majority operational=True "
            f"({sum(1 for e in verified_items if e.operational)}/{verified_count} items).",
            "However, fewer than half of evidence items have software_addressable=True.",
            "The failure mode is more plausibly addressed by policy change, regulatory "
            "compliance, staffing adjustment, legal action, or vendor-contract modification "
            "rather than a software workflow component.",
            "Classified as non_software_problem.",
        ]
        missing_for_upgrade = [
            "majority of evidence items must contain SOFTWARE_ADDRESSABLE_TERMS matches",
            "mechanism must indicate a workflow gap addressable by software (not a legal "
            "or regulatory compliance gap)",
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
            f"Finding {finding.finding_id} is operational and software-addressable "
            f"but: {'; '.join(reasons)}.",
            "Insufficient scale or finding maturity for any commercial assessment.",
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
        category = "repeated_complaint_signal"
        reasoning = [
            f"Finding {finding.finding_id}: evidence_count={ec} ≥ 3, "
            f"company_count={cc} ≥ 2, status=finding_supported_cfpb_only.",
            "All verified evidence items have repeated_signal=True — the same "
            "mechanism appears across multiple complaints.",
            "Operational and software-addressable criteria met within CFPB data.",
            "IMPORTANT: CFPB complaints are unverified consumer allegations. "
            "This classification does NOT confirm operational reality, software "
            "addressability of the root cause, or commercial viability.",
            f"Evidence ceiling enforced: CONTINUE RESEARCH "
            f"(PG-15 source_families=1, PG-16 ceiling applied).",
            "Classified as repeated_complaint_signal.",
        ]
        missing_for_upgrade = list(_ADVANCE_REQUIREMENTS)

    else:
        category = "partial_complaint_signal"
        repeated_count = sum(1 for e in verified_items if e.repeated_signal)
        reasoning = [
            f"Finding {finding.finding_id}: evidence_count={ec} ≥ 3, "
            f"company_count={cc} ≥ 2, status=finding_supported_cfpb_only.",
            f"Only {repeated_count}/{verified_count} verified items have "
            f"repeated_signal=True — some are single-occurrence within this mechanism.",
            "IMPORTANT: CFPB complaints are unverified consumer allegations. "
            "This classification does NOT confirm operational reality, software "
            "addressability, or commercial viability.",
            "Evidence ceiling: CONTINUE RESEARCH.",
            "Classified as partial_complaint_signal.",
        ]
        missing_for_upgrade = [
            "all verified evidence items must have repeated_signal=True "
            "(to reach repeated_complaint_signal)",
        ] + list(_ADVANCE_REQUIREMENTS)

    # Borderline vote detection (F-04 from methodology audit):
    # Emit a note when the majority vote that drove classification is within
    # _BORDERLINE_BAND (10pp) of 50%. A borderline vote means adding or removing
    # one or two evidence items could flip the category.
    op_ratio = _majority_ratio(verified_items, "operational")
    sw_ratio = _majority_ratio(verified_items, "software_addressable")
    borderline_parts: list[str] = []
    if verified_count >= 2:
        if abs(op_ratio - 0.5) <= _BORDERLINE_BAND:
            pct = round(op_ratio * 100)
            borderline_parts.append(
                f"operational vote is borderline ({pct}% of {verified_count} items; "
                f"threshold 50% — a small evidence change could flip this)"
            )
        if abs(sw_ratio - 0.5) <= _BORDERLINE_BAND:
            pct = round(sw_ratio * 100)
            borderline_parts.append(
                f"software_addressable vote is borderline ({pct}% of {verified_count} items; "
                f"threshold 50% — a small evidence change could flip this)"
            )
    borderline_note = (
        "BORDERLINE MAJORITY VOTE: " + "; ".join(borderline_parts)
        if borderline_parts else ""
    )

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
        borderline_note=borderline_note,
    )


def classify_all(
    findings: list[Finding],
    all_evidence: list[VerifiedEvidence],
) -> list[MechanismClassification]:
    """Classify every finding in *findings*."""
    from collections import defaultdict
    evidence_by_mechanism: dict[str, list[VerifiedEvidence]] = defaultdict(list)
    for ev in all_evidence:
        if ev.verification_status == "verified_candidate":
            evidence_by_mechanism[ev.mechanism].append(ev)

    return [
        classify_finding(finding, evidence_by_mechanism[finding.mechanism])
        for finding in findings
    ]
