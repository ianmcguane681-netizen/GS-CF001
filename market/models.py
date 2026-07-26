"""Market and competition evidence, deliberately separate from study evidence.

Market evidence answers "who already solves this, how well, and at what cost".
Study evidence answers "does this operational problem actually occur". They are
different questions with different burdens of proof, and conflating them would let
a vendor's or incumbent's own account of the world corroborate consumer harm.

MarketEvidence is therefore a distinct type from VerifiedEvidence. It cannot be
passed into the proof gates, so it can never contribute to the independent source
family count that governs the evidence ceiling. That separation is structural
rather than a matter of discipline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# SV Engine vocabulary (sv_engine.domain.enums.EvidenceClass.COMPETITIVE_MARKET),
# so this lane hands off cleanly into C8_MARKET_COMPETITION and G7 competitive
# viability without a translation step.
COMPETITIVE_MARKET_CLASS = "E5_COMPETITIVE_MARKET"

FACT_ANNUAL_REVENUE = "ANNUAL_REVENUE"
FACT_FILING_REFERENCE = "FILING_REFERENCE"


@dataclass(frozen=True)
class MarketEntity:
    """An incumbent identified by its own regulatory filings, not by assumption."""

    entity_id: str
    name: str
    cik: str
    sic: str
    sic_description: str
    source_url: str
    is_credit_reporting_agency: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketEvidence:
    evidence_id: str
    entity_id: str
    entity_name: str
    cik: str
    fact_type: str
    source_url: str
    retrieved_at: str
    traceability_hash: str
    evidence_class: str = COMPETITIVE_MARKET_CLASS
    period_end: str = ""
    fiscal_year: str = ""
    value: float | None = None
    currency: str = ""
    unit: str = ""
    filing_form: str = ""
    filing_date: str = ""
    accession: str = ""
    # Recorded explicitly so the constraint is legible in the artifact itself and
    # not only in the code that produced it.
    counts_toward_source_independence: bool = False
    permitted_uses: list[str] = field(default_factory=list)
    prohibited_inferences: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_PERMITTED_USES = [
    "Size the market an incumbent operates in.",
    "Establish a competitive baseline for cost and scale.",
    "Identify which incumbents file as consumer credit reporting agencies.",
]

DEFAULT_PROHIBITED_INFERENCES = [
    "Do not treat an incumbent's own filing as proof that consumer harm occurred.",
    "Do not count market evidence toward independent source families.",
    "Do not infer a product opportunity from revenue scale alone.",
    "Do not infer incumbent solution quality from financial performance.",
]
