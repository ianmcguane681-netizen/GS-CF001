from __future__ import annotations

OPERATIONAL_TERMS = [
    "dispute",
    "investigation",
    "reinvestigation",
    "incorrect",
    "inaccurate",
    "not mine",
    "remove",
    "correct",
    "report",
    "information",
    "documentation",
    "proof",
    "identity theft",
]

SOFTWARE_ADDRESSABLE_TERMS = [
    "dispute",
    "investigation",
    "document",
    "proof",
    "communication",
    "response",
    "timeline",
    "case",
    "status",
    "resolution",
]

MECHANISM_RULES = [
    ("credit_report_dispute_investigation", ["dispute", "investigation", "reinvestigation"]),
    ("incorrect_credit_report_information", ["incorrect", "inaccurate", "information", "report"]),
    ("credit_report_documentation_handling", ["document", "proof", "evidence"]),
    ("credit_report_resolution_communication", ["response", "communication", "status", "resolution"]),
]


def contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def detect_mechanism(text: str) -> str:
    lower = text.lower()
    for mechanism, terms in MECHANISM_RULES:
        if mechanism == "credit_report_dispute_investigation":
            if "dispute" in lower and ("investigation" in lower or "reinvestigation" in lower):
                return mechanism
            continue
        if any(term in lower for term in terms):
            return mechanism
    return "credit_reporting_dispute_handling"
