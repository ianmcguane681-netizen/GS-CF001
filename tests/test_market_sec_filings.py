"""The market lane must stay sealed off from the evidence study.

Market evidence answers "who already solves this and at what scale". It must never
corroborate that consumer harm occurred, and must never contribute to the
independent source family count that governs the evidence ceiling.
"""
from __future__ import annotations

from typing import Any

import pytest

from market.models import COMPETITIVE_MARKET_CLASS, MarketEvidence
from market.sec_filings import (
    CREDIT_REPORTING_SIC,
    SECAccessError,
    SECFilingsConnector,
    is_annual_period,
    latest_annual_revenue,
)

ANNUAL_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"


def fact(start: str, end: str, val: int, filed: str, form: str = "10-K", accn: str = "a") -> dict[str, Any]:
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form, "accn": accn, "fy": end[:4]}


def facts_payload(entries: list[dict[str, Any]], tag: str = ANNUAL_TAG) -> dict[str, Any]:
    return {"facts": {"us-gaap": {tag: {"units": {"USD": entries}}}}}


def submissions(name: str = "TransUnion", sic: str = CREDIT_REPORTING_SIC) -> dict[str, Any]:
    return {
        "name": name,
        "sic": sic,
        "sicDescription": "Services-Consumer Credit Reporting, Collection Agencies",
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q", "10-K"],
                "filingDate": ["2026-02-27", "2026-04-28", "2025-02-13"],
                "accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-25-000003"],
                "primaryDocument": ["tru-20251231.htm", "tru-20260331.htm", "tru-20241231.htm"],
            }
        },
    }


def connector_for(mapping: dict[str, dict[str, Any]], **kwargs) -> SECFilingsConnector:
    def fetch(url: str) -> dict[str, Any]:
        for fragment, payload in mapping.items():
            if fragment in url:
                return payload
        raise SECAccessError(f"no stub for {url}")

    return SECFilingsConnector(fetch_json=fetch, **kwargs)


def test_quarterly_periods_are_not_treated_as_annual():
    """A 10-K carries quarterly breakdowns; counting one as a year understates by ~4x."""
    assert is_annual_period(fact("2025-01-01", "2025-12-31", 1, "2026-02-27")) is True
    assert is_annual_period(fact("2025-01-01", "2025-03-31", 1, "2026-02-27")) is False
    assert is_annual_period({"start": None, "end": "2025-12-31"}) is False


def test_only_annual_figures_are_returned():
    payload = facts_payload(
        [
            fact("2025-01-01", "2025-03-31", 940_300_000, "2026-02-27"),
            fact("2025-01-01", "2025-06-30", 1_900_000_000, "2026-02-27"),
            fact("2025-01-01", "2025-12-31", 4_576_300_000, "2026-02-27"),
        ]
    )

    rows = latest_annual_revenue(payload)

    assert [row["val"] for row in rows] == [4_576_300_000]


def test_restatements_collapse_to_the_most_recent_filing():
    """The same year appears in several 10-Ks; it is one observation, not three."""
    payload = facts_payload(
        [
            fact("2024-01-01", "2024-12-31", 4_183_800_000, "2025-02-13", accn="old"),
            fact("2024-01-01", "2024-12-31", 4_190_000_000, "2026-02-27", accn="new"),
        ]
    )

    rows = latest_annual_revenue(payload)

    assert len(rows) == 1
    assert rows[0]["accn"] == "new"
    assert rows[0]["val"] == 4_190_000_000


def test_revenue_tag_fallback_when_the_primary_tag_is_absent():
    payload = facts_payload([fact("2025-01-01", "2025-12-31", 100, "2026-01-01")], tag="Revenues")

    assert [row["val"] for row in latest_annual_revenue(payload)] == [100]


def test_missing_revenue_tags_yield_no_rows_rather_than_an_error():
    assert latest_annual_revenue({"facts": {"us-gaap": {}}}) == []


def test_entity_sic_is_verified_from_the_filing_not_assumed():
    """A CIK that is not a credit bureau must be reported, not silently accepted."""
    connector = connector_for(
        {
            "submissions": submissions(name="SOMNIGROUP INTERNATIONAL INC.", sic="2510"),
            "companyfacts": facts_payload([]),
        },
        incumbents=((1206264, "NotABureau"),),
    )

    entities, _evidence, errors = connector.retrieve()

    assert entities[0].is_credit_reporting_agency is False
    assert any("2510" in message for message in errors)


