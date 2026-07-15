"""verification/rules.py — Deterministic term lists and mechanism detection rules.

OPERATIONAL_TERMS: words whose presence in a complaint text indicates the
consumer is describing a specific operational workflow failure (a process that
was triggered, executed incorrectly, or not executed at all). Generic credit
vocabulary ("information", "report") is intentionally excluded — those appear
in virtually every credit-related complaint and do not distinguish operational
failures from general dissatisfaction or educational inquiries.

SOFTWARE_ADDRESSABLE_TERMS: words whose presence indicates the failure mode
could plausibly be addressed by a software workflow component (dispute
management, document handling, case tracking, notification). This is checked
independently of operational status and is used only as a classification input,
not as a gate on verified_candidate status.

MECHANISM_RULES: priority-ordered list of (mechanism_name, detection_terms).
Mechanism names use the format:
    <actor>_<trigger-process>_<failure-mode>
e.g. "bureau_dispute_reinvestigation_failure" captures:
    actor=bureau, trigger-process=dispute_reinvestigation, failure=failure
The fallback mechanism "unclassified_credit_reporting_complaint" applies when
no named rule matches.
"""
from __future__ import annotations

# Terms that indicate an operational workflow failure is described.
# NOTE: "information" and "report" are deliberately EXCLUDED — they appear in
# nearly every credit-related complaint and do not distinguish workflow failures
# from general dissatisfaction, educational inquiries, or score confusion.
OPERATIONAL_TERMS = [
    "dispute",
    "reinvestigation",
    "investigation",
    "inaccurate",
    "incorrect",
    "not mine",
    "identity theft",
    "documentation",
    "proof",
    "remove",
    "correct",
]

# Terms that indicate the failure mode could be addressed by a software workflow
# component. Checked independently of OPERATIONAL_TERMS. Note: "dispute" and
# "investigation" appear here because dispute-management and case-tracking
# software directly addresses those failure modes.
SOFTWARE_ADDRESSABLE_TERMS = [
    "dispute",
    "investigation",
    "document",
    "proof",
    "communication",
    "response",
    "timeline",
    "resolution",
]

# Priority-ordered mechanism detection rules.
# Each entry: (mechanism_name, detection_terms_list).
# First matching rule wins. Mechanism names are trigger-process-failure labels.
MECHANISM_RULES = [
    (
        "bureau_dispute_reinvestigation_failure",
        ["dispute", "investigation", "reinvestigation"],
    ),
    (
        "furnisher_tradeline_data_error_persistence",
        ["incorrect", "inaccurate", "information", "report"],
    ),
    (
        "dispute_supporting_evidence_rejection",
        ["document", "proof", "evidence"],
    ),
    (
        "investigation_outcome_notification_failure",
        ["response", "communication", "status", "resolution"],
    ),
]

# Default mechanism applied when no rule matches.
DEFAULT_MECHANISM = "unclassified_credit_reporting_complaint"


def contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def detect_mechanism(text: str) -> str:
    lower = text.lower()
    for mechanism, terms in MECHANISM_RULES:
        if mechanism == "bureau_dispute_reinvestigation_failure":
            # Requires co-occurrence of "dispute" AND ("investigation" OR
            # "reinvestigation") to distinguish from generic mentions.
            if "dispute" in lower and ("investigation" in lower or "reinvestigation" in lower):
                return mechanism
            continue
        if any(term in lower for term in terms):
            return mechanism
    return DEFAULT_MECHANISM
