"""Deterministic evidence qualification and mechanism rules.

Generic credit-reporting vocabulary is not enough to establish an operational
failure. Narrative evidence must describe both a process and an alleged
failure. In the absence of a public narrative, only explicit CFPB taxonomy
phrases that name a failed process can establish a taxonomy-limited signal.
"""
from __future__ import annotations

import re


NARRATIVE_PROCESS_TERMS = [
    "contacted",
    "dispute",
    "disputed",
    "documentation",
    "documents",
    "evidence",
    "investigation",
    "proof",
    "reinvestigation",
    "remove",
    "requested",
    "response",
    "submitted",
]

NARRATIVE_FAILURE_TERMS = [
    "did not",
    "failed",
    "ignored",
    "no response",
    "not considered",
    "not corrected",
    "not fixed",
    "not removed",
    "rejected",
    "refused",
    "refuses",
    "remained",
    "still inaccurate",
    "unresolved",
]

# These phrases describe an operational step and an alleged failure in the
# official structured taxonomy. Broad labels such as "Incorrect information on
# your report" are deliberately absent.
EXPLICIT_OPERATIONAL_TAXONOMY_PHRASES = [
    "investigation into an existing problem",
    "investigation did not fix an error",
    "did not receive notice of the results",
    "was not notified of investigation status or results",
    "problem with fraud alerts or security freezes",
]

SOFTWARE_ADDRESSABLE_TERMS = [
    "communication",
    "dispute",
    "document",
    "evidence",
    "investigation",
    "notification",
    "proof",
    "response",
    "resolution",
    "status",
    "timeline",
]

# Backward-compatible export for callers that import the former name. It now
# represents process terms only and is never sufficient by itself.
OPERATIONAL_TERMS = NARRATIVE_PROCESS_TERMS

DEFAULT_MECHANISM = "unclassified_credit_reporting_complaint"


def matched_terms(text: str, terms: list[str]) -> list[str]:
    """Return exact case-insensitive term matches without substring leakage."""

    return [
        term
        for term in terms
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE)
    ]


def contains_any(text: str, terms: list[str]) -> bool:
    return bool(matched_terms(text, terms))


def operational_assessment(parsed_fields: dict[str, object]) -> tuple[bool, str, list[str]]:
    """Determine whether a record identifies an operational failure and why."""

    narrative = str(parsed_fields.get("narrative") or "").strip()
    if narrative:
        process_matches = matched_terms(narrative, NARRATIVE_PROCESS_TERMS)
        failure_matches = matched_terms(narrative, NARRATIVE_FAILURE_TERMS)
        if process_matches and failure_matches:
            return True, "consumer_narrative_process_and_failure", sorted(
                set(process_matches + failure_matches)
            )

    taxonomy = " ".join(
        str(parsed_fields.get(key) or "") for key in ("issue", "sub_issue")
    )
    taxonomy_matches = matched_terms(taxonomy, EXPLICIT_OPERATIONAL_TAXONOMY_PHRASES)
    if taxonomy_matches:
        return True, "explicit_cfpb_taxonomy_process_failure", taxonomy_matches

    return False, "operational_failure_not_established", []


def detect_mechanism(text: str) -> str:
    process = set(matched_terms(text, NARRATIVE_PROCESS_TERMS))
    failures = set(matched_terms(text, NARRATIVE_FAILURE_TERMS))
    lower = text.lower()

    if ({"dispute", "disputed"} & process) and ({"investigation", "reinvestigation"} & process):
        return "bureau_dispute_reinvestigation_failure"
    if ({"documentation", "documents", "evidence", "proof"} & process) and failures:
        return "dispute_supporting_evidence_rejection"
    if any(term in lower for term in ("notification", "status", "communication", "response")) and failures:
        return "investigation_outcome_notification_failure"
    if any(term in lower for term in ("incorrect", "inaccurate", "not mine", "tradeline")):
        if failures or any(term in lower for term in ("persist", "remain", "still")):
            return "furnisher_tradeline_data_error_persistence"
    return DEFAULT_MECHANISM
