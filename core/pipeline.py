from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from connectors.base import DiscoveryConnector, RetrievalResult
from connectors.cfpb import CFPBConnector
from connectors.courtlistener import CourtListenerConnector, SOURCE_FAMILY as COURT_FAMILY
from connectors.fjc_idb import FJCIDBConnector
from core.ai_governance import deterministic_analysis_artifact
from core.manifest import build_run_manifest
from core.models import PipelineResult
from core.normalization import normalise_cfpb_records, normalise_court_records, normalise_idb_records
from core.opportunity_decision_register import build_odr, write_odr_json, write_odr_markdown
from core.run_index import append_run_index, build_run_index_entry
from core.storage import file_checksum, run_timestamp, write_json_artifact
from findings.engine import generate_findings
from findings.mechanism_classifier import classify_all
from opportunity.assessment import assess_findings
from proof_gates.evaluator import evaluate_proof_gates, make_verdict
from reports.report_generator import write_json_report, write_markdown_report
from studies.definitions import get_study
from verification.classifier import verify_candidates


def _normalise_for_source(retrieval: "RetrievalResult", study) -> list:
    """Route each source family to the normaliser that understands its records.

    Dispatching on source family rather than connector type keeps the pipeline
    open to further families without another branch here per connector class.

    Source type is checked before family because the FJC Integrated Database
    deliberately shares the court records family: it raises evidentiary standing
    rather than independence, so family alone no longer identifies a normaliser.
    """

    if retrieval.source.source_type == "federal_judicial_outcomes":
        return normalise_idb_records(retrieval.records, retrieval.source, study)
    if retrieval.source.source_family == COURT_FAMILY:
        return normalise_court_records(retrieval.records, retrieval.source, study)
    return normalise_cfpb_records(retrieval.records, retrieval.source, study)


def _load_ledger(path: Path, *, to_competitor: bool = False) -> list:
    """Read an optional commercial ledger, tolerating its absence.

    These are produced outside the study run -- pricing by `market.pricing_cli`,
    buyer records by a human conversation -- so a missing file is the ordinary
    case and must not be an error.
    """

    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not to_competitor:
        return rows
    from market.pricing import PricingObservation, to_sv_competitor

    competitors = []
    for row in rows:
        try:
            observation = PricingObservation(
                **{**row, "limitations": tuple(row.get("limitations", ()))}
            )
        except TypeError:
            continue
        competitors.append(to_sv_competitor(observation))
    return competitors


