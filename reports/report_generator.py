from __future__ import annotations

import json
from pathlib import Path

from core.ids import utc_now
from core.models import Finding, OpportunityHypothesis, PipelineResult, StudyVerdict, VerifiedEvidence


def write_json_report(result: PipelineResult, path: str | Path) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return str(output)


def render_markdown_report(
    verdict: StudyVerdict,
    evidence: list[VerifiedEvidence],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
) -> str:
    lines = [
        "# GS-CF001-C Traceable Verdict Report",
        "",
        f"Generated: {utc_now()}",
        "",
        f"Verdict: {verdict.outcome}",
        "",
        "## Evidence",
    ]
    for item in evidence:
        lines.append(f"- `{item.evidence_id}` from candidate `{item.candidate_id}`: {item.verification_status}; mechanism `{item.mechanism}`.")
    lines.extend(["", "## Findings"])
    for finding in findings:
        linked = ", ".join(f"`{evidence_id}`" for evidence_id in finding.evidence_ids)
        lines.append(f"- `{finding.finding_id}`: {finding.status}; supported by {linked}; missing: {', '.join(finding.missing_evidence) or 'none'}.")
    lines.extend(["", "## Opportunity Assessment"])
    for opportunity in opportunities:
        linked = ", ".join(f"`{evidence_id}`" for evidence_id in opportunity.evidence_ids)
        lines.append(
            f"- `{opportunity.opportunity_id}`: {opportunity.status}; component `{opportunity.component_hypothesis}`; "
            f"supported by {linked}; missing: {', '.join(opportunity.missing_evidence) or 'none'}."
        )
    lines.extend(["", "## Proof Gates"])
    for gate in verdict.proof_gates:
        linked = ", ".join(f"`{evidence_id}`" for evidence_id in gate.evidence_ids) or "no evidence"
        lines.append(
            f"- {gate.gate_name}: {gate.status}; confidence {gate.confidence}; evidence {linked}; "
            f"missing: {', '.join(gate.missing_evidence) or 'none'}; next action: {gate.recommended_next_action}"
        )
    lines.extend(["", "## Verdict Reasoning"])
    for reason in verdict.reasoning_chain:
        lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"


def write_markdown_report(
    verdict: StudyVerdict,
    evidence: list[VerifiedEvidence],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
    path: str | Path,
) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown_report(verdict, evidence, findings, opportunities), encoding="utf-8")
    return str(output)

