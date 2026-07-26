"""Incumbent financial disclosures from SEC EDGAR.

This is the market and competition lane. It answers "who are the incumbents, at
what scale do they operate, and where is their primary disclosure", using audited
filings rather than vendor marketing.

Two deliberate constraints:

* Entities are verified against the SIC code the registrant files under, not a
  hardcoded assumption about who they are. A CIK that turns out to be a furniture
  company is reported as such rather than silently treated as a credit bureau.
* Nothing produced here can reach the proof gates. MarketEvidence is a distinct
  type from VerifiedEvidence, so incumbent self-disclosure can never corroborate
  consumer harm or lift the evidence ceiling.

EDGAR full-text search was evaluated and rejected as a source: a phrase search for
"Fair Credit Reporting Act" across 10-K filings returns thousands of unrelated
registrants, so it cannot support a deterministic admission rule.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Any, Callable

from core.ids import stable_id, utc_now
from core.storage import file_checksum  # noqa: F401  (kept for artifact parity)
from market.models import (
    DEFAULT_PERMITTED_USES,
    DEFAULT_PROHIBITED_INFERENCES,
    FACT_ANNUAL_REVENUE,
    FACT_FILING_REFERENCE,
    MarketEntity,
    MarketEvidence,
)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
ACCESS_TIMEOUT_SECONDS = 45

# SEC requires a descriptive User-Agent identifying the requester.
USER_AGENT = "GS-CF001 methodology proof (contact: research@example.com)"

# 7320 is "Services-Consumer Credit Reporting, Collection Agencies".
CREDIT_REPORTING_SIC = "7320"

# Registrants are candidates, not assertions: each is verified against its filed
# SIC code at retrieval time. Experian is deliberately absent - it is LSE-listed
# and does not file with the SEC, so no EDGAR evidence exists for it.
INCUMBENT_CIKS: tuple[tuple[int, str], ...] = (
    (1552033, "TransUnion"),
    (33185, "Equifax"),
)

# Revenue is tagged inconsistently across registrants, so candidates are tried in
# order rather than assuming a single concept exists.
REVENUE_TAGS: tuple[str, ...] = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
)

Fetcher = Callable[[str], dict[str, Any]]


class SECAccessError(RuntimeError):
    pass


def _default_fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=ACCESS_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as exc:
        raise SECAccessError(f"SEC request failed: HTTP {exc.code} for {url}") from exc
    except Exception as exc:  # transport, DNS, TLS, malformed JSON
        raise SECAccessError(f"SEC request failed: {exc}") from exc


MIN_ANNUAL_PERIOD_DAYS = 340
MAX_ANNUAL_PERIOD_DAYS = 400


def _period_days(entry: dict[str, Any]) -> int | None:
    start, end = entry.get("start"), entry.get("end")
    if not start or not end:
        return None
    try:
        return (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days
    except ValueError:
        return None


def is_annual_period(entry: dict[str, Any]) -> bool:
    """Distinguish a full year from the quarterly breakdowns a 10-K also carries.

    Filtering on form alone is not enough: a 10-K reports quarterly figures as well
    as the annual total, so a quarter's revenue would otherwise be recorded as a
    year's and understate the market by roughly a factor of four.
    """

    days = _period_days(entry)
    return days is not None and MIN_ANNUAL_PERIOD_DAYS <= days <= MAX_ANNUAL_PERIOD_DAYS


def latest_annual_revenue(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one annual revenue figure per period, preferring the latest filing.

    A 10-K restates prior years, so the same period appears in several filings.
    Grouping on the period end and keeping the most recently filed value avoids
    counting one year twice as though it were two observations.
    """

    us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    for tag in REVENUE_TAGS:
        entries = ((us_gaap.get(tag) or {}).get("units") or {}).get("USD")
        if not entries:
            continue
        by_period: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if entry.get("form") != "10-K" or not is_annual_period(entry):
                continue
            period_end = str(entry.get("end") or "")
            current = by_period.get(period_end)
            if current is None or str(entry.get("filed") or "") > str(current.get("filed") or ""):
                by_period[period_end] = entry
        if by_period:
            return [by_period[key] for key in sorted(by_period)]
    return []


