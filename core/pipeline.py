from __future__ import annotations

import argparse
import json
from pathlib import Path

from connectors.base import DiscoveryConnector
from connectors.cfpb import CFPBConnector
from core.models import PipelineResult
from core.normalization import normalise_cfpb_records
from core.storage import write_json_artifact
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

    base = Path(data_dir)
    raw_path = write_json_artifact(
        {
            "source": retrieval.source.to_dict(),
            "retrieval_url": retrieval.retrieval_url,
            "retrieved_at": retrieval.retrieved_at,
            "errors": retrieval.errors,
            "records": retrieval.records,
        },
        base / "raw",
        "cfpb_credit_reporting_raw",
    )

    candidates = normalise_cfpb_records(retrieval.records, retrieval.source, study)
    verified = verify_candidates(candidates)
    findings = generate_findings(verified)
    opportunities = assess_findings(findings)
    gates = evaluate_proof_gates(verified, findings, opportunities)
    verdict = make_verdict(study.study_id, gates, findings, opportunities)

    result = PipelineResult(
        source_records=retrieval.records,
        candidates=candidates,
        verified_evidence=verified,
        findings=findings,
        opportunities=opportunities,
        gates=gates,
        verdict=verdict,
    )
    processed_path = write_json_artifact(result.to_dict(), base / "processed", "gs_cf001_c_processed")
    report_json_path = write_json_report(result, base / "exports" / "gs_cf001_c_report.json")
    report_md_path = write_markdown_report(verdict, verified, findings, opportunities, base / "exports" / "gs_cf001_c_report.md")
    result.artifacts.update(
        {
            "raw": raw_path,
            "processed": processed_path,
            "report_json": report_json_path,
            "report_markdown": report_md_path,
        }
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

