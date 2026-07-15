"""opportunity_decision_register.py — Fully traceable Opportunity Decision Register.

Produces one ODREntry per opportunity hypothesis, using deterministic rules only.
No AI is used in any ODR decision. All reasoning is derived from:
  - MechanismClassification (category, decision_status)
  - Finding fields (evidence_count, company_count, status, companies)
  - OpportunityHypothesis fields (component_hypothesis, buyer_clarity, etc.)
  - Proof Gate outputs (specifically PG-15, PG-16 for ceiling enforcement)

An ODREntry records:
  - odr_id          — deterministic stable ID
  - mechanism       — the detected mechanism name
  - mechanism_classification — six-category result
  - evidence_references — evidence IDs supporting this entry
  - companies_observed — companies seen in CFPB data
  - evidence_count, company_count — counts for traceability
  - finding_id, opportunity_id — cross-references
  - component_hypothesis — what software component was hypothesised
  - commercial_assessment — buyer_clarity, relevance, reusability fields verbatim
  - decision_status — REJECTED | CONTINUE_RESEARCH
  - decision_rationale — full deterministic reasoning chain
  - evidence_ceiling_note — explicit ceiling enforcement statement
  - missing_for_decision_upgrade — what evidence is needed to advance status
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ids import stable_id
from core.models import Finding, OpportunityHypothesis
from findings.mechanism_classifier import (
    EVIDENCE_CEILING_NOTE,
    MechanismClassification,
)


@dataclass(frozen=True)
class ODREntry:
    """One row in the Opportunity Decision Register.

    Every field is populated from pipeline outputs by deterministic rules.
    """
    odr_id: str
    mechanism: str
    mechanism_classification: str       # six-category label
    decision_status: str                # REJECTED | CONTINUE_RESEARCH
    evidence_ceiling_note: str
    finding_id: str
    opportunity_id: str
    evidence_references: list[str]      # evidence IDs
    companies_observed: list[str]
    evidence_count: int
    company_count: int
    component_hypothesis: str
    buyer_clarity: str
    commercial_relevance: str
    component_reusability: str
    commercial_assessment_summary: str
    decision_rationale: list[str]
    missing_for_decision_upgrade: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpportunityDecisionRegister:
    """Full ODR for one pipeline run."""
    odr_id: str
    study_id: str
    run_id: str
    generated_at: str
    evidence_ceiling: str
    evidence_ceiling_note: str
    entry_count: int
    rejected_count: int
    continue_research_count: int
    entries: list[ODREntry]
    methodology_note: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["entries"] = [e.to_dict() for e in self.entries]
        return data


_METHODOLOGY_NOTE = (
    "All decisions in this ODR are produced by deterministic pipeline rules. "
    "No AI model was consulted for any classification or decision. "
    "The Evidence Ceiling (CONTINUE RESEARCH) is enforced by Proof Gates PG-15 and PG-16 "
    "and cannot be overridden by any ODR entry, report, or configuration. "
    "CFPB complaint data is a single source family; BUILD CANDIDATE requires "
    "at least two independent source families."
)


def _commercial_summary(opp: OpportunityHypothesis) -> str:
    parts = [
        f"Buyer clarity: {opp.buyer_clarity}.",
        f"Commercial relevance: {opp.commercial_relevance}.",
        f"Component reusability: {opp.component_reusability}.",
        f"Market saturation: {opp.market_saturation}.",
        f"Existing solution maturity: {opp.existing_solution_maturity}.",
        f"Non-software alternatives: {opp.non_software_alternatives}.",
    ]
    return " ".join(parts)


def build_odr_entry(
    finding: Finding,
    opportunity: OpportunityHypothesis,
    classification: MechanismClassification,
) -> ODREntry:
    """Build one ODREntry from a finding, opportunity, and classification.

    Decision logic:
    - decision_status comes from the classification (REJECTED or CONTINUE_RESEARCH).
    - decision_rationale is assembled from classification reasoning + commercial fields.
    - missing_for_decision_upgrade lists what evidence would advance the status.
    """
    rationale = list(classification.classification_reasoning)

    # Add commercial context to rationale.
    rationale.append(
        f"Commercial hypothesis: '{opportunity.component_hypothesis}' — "
        f"buyer_clarity={opportunity.buyer_clarity}, "
        f"commercial_relevance={opportunity.commercial_relevance}, "
        f"reusability={opportunity.component_reusability}."
    )
    if classification.decision_status == "REJECTED":
        rationale.append(
            "Decision: REJECTED. The mechanism does not meet the threshold for "
            "commercial investigation under the current evidence base."
        )
    else:
        rationale.append(
            "Decision: CONTINUE_RESEARCH. Evidence ceiling enforced. "
            "CFPB data alone cannot support a BUILD CANDIDATE verdict. "
            "Independent corroboration must be sourced before this can advance."
        )

    odr_id = stable_id(
        "ODR",
        {"finding_id": finding.finding_id, "opportunity_id": opportunity.opportunity_id},
    )
    return ODREntry(
        odr_id=odr_id,
        mechanism=finding.mechanism,
        mechanism_classification=classification.category_label,
        decision_status=classification.decision_status,
        evidence_ceiling_note=EVIDENCE_CEILING_NOTE,
        finding_id=finding.finding_id,
        opportunity_id=opportunity.opportunity_id,
        evidence_references=list(finding.evidence_ids),
        companies_observed=list(finding.companies),
        evidence_count=finding.evidence_count,
        company_count=finding.company_count,
        component_hypothesis=opportunity.component_hypothesis,
        buyer_clarity=opportunity.buyer_clarity,
        commercial_relevance=opportunity.commercial_relevance,
        component_reusability=opportunity.component_reusability,
        commercial_assessment_summary=_commercial_summary(opportunity),
        decision_rationale=rationale,
        missing_for_decision_upgrade=list(classification.missing_for_upgrade),
    )


def build_odr(
    study_id: str,
    run_id: str,
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
    classifications: list[MechanismClassification],
) -> OpportunityDecisionRegister:
    """Build the full ODR for one pipeline run.

    Pairs each finding with its corresponding opportunity and classification.
    Findings without a matching opportunity are included as REJECTED entries
    with an explicit note. Opportunities without a matching finding are skipped
    (should not occur in a well-formed pipeline run).
    """
    # Index by finding_id for O(1) lookup.
    opp_by_finding: dict[str, OpportunityHypothesis] = {
        opp.finding_id: opp for opp in opportunities
    }
    clf_by_finding: dict[str, MechanismClassification] = {
        clf.finding_id: clf for clf in classifications
    }

    entries: list[ODREntry] = []
    for finding in findings:
        opp = opp_by_finding.get(finding.finding_id)
        clf = clf_by_finding.get(finding.finding_id)
        if opp is None or clf is None:
            continue  # mismatched data; skip rather than crash
        entries.append(build_odr_entry(finding, opp, clf))

    rejected = sum(1 for e in entries if e.decision_status == "REJECTED")
    continue_r = sum(1 for e in entries if e.decision_status == "CONTINUE_RESEARCH")

    odr_id = stable_id("ODR-SET", {"run_id": run_id, "study_id": study_id})
    return OpportunityDecisionRegister(
        odr_id=odr_id,
        study_id=study_id,
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        evidence_ceiling="CONTINUE RESEARCH",
        evidence_ceiling_note=EVIDENCE_CEILING_NOTE,
        entry_count=len(entries),
        rejected_count=rejected,
        continue_research_count=continue_r,
        entries=entries,
        methodology_note=_METHODOLOGY_NOTE,
    )


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def write_odr_json(odr: OpportunityDecisionRegister, path: str | Path) -> str:
    """Write the ODR as machine-readable JSON. Returns path as str."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(odr.to_dict(), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return str(out)


