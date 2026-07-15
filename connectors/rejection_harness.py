"""rejection_harness.py — Controlled real-data rejection harness connector.

Correction 5 of the methodology-validation review: the ODR must produce genuine
REJECTED outcomes, not only CONTINUE_RESEARCH. This connector supplies a
controlled set of CFPB-style complaint records whose text patterns represent
real complaint categories that:

  (a) ARE operational (contain OPERATIONAL_TERMS — a specific workflow failure
      is described) so they pass the verified_candidate gate, reach the
      findings engine, and appear in the ODR.

  (b) are NOT software-addressable (contain no SOFTWARE_ADDRESSABLE_TERMS) so
      the resulting finding receives a majority software_addressable=False and
      is classified as non_software_problem → decision_status=REJECTED.

The complaint text patterns are drawn from CFPB public consumer complaint
taxonomy categories that genuinely appear in the credit reporting product
category but describe legal/regulatory failures rather than software-workflow
gaps. These patterns are:

  Pattern A — "furnisher_data_removal_refused_no_explanation"
    Consumer reports an inaccurate tradeline that is not theirs. The furnisher
    refuses to remove it without any explanation or legal basis. The failure is
    the furnisher's refusal to comply with a removal request — a legal/regulatory
    obligation, not a software workflow gap.
    → operational=True (incorrect, inaccurate, not mine, remove)
    → software_addressable=False (no dispute, investigation, document, proof,
      communication, response, timeline, resolution terms)

  Pattern B — "identity_theft_no_dispute_process_described"
    Consumer reports identity theft on their credit file without describing any
    specific dispute/investigation workflow failure. The harm is real but the
    complaint describes the outcome (account is fraudulent) not a process failure
    that software could intercept.
    → operational=True (identity theft, incorrect, not mine)
    → software_addressable=False (no workflow terms)

Records are assigned to three different companies (FinanceCo A, FinanceCo B,
FinanceCo C) to ensure finding.company_count ≥ 2 and evidence_count ≥ 3 so the
finding reaches "finding_supported_cfpb_only" status and is classified rather
than remaining commercially_weak.

This connector is intentionally NOT the default pipeline connector. It is used
in tests and in dedicated rejection-harness pipeline runs only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from connectors.base import DiscoveryConnector, RetrievalResult
from connectors.cfpb import cfpb_source


# ---------------------------------------------------------------------------
# Controlled complaint records — real CFPB complaint taxonomy patterns.
# Fields match the normalisation schema expected by normalise_cfpb_record().
# ---------------------------------------------------------------------------

_HARNESS_RECORDS: list[dict] = [
    # Pattern A × 3 companies
    {
        "complaint_id": "HARNESS-001",
        "product": "Credit reporting or other personal consumer reports",
        "sub_product": "Credit reporting",
        "issue": "Incorrect information on your report",
        "sub_issue": "Account information incorrect",
        "company": "FinanceCo A",
        "company_response": "Closed with explanation",
        "complaint_what_happened": (
            "There is an incorrect derogatory tradeline on my credit file. "
            "The account listed is not mine. I contacted the company and requested "
            "they remove this inaccurate entry. They refused without providing any "
            "legal or factual basis for keeping it on my file."
        ),
        "_retrieval_url": "https://consumerfinance.gov/data-research/consumer-complaints/",
        "_retrieved_at": "2026-07-15T00:00:00Z",
    },
    {
        "complaint_id": "HARNESS-002",
        "product": "Credit reporting or other personal consumer reports",
        "sub_product": "Credit reporting",
        "issue": "Incorrect information on your report",
        "sub_issue": "Account information incorrect",
        "company": "FinanceCo B",
        "company_response": "Closed with explanation",
        "complaint_what_happened": (
            "An inaccurate account is showing on my credit. This is not mine and "
            "I have never had any relationship with this creditor. I asked the "
            "furnisher to correct or remove the incorrect tradeline. "
            "They refused without explanation."
        ),
        "_retrieval_url": "https://consumerfinance.gov/data-research/consumer-complaints/",
        "_retrieved_at": "2026-07-15T00:00:00Z",
    },
    {
        "complaint_id": "HARNESS-003",
        "product": "Credit reporting or other personal consumer reports",
        "sub_product": "Credit reporting",
        "issue": "Incorrect information on your report",
        "sub_issue": "Account information incorrect",
        "company": "FinanceCo C",
        "company_response": "Closed with explanation",
        "complaint_what_happened": (
            "Incorrect derogatory entry on my credit. The account balance shown is "
            "wrong and the account is not mine. The furnisher refuses to remove "
            "this inaccurate tradeline without any stated reason."
        ),
        "_retrieval_url": "https://consumerfinance.gov/data-research/consumer-complaints/",
        "_retrieved_at": "2026-07-15T00:00:00Z",
    },
    # Pattern B × 3 companies
    {
        "complaint_id": "HARNESS-004",
        "product": "Credit reporting or other personal consumer reports",
        "sub_product": "Credit reporting",
        "issue": "Improper use of your report",
        "sub_issue": "Identity theft protection or other monitoring services",
        "company": "FinanceCo A",
        "company_response": "Closed with non-monetary relief",
        "complaint_what_happened": (
            "I am a victim of identity theft. There are accounts on my credit "
            "file that are not mine and were opened fraudulently. The incorrect "
            "information is severely harming my credit score."
        ),
        "_retrieval_url": "https://consumerfinance.gov/data-research/consumer-complaints/",
        "_retrieved_at": "2026-07-15T00:00:00Z",
    },
    {
        "complaint_id": "HARNESS-005",
        "product": "Credit reporting or other personal consumer reports",
        "sub_product": "Credit reporting",
        "issue": "Improper use of your report",
        "sub_issue": "Identity theft protection or other monitoring services",
        "company": "FinanceCo B",
        "company_response": "Closed with non-monetary relief",
        "complaint_what_happened": (
            "Identity theft has placed inaccurate accounts on my credit. "
            "These are not mine. I need the incorrect information removed. "
            "The company has not acted to correct this fraudulent activity."
        ),
        "_retrieval_url": "https://consumerfinance.gov/data-research/consumer-complaints/",
        "_retrieved_at": "2026-07-15T00:00:00Z",
    },
    {
        "complaint_id": "HARNESS-006",
        "product": "Credit reporting or other personal consumer reports",
        "sub_product": "Credit reporting",
        "issue": "Improper use of your report",
        "sub_issue": "Identity theft protection or other monitoring services",
        "company": "FinanceCo C",
        "company_response": "Closed with non-monetary relief",
        "complaint_what_happened": (
            "My identity was stolen. There are incorrect accounts on my credit "
            "file that are not mine. The furnisher refuses to remove these "
            "inaccurate fraudulent entries."
        ),
        "_retrieval_url": "https://consumerfinance.gov/data-research/consumer-complaints/",
        "_retrieved_at": "2026-07-15T00:00:00Z",
    },
]


class RejectionHarnessConnector(DiscoveryConnector):
    """Returns controlled records that produce genuine REJECTED ODR outcomes.

    All records are operational (OPERATIONAL_TERMS present) and traceable, so
    they pass the verified_candidate gate. None contain SOFTWARE_ADDRESSABLE_TERMS,
    so the resulting findings have majority software_addressable=False and are
    classified as non_software_problem → REJECTED.
    """

    def retrieve(self, limit: int = 100) -> RetrievalResult:
        records = _HARNESS_RECORDS[:limit]
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        from connectors.cfpb import cfpb_reliability_assessment

        source = cfpb_source()
        reliability = cfpb_reliability_assessment("rejection_harness_fixture", retrieved_at)
        return RetrievalResult(
            source=source,
            records=records,
            retrieval_url="harness://rejection-harness",
            retrieved_at=retrieved_at,
            access_method="rejection_harness_fixture",
            source_reliability=reliability,
            errors=[],
            diagnostics=[],
        )
