"""The pipeline must be able to run more than one source family.

The board's first review failed this study's proof bundle partly because the run
recorded a single source family, which caps the verdict at CONTINUE RESEARCH
however good the evidence is. The pipeline could only ever take one connector, so
the cap was structural rather than evidential.
"""
from __future__ import annotations

from typing import Any

from connectors.base import RetrievalResult
from connectors.cfpb import cfpb_reliability_assessment, cfpb_source
from connectors.courtlistener import courtlistener_reliability_assessment, courtlistener_source
from core.pipeline import _normalise_for_source, run_credit_reporting_proof
from studies.definitions import get_study

STUDY = get_study("GS-CF001-C")
NOW = "2026-07-26T00:00:00Z"


class StubConnector:
    def __init__(self, source, records, reliability):
        self.source = source
        self._records = records
        self._reliability = reliability

    def retrieve(self, limit: int = 1) -> RetrievalResult:
        return RetrievalResult(
            self.source,
            "https://example.test/query",
            NOW,
            [dict(item, _retrieved_at=NOW) for item in self._records[:limit]],
            [],
            access_method="stub",
            diagnostics=[],
            source_reliability=self._reliability,
        )


def cfpb_records() -> list[dict[str, Any]]:
    return [
        {
            "complaint_id": str(index),
            "product": "Credit reporting or other personal consumer reports",
            "issue": "Incorrect information on your report",
            "company": f"Company {index}",
            "complaint_what_happened": (
                "My dispute investigation failed to remove inaccurate information "
                "from my credit report after I submitted documentation."
            ),
            "_retrieval_url": "https://consumerfinance.gov/api",
        }
        for index in range(3)
    ]


def court_records() -> list[dict[str, Any]]:
    return [
        {
            "docket_id": str(900 + index),
            "case_name": f"Consumer {index} v. TRANS UNION, LLC",
            "court": "District Court, E.D. Pennsylvania",
            "court_id": "paed",
            "docket_number": f"2:26-cv-0{index}",
            "date_filed": "2026-07-24",
            "cause": "15:1681 Fair Credit Reporting Act",
            "suit_nature": "480 Other Statutes: Consumer Credit",
            "parties": ["Consumer", "TRANS UNION, LLC"],
            "_source_record_id": str(900 + index),
            "_retrieval_url": "https://www.courtlistener.com/docket/x/",
        }
        for index in range(3)
    ]


def cfpb_stub() -> StubConnector:
    return StubConnector(cfpb_source(), cfpb_records(), cfpb_reliability_assessment("stub", NOW))


def court_stub() -> StubConnector:
    return StubConnector(
        courtlistener_source(), court_records(), courtlistener_reliability_assessment("stub", NOW)
    )


def test_records_are_routed_to_the_normaliser_for_their_family():
    """Dispatch is on source family, so a new family needs no branch per connector."""
    court = _normalise_for_source(court_stub().retrieve(limit=3), STUDY)
    cfpb = _normalise_for_source(cfpb_stub().retrieve(limit=3), STUDY)

    assert court and all(item.parsed_fields.get("cause") for item in court)
    assert cfpb and all(item.parsed_fields.get("complaint_id") for item in cfpb)


def test_a_single_family_run_is_still_capped(tmp_path):
    result = run_credit_reporting_proof(
        limit=3, data_dir=tmp_path, connectors=[cfpb_stub()]
    )

    assert result.verdict.independent_source_family_count == 1
    assert result.verdict.evidence_ceiling == "CONTINUE RESEARCH"


def test_two_families_lift_the_ceiling(tmp_path):
    result = run_credit_reporting_proof(
        limit=3, data_dir=tmp_path, connectors=[cfpb_stub(), court_stub()]
    )

    families = sorted({item.source_family for item in result.verified_evidence if item.source_family})
    assert families == ["CFPB complaints", "Federal court records"]
    assert result.verdict.independent_source_family_count == 2
    assert result.verdict.evidence_ceiling == "BUILD CANDIDATE"
    # The remaining gates still hold the verdict down; the cap is simply no longer
    # the thing doing it.
    assert result.verdict.outcome == "CONTINUE RESEARCH"


def test_every_family_contributes_its_reliability_assessment(tmp_path):
    result = run_credit_reporting_proof(
        limit=3, data_dir=tmp_path, connectors=[cfpb_stub(), court_stub()]
    )

    assert sorted(item.source_family for item in result.source_reliability) == [
        "CFPB complaints",
        "Federal court records",
    ]


def test_the_default_run_is_unchanged(tmp_path):
    """Callers passing a single connector keep the previous behaviour."""
    result = run_credit_reporting_proof(limit=3, connector=cfpb_stub(), data_dir=tmp_path)

    assert result.verdict.independent_source_family_count == 1