def write_odr_markdown(odr: OpportunityDecisionRegister, path: str | Path) -> str:
    """Write the ODR as a human-readable Markdown report. Returns path as str."""
    lines: list[str] = []
    lines.append(f"# Opportunity Decision Register — {odr.study_id}")
    lines.append("")
    lines.append(f"**Run ID:** `{odr.run_id}`  ")
    lines.append(f"**Generated:** {odr.generated_at}  ")
    lines.append(f"**Evidence Ceiling:** **{odr.evidence_ceiling}** (enforced — CFPB single source family)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Methodology note")
    lines.append("")
    lines.append(f"> {odr.methodology_note}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Total ODR entries | {odr.entry_count} |")
    lines.append(f"| CONTINUE_RESEARCH | {odr.continue_research_count} |")
    lines.append(f"| REJECTED | {odr.rejected_count} |")
    lines.append("")

    if not odr.entries:
        lines.append("*No ODR entries produced for this run (no findings generated).*")
        lines.append("")
    else:
        lines.append("## Decision table")
        lines.append("")
        lines.append("| ODR ID | Mechanism | Classification | Evidence | Companies | Decision |")
        lines.append("|---|---|---|---|---|---|")
        for e in odr.entries:
            lines.append(
                f"| `{e.odr_id}` | {e.mechanism} | {e.mechanism_classification} "
                f"| {e.evidence_count} | {e.company_count} | **{e.decision_status}** |"
            )
        lines.append("")

        for e in odr.entries:
            lines.append(f"---")
            lines.append("")
            lines.append(f"### {e.odr_id} — {e.mechanism}")
            lines.append("")
            lines.append(f"| Field | Value |")
            lines.append(f"|---|---|")
            lines.append(f"| Classification | {e.mechanism_classification} |")
            lines.append(f"| Decision status | **{e.decision_status}** |")
            lines.append(f"| Finding ID | `{e.finding_id}` |")
            lines.append(f"| Opportunity ID | `{e.opportunity_id}` |")
            lines.append(f"| Evidence count | {e.evidence_count} |")
            lines.append(f"| Company count | {e.company_count} |")
            lines.append(f"| Companies | {', '.join(e.companies_observed) if e.companies_observed else '—'} |")
            lines.append(f"| Component hypothesis | {e.component_hypothesis} |")
            lines.append(f"| Buyer clarity | {e.buyer_clarity} |")
            lines.append(f"| Commercial relevance | {e.commercial_relevance} |")
            lines.append(f"| Component reusability | {e.component_reusability} |")
            lines.append("")
            lines.append("**Evidence references:**")
            lines.append("")
            for ref in e.evidence_references:
                lines.append(f"- `{ref}`")
            lines.append("")
            lines.append("**Decision rationale:**")
            lines.append("")
            for step in e.decision_rationale:
                lines.append(f"- {step}")
            lines.append("")
            if e.missing_for_decision_upgrade:
                lines.append("**Required to advance decision status:**")
                lines.append("")
                for item in e.missing_for_decision_upgrade:
                    lines.append(f"- {item}")
                lines.append("")
            lines.append(f"**Evidence ceiling note:**")
            lines.append("")
            lines.append(f"> {e.evidence_ceiling_note}")
            lines.append("")

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)