def test_market_evidence_is_classified_and_cannot_count_for_independence():
    connector = connector_for(
        {
            "submissions": submissions(),
            "companyfacts": facts_payload([fact("2025-01-01", "2025-12-31", 4_576_300_000, "2026-02-27")]),
        },
        incumbents=((1552033, "TransUnion"),),
    )

    _entities, evidence, errors = connector.retrieve(filings_per_entity=1)

    assert errors == []
    revenue = [item for item in evidence if item.fact_type == "ANNUAL_REVENUE"]
    assert revenue[0].evidence_class == COMPETITIVE_MARKET_CLASS
    assert revenue[0].value == 4_576_300_000
    for item in evidence:
        assert item.counts_toward_source_independence is False
        assert "Do not count market evidence toward independent source families." in (
            item.prohibited_inferences
        )


def test_market_evidence_is_structurally_not_study_evidence():
    """The proof gates cannot consume this type.

    The independent source family count is computed from `source_family` on study
    evidence. MarketEvidence has no such field, so incumbent self-disclosure cannot
    reach that count even if someone wired it through by mistake.
    """
    from core.models import VerifiedEvidence

    assert "source_family" in VerifiedEvidence.__dataclass_fields__
    assert "source_family" not in MarketEvidence.__dataclass_fields__
    assert not issubclass(MarketEvidence, VerifiedEvidence)


def test_market_evidence_does_not_change_the_evidence_ceiling():
    from connectors.cfpb import cfpb_source
    from core.normalization import normalise_cfpb_record
    from findings.engine import generate_findings
    from opportunity.assessment import assess_findings
    from proof_gates.evaluator import evaluate_proof_gates, make_verdict
    from studies.definitions import get_study
    from verification.classifier import verify_candidates

    study = get_study("GS-CF001-C")
    candidate = normalise_cfpb_record(
        {
            "complaint_id": "1",
            "product": "Credit reporting or other personal consumer reports",
            "issue": "Incorrect information on your report",
            "company": "A",
            "complaint_what_happened": "My dispute investigation failed to remove inaccurate information.",
            "_retrieval_url": "https://consumerfinance.gov/api",
            "_retrieved_at": "2026-07-25T00:00:00Z",
        },
        cfpb_source(),
        study,
    )
    verified = verify_candidates([candidate])
    findings = generate_findings(verified)
    opportunities = assess_findings(findings)
    gates = evaluate_proof_gates(verified, findings, opportunities)
    verdict = make_verdict("GS-CF001-C", gates, findings, opportunities, verified)

    # Market evidence exists in the run, and changes nothing about independence.
    connector = connector_for(
        {
            "submissions": submissions(),
            "companyfacts": facts_payload([fact("2025-01-01", "2025-12-31", 4_576_300_000, "2026-02-27")]),
        },
        incumbents=((1552033, "TransUnion"),),
    )
    _entities, market, _errors = connector.retrieve(filings_per_entity=1)

    assert market
    assert verdict.independent_source_family_count == 1
    assert verdict.evidence_ceiling == "CONTINUE RESEARCH"


def test_access_failure_is_surfaced_as_an_error():
    def failing(_url: str) -> dict[str, Any]:
        raise SECAccessError("SEC request failed: HTTP 503")

    connector = SECFilingsConnector(fetch_json=failing, incumbents=((1552033, "TransUnion"),))

    entities, evidence, errors = connector.retrieve()

    assert entities == []
    assert evidence == []
    assert errors and "503" in errors[0]


def test_filing_references_point_at_primary_annual_documents():
    connector = connector_for(
        {"submissions": submissions(), "companyfacts": facts_payload([])},
        incumbents=((1552033, "TransUnion"),),
    )

    _entities, evidence, _errors = connector.retrieve(filings_per_entity=5)

    references = [item for item in evidence if item.fact_type == "FILING_REFERENCE"]
    assert len(references) == 2  # the two 10-Ks, not the 10-Q
    assert all(item.filing_form == "10-K" for item in references)
    assert references[0].source_url.endswith("tru-20251231.htm")