def run_credit_reporting_proof(
    limit: int = 1,
    connector: DiscoveryConnector | None = None,
    data_dir: str | Path = "data",
    connectors: Sequence[DiscoveryConnector] | None = None,
) -> PipelineResult:
    """Run the study across one or more independent source families.

    `connector` remains for a single-source run. `connectors` runs several: each
    family is retrieved and normalised by its own rules, and the results are
    pooled before verification so the evidence ceiling sees every family present.
    A family that fails to retrieve contributes its diagnostics and no records,
    which is a transparent partial run rather than a silent one.
    """

    study = get_study("GS-CF001-C")
    if connectors is None:
        connectors = [connector or CFPBConnector()]

    # One timestamp shared by every artifact this run produces, so the full
    # set of a run's files can always be found and grouped by this stamp
    # alone, and no run's files collide with another run's.
    stamp = run_timestamp()

    base = Path(data_dir)
    retrievals = [item.retrieve(limit=limit) for item in connectors]
    retrieval = retrievals[0]
    raw_path = write_json_artifact(
        [
            {
                "source": item.source.to_dict(),
                "retrieval_url": item.retrieval_url,
                "retrieved_at": item.retrieved_at,
                "access_method": item.access_method,
                "errors": item.errors,
                "records": item.records,
            }
            for item in retrievals
        ],
        base / "raw",
        "cfpb_credit_reporting_raw",
        timestamp=stamp,
    )
    diagnostics = [item for r in retrievals for item in (r.diagnostics or [])]
    source_reliability = [r.source_reliability for r in retrievals if r.source_reliability]
    diagnostics_path = write_json_artifact([diagnostic.to_dict() for diagnostic in diagnostics], base / "exports", "access_diagnostics", timestamp=stamp)
    reliability_path = write_json_artifact([item.to_dict() for item in source_reliability], base / "exports", "source_reliability", timestamp=stamp)

    candidates = [
        candidate
        for item in retrievals
        for candidate in _normalise_for_source(item, study)
    ]
    verified = verify_candidates(candidates)
    findings = generate_findings(verified)
    opportunities = assess_findings(findings)

    # Mechanism classification: deterministic six-category classification of every
    # finding. Produces one MechanismClassification per finding — no AI used.
    classifications = classify_all(findings, verified)

    # Opportunity Decision Register: one ODREntry per finding/opportunity pair,
    # with full reasoning chain, commercial assessment, decision status, and
    # Evidence Ceiling enforcement note. No AI used.
    odr = build_odr(
        study_id=study.study_id,
        run_id="",  # placeholder; replaced after manifest is built below
        findings=findings,
        opportunities=opportunities,
        classifications=classifications,
    )

    analysis_artifacts = [
        deterministic_analysis_artifact(
            [item.evidence_id for item in verified],
            {
                "verification_count": len(verified),
                "finding_count": len(findings),
                "opportunity_count": len(opportunities),
                "classification_count": len(classifications),
                "odr_entry_count": odr.entry_count,
                "ai_used": False,
            },
            affected_finding_or_verdict=bool(findings or opportunities),
        )
    ]
    # Competitor and buyer material reach PG-11 and PG-12 through their own
    # parameters, never through `verified`. Both ledgers are optional and default
    # to empty: an absent ledger leaves those gates failing for want of research,
    # which is the honest state, rather than being silently skipped.
    competitors = _load_ledger(base / "market_pricing.json", to_competitor=True)
    buyers = _load_ledger(base / "buyer_evidence.json")
    gates = evaluate_proof_gates(
        verified,
        findings,
        opportunities,
        source_reliability,
        diagnostics,
        competitors=competitors,
        buyer_evidence=buyers,
    )
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
        mechanism_classifications=classifications,
        odr_entries=list(odr.entries),
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
    # Mechanism classifications and ODR written with placeholder run_id;
    # the final ODR with correct run_id is written after manifest is built.
    classifications_path = write_json_artifact(
        [c.to_dict() for c in classifications],
        base / "exports", "mechanism_classifications", timestamp=stamp,
    )
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
        classifications_path,
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

    # Rebuild ODR with the real run_id now that the manifest is available.
    odr = build_odr(
        study_id=study.study_id,
        run_id=manifest.run_id,
        findings=findings,
        opportunities=opportunities,
        classifications=classifications,
    )
    odr_json_path = write_odr_json(odr, base / "exports" / f"odr_{stamp}.json")
    odr_md_path = write_odr_markdown(odr, base / "exports" / f"odr_{stamp}.md")

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
        "mechanism_classifications": classifications_path,
        "processed": processed_path,
        "report_json": report_json_path,
        "report_markdown": report_md_path,
        "odr_json": odr_json_path,
        "odr_markdown": odr_md_path,
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
        mechanism_classifications=classifications,
        odr_entries=list(odr.entries),
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
    parser.add_argument(
        "--sources",
        default="cfpb",
        help=(
            "Comma-separated sources: cfpb, court, fjc. Two families lift the evidence "
            "ceiling; fjc adds adjudicated standing and needs COURTLISTENER_API_TOKEN."
        ),
    )
    args = parser.parse_args()
    available = {"cfpb": CFPBConnector, "court": CourtListenerConnector, "fjc": FJCIDBConnector}
    chosen = [name.strip().lower() for name in args.sources.split(",") if name.strip()]
    unknown = sorted(set(chosen) - set(available))
    if unknown:
        parser.error(f"unknown source(s): {', '.join(unknown)}; choose from {sorted(available)}")
    result = run_credit_reporting_proof(
        limit=args.limit,
        data_dir=args.data_dir,
        connectors=[available[name]() for name in chosen],
    )
    print(json.dumps({
        "verdict": result.verdict.to_dict() if result.verdict else None,
        "artifacts": result.artifacts,
        "classification_count": len(result.mechanism_classifications),
        "odr_entry_count": len(result.odr_entries),
        "source_families": sorted({
            item.source_family for item in result.verified_evidence if item.source_family
        }),
        "occurrence_established": sum(
            1 for item in result.verified_evidence if item.establishes_occurrence
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
