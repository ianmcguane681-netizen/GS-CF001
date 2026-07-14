from connectors.base import RetrievalResult
from connectors.cfpb import cfpb_source
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
    assert result.artifacts["raw"]
    assert result.artifacts["report_markdown"]

