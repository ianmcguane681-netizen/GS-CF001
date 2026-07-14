from __future__ import annotations

import json
from pathlib import Path

from core.ids import utc_now
from core.models import AccessDiagnostic, Finding, OpportunityHypothesis, PipelineResult, RunManifest, SourceReliabilityAssessment, StudyVerdict, VerifiedEvidence


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
    source_reliability: list[SourceReliabilityAssessment] | None = None,
    access_diagnostics: list[AccessDiagnostic] | None = None,
    run_manifest: RunManifest | None = None,
) -> str:
    source_reliability = source_reliability or []
    access_diagnostics = access_diagnostics or []
    lines = [
        "# GS-CF001-C Traceable Verdict Report",
        "",
        f"Generated: {utc_now()}",
        "",
        f"Unconstrained Assessment: {verdict.unconstrained_outcome}",
        f"Evidence Ceiling: {verdict.evidence_ceiling}",
        f"Evidence Ceiling Reason: {verdict.evidence_ceiling_reason}",
        f"Final Verdict: {verdict.final_permitted_outcome}",
        f"Required Next Evidence: {', '.join(verdict.evidence_required_to_remove_ceiling) or 'none'}",
        "",
        "## Source Reliability",
    ]
    if not source_reliability:
        lines.append("- No source reliability assessment was available.")
    for assessment in source_reliability:
        lines.append(f"- `{assessment.source_id}` {assessment.source_name}; family `{assessment.source_family}`; method `{assessment.retrieval_method}`.")
        lines.append(f"  - Representativeness warning: {assessment.representativeness_warning}")
        lines.append(f"  - Data completeness warning: {assessment.data_completeness_warning}")
        lines.append(f"  - Verification constraints: {'; '.join(assessment.verification_constraints)}")
        lines.append(f"  - Prohibited inferences: {'; '.join(assessment.prohibited_inferences)}")
    lines.extend([
        "",
        "## Access Diagnostics",
    ])
    if not access_diagnostics:
        lines.append("- No access diagnostics were recorded.")
    for diagnostic in access_diagnostics:
        lines.append(
            f"- `{diagnostic.diagnostic_id}` method `{diagnostic.access_method}` endpoint `{diagnostic.endpoint}` "
            f"status `{diagnostic.response_status}`; interpretation: {diagnostic.final_interpretation}"
        )
    lines.extend([
        "",
        "## Evidence",
    ])
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
            f"- {gate.gate_id} {gate.gate_name}: {gate.status}; threshold `{gate.threshold}`; observed `{gate.observed_value}`; "
            f"confidence {gate.confidence}; evidence {linked}; missing: {', '.join(gate.missing_evidence) or 'none'}; "
            f"constrains max verdict: {gate.constrains_max_verdict}; next action: {gate.recommended_next_action}"
        )
    lines.extend(["", "## Verdict Reasoning"])
    for reason in verdict.reasoning_chain:
        lines.append(f"- {reason}")
    if run_manifest:
        lines.extend([
            "",
            "## Run Manifest",
            f"- Run ID: `{run_manifest.run_id}`",
            f"- Code commit: `{run_manifest.code_commit_hash}`",
            f"- Methodology version: `{run_manifest.methodology_version}`",
            f"- Source access method: `{run_manifest.source_access_method}`",
            f"- AI model configuration: {run_manifest.ai_model_configuration}",
        ])
    return "\n".join(lines) + "\n"


def write_markdown_report(
    verdict: StudyVerdict,
    evidence: list[VerifiedEvidence],
    findings: list[Finding],
    opportunities: list[OpportunityHypothesis],
    path: str | Path,
    source_reliability: list[SourceReliabilityAssessment] | None = None,
    access_diagnostics: list[AccessDiagnostic] | None = None,
    run_manifest: RunManifest | None = None,
) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_markdown_report(verdict, evidence, findings, opportunities, source_reliability, access_diagnostics, run_manifest),
        encoding="utf-8",
    )
    return str(output)
