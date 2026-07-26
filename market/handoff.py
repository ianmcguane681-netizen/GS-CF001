"""Emit market evidence in the SV Engine's input shape.

The market lane and the SV Engine live in different repositories, so the seam is a
written artifact rather than an import - the same pattern as the Golden Study
verified-problem handoff.

Two things this deliberately does not do:

* It does not invent competitive judgements. Strengths, weaknesses, switching cost
  and differentiation are assessments, not facts disclosed in a filing, so they are
  emitted as explicitly unassessed rather than guessed. Pricing is recorded as not
  disclosed, because SEC filings do not contain it.
* It does not mark evidence as reviewed. Machine retrieval is not human review, so
  every item is emitted PENDING_REVIEW. The SV Engine only counts approved evidence
  toward a gate, so filings alone cannot make G7 pass - they make it assessable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.ids import utc_now
from market.models import (
    COMPETITIVE_MARKET_CLASS,
    FACT_ANNUAL_REVENUE,
    MarketEntity,
    MarketEvidence,
)

HANDOFF_SCHEMA_VERSION = "1.0.0"
MARKET_COMPETITION_CATEGORY = "C8_MARKET_COMPETITION"
COMPETITIVE_VIABILITY_GATE = "G7_COMPETITIVE_VIABILITY"

# sv_engine.domain.enums.ReviewState.PENDING_REVIEW
PENDING_REVIEW = "PENDING_REVIEW"

NOT_ASSESSED = "not assessed from regulatory filings"
PRICING_NOT_DISCLOSED = "not disclosed in SEC filings"

ALTERNATIVE_TYPE = "incumbent consumer credit reporting agency"


def _evidence_for_entity(
    entity: MarketEntity, evidence: list[MarketEvidence]
) -> list[MarketEvidence]:
    return [item for item in evidence if item.entity_id == entity.entity_id]


def _latest_revenue(items: list[MarketEvidence]) -> MarketEvidence | None:
    revenue = [item for item in items if item.fact_type == FACT_ANNUAL_REVENUE and item.value]
    if not revenue:
        return None
    return sorted(revenue, key=lambda item: item.period_end)[-1]


def build_competitor_records(
    entities: list[MarketEntity], evidence: list[MarketEvidence]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entity in entities:
        items = _evidence_for_entity(entity, evidence)
        if not items:
            continue
        latest = _latest_revenue(items)
        scale = (
            f"Audited annual revenue {latest.currency} {latest.value:,.0f} "
            f"for the period ending {latest.period_end}."
            if latest
            else "No audited annual revenue retrieved."
        )
        records.append(
            {
                "competitor_id": entity.entity_id,
                "name": entity.name,
                "alternative_type": ALTERNATIVE_TYPE
                if entity.is_credit_reporting_agency
                else f"registrant filing under SIC {entity.sic} ({entity.sic_description})",
                # Judgements, not disclosures. Left explicitly unassessed so the SV
                # Engine records them as gaps rather than treating a guess as input.
                "strengths": [NOT_ASSESSED],
                "weaknesses": [NOT_ASSESSED],
                "pricing": PRICING_NOT_DISCLOSED,
                "switching_cost": NOT_ASSESSED,
                "differentiation": NOT_ASSESSED,
                "evidence_ids": [item.evidence_id for item in items],
                "observed_scale": scale,
            }
        )
    return records


def build_evidence_items(evidence: list[MarketEvidence]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in evidence:
        if item.fact_type == FACT_ANNUAL_REVENUE and item.value is not None:
            title = f"{item.entity_name} audited annual revenue, period ending {item.period_end}"
            claim = f"{item.entity_name} operates at {item.currency} {item.value:,.0f} annual revenue."
        else:
            title = f"{item.entity_name} {item.filing_form} filed {item.filing_date}"
            claim = f"Primary annual disclosure for {item.entity_name}."
        items.append(
            {
                "evidence_id": item.evidence_id,
                "title": title,
                "description": claim,
                "relevant_claim": claim,
                "evidence_class": COMPETITIVE_MARKET_CLASS,
                "source_type": "sec_regulatory_filing",
                "source_organisation": item.entity_name,
                "source_locator": item.source_url,
                "content_hash": item.traceability_hash,
                "date_observed_or_published": item.filing_date,
                "retrieval_timestamp": item.retrieved_at,
                "provenance": (
                    f"Retrieved from SEC EDGAR for CIK {item.cik}"
                    + (f", accession {item.accession}" if item.accession else "")
                ),
                "linked_categories": [MARKET_COMPETITION_CATEGORY],
                "linked_gates": [COMPETITIVE_VIABILITY_GATE],
                # Machine retrieval is not human review.
                "review_state": PENDING_REVIEW,
                "reviewed_by": "",
                "reviewed_at": "",
                "confidence_contribution": 0.0,
                "contradiction_flag": False,
                "assumptions": [],
                "limitations": list(item.prohibited_inferences),
            }
        )
    return items


def build_market_handoff(
    entities: list[MarketEntity],
    evidence: list[MarketEvidence],
    *,
    study_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "study_id": study_id,
        "generated_at": generated_at or utc_now(),
        "lane": "market_and_competition",
        "counts_toward_source_independence": False,
        "competitors": build_competitor_records(entities, evidence),
        "evidence_items": build_evidence_items(evidence),
        "limitations": [
            "Regulatory filings establish incumbent identity and scale only.",
            "Competitive judgements are not assessed from filings.",
            "Pricing is not disclosed in SEC filings.",
            "Evidence is unreviewed; human review is required before it supports a gate.",
            "Market evidence never contributes to independent source family count.",
        ],
    }


def write_market_handoff(path: str | Path, handoff: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(handoff, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
