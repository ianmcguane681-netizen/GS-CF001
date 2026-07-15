from connectors.base import RetrievalResult
from connectors.cfpb import cfpb_reliability_assessment, cfpb_source
from core.models import AccessDiagnostic
from core.pipeline import run_credit_reporting_proof


class FakeCFPBConnector:
    source = cfpb_source()

    def retrieve(self, limit: int = 1):
        return RetrievalResult(
            source=self.source,
            retrieval_url="https://consumerfinance.gov/api",
            retrieved_at="2026-07-14T00:00:00Z",
            errors=[],
            records=[
                {
                    "complaint_id": "1",
                    "product": "Credit reporting or other personal consumer reports",
                    "issue": "Incorrect information on your report",
                    "company": "Example Financial",
                    "complaint_what_happened": "I disputed incorrect information and the investigation did not correct it.",
                    "_retrieval_url": "https://consumerfinance.gov/api",
                    "_retrieved_at": "2026-07-14T00:00:00Z",
                }
            ],
            access_method="official_cfpb_search_api",
            diagnostics=[
                AccessDiagnostic(
                    "ADIAG-1",
                    "https://consumerfinance.gov/api",
                    "2026-07-14T00:00:00Z",
                    "test",
                    "GET",
                    {"Accept": "application/json"},
                    "200",
                    {},
                    "Retrieved one record.",
                    "not retried",
                    "Test retrieval succeeded.",
                    "official_cfpb_search_api",
                )
            ],
            source_reliability=cfpb_reliability_assessment("official_cfpb_search_api", "2026-07-14T00:00:00Z"),
        )


def test_credit_reporting_pipeline_preserves_and_traces_all_stages(tmp_path):
    result = run_credit_reporting_proof(limit=1, connector=FakeCFPBConnector(), data_dir=tmp_path)

    assert result.source_records
    assert result.candidates
    assert result.verified_evidence
    assert result.findings
    assert result.opportunities
    assert result.gates
    assert result.verdict is not None
    assert result.verdict.outcome == "CONTINUE RESEARCH"
    assert result.verdict.evidence_ceiling == "CONTINUE RESEARCH"
    assert result.artifacts["raw"]
    assert result.artifacts["report_markdown"]
    assert result.artifacts["run_manifest"]
    assert result.run_manifest is not None
    assert result.access_diagnostics
    assert result.source_reliability
    assert result.artifacts["normalised_candidates"]
    assert result.artifacts["findings"]
    assert result.artifacts["opportunities"]


def test_pipeline_writes_timestamped_reports_and_append_only_run_index(tmp_path):
    from pathlib import Path
    import json

    result_one = run_credit_reporting_proof(limit=1, connector=FakeCFPBConnector(), data_dir=tmp_path)
    result_two = run_credit_reporting_proof(limit=1, connector=FakeCFPBConnector(), data_dir=tmp_path)

    # Each run's Markdown/JSON reports get distinct, timestamped filenames --
    # a second run must never overwrite the first run's report.
    assert result_one.artifacts["report_json"] != result_two.artifacts["report_json"]
    assert result_one.artifacts["report_markdown"] != result_two.artifacts["report_markdown"]
    assert Path(result_one.artifacts["report_json"]).exists()
    assert Path(result_two.artifacts["report_json"]).exists()

    # Per-run candidates/findings/opportunities artifacts exist independently
    # of the combined processed bundle, and are distinct per run.
    assert result_one.artifacts["normalised_candidates"] != result_two.artifacts["normalised_candidates"]
    assert Path(result_one.artifacts["normalised_candidates"]).exists()
    assert Path(result_one.artifacts["findings"]).exists()
    assert Path(result_one.artifacts["opportunities"]).exists()

    # The run index is append-only: after two runs it holds two entries, the
    # first run's entry is untouched, and both runs are recorded.
    index_path = tmp_path / "exports" / "run_index.json"
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(entries) == 2
    assert entries[0]["run_id"] == result_one.run_manifest.run_id
    assert entries[1]["run_id"] == result_two.run_manifest.run_id
    assert entries[0]["artifact_paths"]["report_json"] == result_one.artifacts["report_json"]