class SECFilingsConnector:
    """Retrieve incumbent identity and audited scale from EDGAR."""

    method_name = "sec_edgar_submissions_and_xbrl"

    def __init__(
        self,
        fetch_json: Fetcher | None = None,
        *,
        incumbents: tuple[tuple[int, str], ...] = INCUMBENT_CIKS,
    ) -> None:
        self._fetch_json = fetch_json or _default_fetch_json
        self.incumbents = incumbents

    def entity(self, cik: int) -> MarketEntity:
        url = SUBMISSIONS_URL.format(cik=cik)
        payload = self._fetch_json(url)
        sic = str(payload.get("sic") or "")
        return MarketEntity(
            entity_id=stable_id("MENT", {"cik": cik}),
            name=str(payload.get("name") or ""),
            cik=f"{cik:010d}",
            sic=sic,
            sic_description=str(payload.get("sicDescription") or ""),
            source_url=url,
            # Verified from the registrant's own filing, not assumed from the list.
            is_credit_reporting_agency=sic == CREDIT_REPORTING_SIC,
        )

    def revenue_evidence(self, entity: MarketEntity) -> list[MarketEvidence]:
        url = COMPANY_FACTS_URL.format(cik=int(entity.cik))
        facts = self._fetch_json(url)
        retrieved_at = utc_now()
        records: list[MarketEvidence] = []
        for entry in latest_annual_revenue(facts):
            period_end = str(entry.get("end") or "")
            digest = stable_id(
                "MEV",
                {
                    "cik": entity.cik,
                    "fact": FACT_ANNUAL_REVENUE,
                    "end": period_end,
                    "val": entry.get("val"),
                    "accn": entry.get("accn"),
                },
            )
            records.append(
                MarketEvidence(
                    evidence_id=digest,
                    entity_id=entity.entity_id,
                    entity_name=entity.name,
                    cik=entity.cik,
                    fact_type=FACT_ANNUAL_REVENUE,
                    source_url=url,
                    retrieved_at=retrieved_at,
                    traceability_hash=digest,
                    period_end=period_end,
                    fiscal_year=str(entry.get("fy") or ""),
                    value=float(entry.get("val")) if entry.get("val") is not None else None,
                    currency="USD",
                    unit="USD",
                    filing_form=str(entry.get("form") or ""),
                    filing_date=str(entry.get("filed") or ""),
                    accession=str(entry.get("accn") or ""),
                    permitted_uses=list(DEFAULT_PERMITTED_USES),
                    prohibited_inferences=list(DEFAULT_PROHIBITED_INFERENCES),
                )
            )
        return records

    def filing_references(self, entity: MarketEntity, limit: int = 3) -> list[MarketEvidence]:
        """Point at primary annual filings without ingesting their full text."""

        url = SUBMISSIONS_URL.format(cik=int(entity.cik))
        payload = self._fetch_json(url)
        recent = (payload.get("filings") or {}).get("recent") or {}
        retrieved_at = utc_now()
        records: list[MarketEvidence] = []
        for form, filed, accession, document in zip(
            recent.get("form") or [],
            recent.get("filingDate") or [],
            recent.get("accessionNumber") or [],
            recent.get("primaryDocument") or [],
        ):
            if form != "10-K":
                continue
            document_url = FILING_INDEX_URL.format(
                cik=int(entity.cik),
                accession=str(accession).replace("-", ""),
                document=document,
            )
            digest = stable_id(
                "MEV",
                {"cik": entity.cik, "fact": FACT_FILING_REFERENCE, "accn": accession},
            )
            records.append(
                MarketEvidence(
                    evidence_id=digest,
                    entity_id=entity.entity_id,
                    entity_name=entity.name,
                    cik=entity.cik,
                    fact_type=FACT_FILING_REFERENCE,
                    source_url=document_url,
                    retrieved_at=retrieved_at,
                    traceability_hash=digest,
                    filing_form=form,
                    filing_date=str(filed),
                    accession=str(accession),
                    permitted_uses=list(DEFAULT_PERMITTED_USES),
                    prohibited_inferences=list(DEFAULT_PROHIBITED_INFERENCES),
                )
            )
            if len(records) >= limit:
                break
        return records

    def retrieve(self, *, filings_per_entity: int = 2) -> tuple[list[MarketEntity], list[MarketEvidence], list[str]]:
        entities: list[MarketEntity] = []
        evidence: list[MarketEvidence] = []
        errors: list[str] = []
        for cik, label in self.incumbents:
            try:
                entity = self.entity(cik)
            except SECAccessError as exc:
                errors.append(f"{label}: {exc}")
                continue
            entities.append(entity)
            if not entity.is_credit_reporting_agency:
                # Reported, not silently dropped: a mis-registered CIK is itself a
                # finding about the register rather than something to hide.
                errors.append(
                    f"{label} (CIK {entity.cik}) files under SIC {entity.sic} "
                    f"({entity.sic_description}), not {CREDIT_REPORTING_SIC}"
                )
            try:
                evidence.extend(self.revenue_evidence(entity))
                evidence.extend(self.filing_references(entity, limit=filings_per_entity))
            except SECAccessError as exc:
                errors.append(f"{label}: {exc}")
        return entities, evidence, errors
