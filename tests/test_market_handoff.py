"""The handoff must not overstate what a regulatory filing establishes.

Filings give incumbent identity and scale. They do not contain competitive
judgements or pricing, and machine retrieval is not human review. The SV Engine
refuses to pass its competitive gate on records whose comparative fields are
placeholders, so emitting honest placeholders is what keeps unassessed market data
from carrying a build decision.
"""
from __future__ import annotations

import json

from market.handoff import (
    NOT_ASSESSED,
    PENDING_REVIEW,
    PRICING_NOT_DISCLOSED,
    build_competitor_records,
    build_evidence_items,
    build_market_handoff,
    write_market_handoff,
)
from market.models import COMPETITIVE_MARKET_CLASS, MarketEntity, MarketEvidence

ENTITY = MarketEntity(
    entity_id="MENT-TU",
    name="TransUnion",
    cik="0001552033",
    sic="7320",
    sic_description="Services-Consumer Credit Reporting, Collection Agencies",
    source_url="https://data.sec.gov/submissions/CIK0001552033.json",
    is_credit_reporting_agency=True,
)


def revenue(value: float, period_end: str, entity: MarketEntity = ENTITY) -> MarketEvidence:
    return MarketEvidence(
        evidence_id=f"MEV-{period_end}",
        entity_id=entity.entity_id,
        entity_name=entity.name,
        cik=entity.cik,
        fact_type="ANNUAL_REVENUE",
        source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0001552033.json",
        retrieved_at="2026-07-26T00:00:00Z",
        traceability_hash=f"hash-{period_end}",
        period_end=period_end,
        value=value,
        currency="USD",
        filing_form="10-K",
        filing_date="2026-02-27",
        accession="0001-26-000001",
        prohibited_inferences=["Do not count market evidence toward independent source families."],
    )


def test_competitor_records_do_not_invent_judgements():
    records = build_competitor_records([ENTITY], [revenue(4_576_300_000, "2025-12-31")])

    record = records[0]
    assert record["name"] == "TransUnion"
    assert record["pricing"] == PRICING_NOT_DISCLOSED
    assert record["differentiation"] == NOT_ASSESSED
    assert record["switching_cost"] == NOT_ASSESSED
    assert record["strengths"] == [NOT_ASSESSED]
    assert record["weaknesses"] == [NOT_ASSESSED]


def test_observed_scale_uses_the_most_recent_period():
    records = build_competitor_records(
        [ENTITY], [revenue(4_183_800_000, "2024-12-31"), revenue(4_576_300_000, "2025-12-31")]
    )

    assert "4,576,300,000" in records[0]["observed_scale"]
    assert "2025-12-31" in records[0]["observed_scale"]


def test_entity_without_evidence_is_not_emitted_as_a_competitor():
    assert build_competitor_records([ENTITY], []) == []


def test_non_bureau_registrant_is_labelled_honestly():
    furniture = MarketEntity(
        entity_id="MENT-X",
        name="SOMNIGROUP INTERNATIONAL INC.",
        cik="0001206264",
        sic="2510",
        sic_description="Household Furniture",
        source_url="https://data.sec.gov/submissions/CIK0001206264.json",
        is_credit_reporting_agency=False,
    )

    records = build_competitor_records([furniture], [revenue(1.0, "2025-12-31", furniture)])

    assert "2510" in records[0]["alternative_type"]
    assert "Household Furniture" in records[0]["alternative_type"]


def test_evidence_items_are_unreviewed_and_classified_for_the_competitive_gate():
    items = build_evidence_items([revenue(4_576_300_000, "2025-12-31")])

    item = items[0]
    assert item["evidence_class"] == COMPETITIVE_MARKET_CLASS
    assert item["review_state"] == PENDING_REVIEW
    assert item["reviewed_by"] == ""
    assert item["confidence_contribution"] == 0.0
    assert item["linked_gates"] == ["G7_COMPETITIVE_VIABILITY"]
    assert item["linked_categories"] == ["C8_MARKET_COMPETITION"]
    assert item["content_hash"] == "hash-2025-12-31"


def test_handoff_records_its_own_limits():
    handoff = build_market_handoff([ENTITY], [revenue(1.0, "2025-12-31")], study_id="GS-CF001-C")

    assert handoff["counts_toward_source_independence"] is False
    assert handoff["lane"] == "market_and_competition"
    assert any("Pricing is not disclosed" in item for item in handoff["limitations"])
    assert any("never contributes to independent source family" in item for item in handoff["limitations"])


def test_handoff_is_written_deterministically(tmp_path):
    handoff = build_market_handoff(
        [ENTITY], [revenue(1.0, "2025-12-31")], study_id="GS-CF001-C", generated_at="2026-07-26T00:00:00Z"
    )
    first = write_market_handoff(tmp_path / "a" / "market.json", handoff).read_text(encoding="utf-8")
    second = write_market_handoff(tmp_path / "b" / "market.json", handoff).read_text(encoding="utf-8")

    assert first == second
    assert json.loads(first)["generated_at"] == "2026-07-26T00:00:00Z"
