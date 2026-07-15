from __future__ import annotations

import argparse
import json
from pathlib import Path

from connectors.base import DiscoveryConnector
from connectors.cfpb import CFPBConnector
from core.ai_governance import deterministic_analysis_artifact
from core.manifest import build_run_manifest
from core.models import PipelineResult
from core.normalization import normalise_cfpb_records
from core.run_index import append_run_index, build_run_index_entry
from core.storage import file_checksum, run_timestamp, write_json_artifact
from findings.engine import generate_findings
from opportunity.assessment import assess_findings
from proof_gates.evaluator import evaluate_proof_gates, make_verdict
from reports.report_generator import write_json_report, write_markdown_report
from studies.definitions import get_study
from verification.classifier import verify_candidates


def run_credit_reporting_proof(
    limit: int = 1,
    connector: DiscoveryConnector | None = None,
    data_dir: str | Path = "data",
) -> PipelineResult:
    study = get_study("GS-CF001-C")
    connector = connector or CFPBConnector()
    retrieval = connector.retrieve(limit=limit)

    # One timestamp shared by every artifact this run produces, so the full
    # set of a run's files can always be found and grouped by this stamp
    # alone, and no run's files collide with another run's.
    stamp = run_timestamp()

    base = Path(data_dir)
    raw_path = write_json_artifact(
        {
            "source": retrieval.source.to_dict(),
            "retrieval_url": retrieval.retrieval_url,
            "retrieved_at": retrieval.retrieved_at,
            "access_method": retrieval.access_method,
            "errors": retrieval.errors,
            "records": retrieval.records,
        },
        base / "raw",
        "cfpb_credit_reporting_raw",
        timestamp=stamp,
    )
    diagnostics = retrieval.diagnostics or []
    source_reliability = [retrieval.source_reliability] if retrieval.source_reliability else []
    diagnostics_path = write_json_artifact([diagnostic.to_dict() for diagnostic in diagnostics], base / "exports", "access_diagnostics", timestamp=stamp)
    reliability_path = write_json_artifact([item.to_dict() for item in source_reliability], base / "exports", "source_reliability", timestamp=stamp)

    candidates = normalise_cfpb_records(retrieval.records, retrieval.source, study)
    verified = verify_candidates(candidates)
    findings = generate_findings(verified)
    opportunities = assess_findings(findings)
    analysis_artifacts = [
        deterministic_analysis_artifact(
            [item.evidence_id for item in verified],
            {
                "verification_count": len(verified),
                "finding_count": len(findings),
                "opportunity_count": len(opportunities),
                "ai_used": False,
            },
            affected_finding_or_verdict=bool(findings or opportunities),
        )
    ]
    gates = evaluate_proof_gates(verified, findings, opportunities, source_reliability, diagnostics)
    verdict = make_verdict(study.study_id, gates, findings, opportunities, verified)
    state_transitions = []
    for candidate in candidates:
        state_transitions.extend(candidate.state_transitions)
    for item in verified:
        state_transitions.extend(item.state_transitions)

    result_without_manifest = PipelineResult(
        source_records=retrieval.records,
        candidates=candidates,
        verified_evidence=verified,
        findings=findings,
        opportunities=opportunities,
        gates=gates,
        verdict=verdict,
        source_reliability=source_reliability,
        access_diagnostics=diagnostics,
        analysis_artifacts=analysis_artifacts,
        state_transitions=[],
    )
    analysis_path = write_json_artifact([artifact.to_dict() for artifact in analysis_artifacts], base / "exports", "analysis_artifacts", timestamp=stamp)
    verification_path = write_json_artifact([item.to_dict() for item in verified], base / "exports", "verification_artifacts", timestamp=stamp)
    proof_gate_path = write_json_artifact([gate.to_dict() for gate in gates], base / "exports", "proof_gate_results", timestamp=stamp)
    audit_path = write_json_artifact(state_transitions, base / "exports", "audit_trail", timestamp=stamp)
    # Per-run artifacts for normalised candidates, findings, and opportunities,
    # in addition to (not instead of) the combined processed bundle below --
    # these let each stage be inspected, diffed, or archived independently
    # without unpacking the whole processed file.
    candidates_path = write_json_artifact([candidate.to_dict() for candidate in candidates], base / "exports", "normalised_candidates", timestamp=stamp)
    findings_path = write_json_artifact([finding.to_dict() for finding in findings], base / "exports", "findings", timestamp=stamp)
    opportunities_path = write_json_artifact([opportunity.to_dict() for opportunity in opportunities], base / "exports", "opportunities", timestamp=stamp)
    processed_path = write_json_artifact(result_without_manifest.to_dict(), base / "processed", "gs_cf001_c_processed", timestamp=stamp)
    report_json_path = write_json_report(result_without_manifest, base / "exports" / f"gs_cf001_c_report_{stamp}.json")
    report_md_path = write_markdown_report(
        verdict,
        verified,
        findings,
        opportunities,
        base / "exports" / f"gs_cf001_c_report_{stamp}.md",
        source_reliability,
        diagnostics,
    )
    output_paths = [
        raw_path,
        diagnostics_path,
        reliability_path,
        analysis_path,
        verification_path,
        proof_gate_path,
        audit_path,
        candidates_path,
        findings_path,
        opportunities_path,
        processed_path,
        report_json_path,
        report_md_path,
    ]
    manifest = build_run_manifest(
        study_id=study.study_id,
        source_access_method=retrieval.access_method,
        retrieval_timestamps=[retrieval.retrieved_at],
        input_record_identifiers=[str(record.get("complaint_id") or record.get("_source_record_id") or "") for record in retrieval.records],
        output_artifact_list=output_paths,
        final_verdict=verdict.outcome,
        evidence_ceiling=verdict.evidence_ceiling,
        errors=retrieval.errors,
        warnings=verdict.missing_evidence,
    )
    manifest_path = write_json_artifact(manifest.to_dict(), base / "exports", "run_manifest", timestamp=stamp)
    output_paths.append(manifest_path)
    artifacts = {
        "raw": raw_path,
        "access_diagnostics": diagnostics_path,
        "source_reliability": reliability_path,
        "analysis_artifacts": analysis_path,
        "verification_artifacts": verification_path,
        "proof_gate_results": proof_gate_path,
        "audit_trail": audit_path,
        "normalised_candidates": candidates_path,
        "findings": findings_path,
        "opportunities": opportunities_path,
        "processed": processed_path,
        "report_json": report_json_path,
        "report_markdown": report_md_path,
        "run_manifest": manifest_path,
    }
    result = PipelineResult(
        source_records=retrieval.records,
        candidates=candidates,
        verified_evidence=verified,
        findings=findings,
        opportunities=opportunities,
        gates=gates,
        verdict=verdict,
        source_reliability=source_reliability,
        access_diagnostics=diagnostics,
        analysis_artifacts=analysis_artifacts,
        state_transitions=[],
        run_manifest=manifest,
        artifacts=artifacts,
    )
    write_json_report(result, base / "exports" / f"gs_cf001_c_report_{stamp}.json")
    write_markdown_report(verdict, verified, findings, opportunities, base / "exports" / f"gs_cf001_c_report_{stamp}.md", source_reliability, diagnostics, manifest)
    # Compute checksums from the final on-disk state of every artifact — AFTER
    # the second report writes above, which overwrite the preliminary versions
    # that build_run_manifest checksummed. Using manifest.artifact_checksums
    # here would record stale pre-overwrite hashes for the report files.
    final_checksums = {path: file_checksum(path) for path in artifacts.values()}
    append_run_index(
        build_run_index_entry(
            run_id=manifest.run_id,
            timestamp=stamp,
            study_id=study.study_id,
            verdict=verdict.final_permitted_outcome,
            evidence_ceiling=verdict.evidence_ceiling,
            source_access_method=retrieval.access_method,
            artifact_paths=artifacts,
            artifact_checksums=final_checksums,
        ),
        path=base / "exports" / "run_index.json",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GS-CF001-C Credit Reporting Disputes proof pipeline.")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    result = run_credit_reporting_proof(limit=args.limit, data_dir=args.data_dir)
    print(json.dumps({"verdict": result.verdict.to_dict() if result.verdict else None, "artifacts": result.artifacts}, indent=2))


if __name__ == "__main__":
    main()
