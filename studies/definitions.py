from __future__ import annotations

from core.models import Study


STUDIES: dict[str, Study] = {
    "GS-CF001-A": Study(
        "GS-CF001-A",
        "Mortgage Servicing",
        "Is there enough verified, repeated operational pain in U.S. mortgage servicing and complaint resolution to justify building a reusable workflow component?",
        implemented=False,
    ),
    "GS-CF001-B": Study(
        "GS-CF001-B",
        "Bank Account Servicing",
        "Is there enough verified, repeated operational pain in U.S. bank-account servicing and complaint resolution to justify building a reusable workflow component?",
        implemented=False,
    ),
    "GS-CF001-C": Study(
        "GS-CF001-C",
        "Credit Reporting Disputes",
        "Is there enough verified, repeated operational pain in U.S. credit-reporting dispute handling to justify building a reusable workflow component?",
        implemented=True,
    ),
    "GS-CF001-D": Study(
        "GS-CF001-D",
        "Debt Collection Communication",
        "Is there enough verified, repeated operational pain in U.S. debt-collection communication and dispute handling to justify building a reusable workflow component?",
        implemented=False,
    ),
    "GS-CF001-E": Study(
        "GS-CF001-E",
        "Consumer Loan Servicing",
        "Is there enough verified, repeated operational pain in U.S. consumer-loan servicing and complaint resolution to justify building a reusable workflow component?",
        implemented=False,
    ),
    "GS-CF001-F": Study(
        "GS-CF001-F",
        "Payment & Transaction Disputes",
        "Is there enough verified, repeated operational pain in U.S. payment and transaction dispute handling to justify building a reusable workflow component?",
        implemented=False,
    ),
}


def get_study(study_id: str) -> Study:
    try:
        return STUDIES[study_id]
    except KeyError as exc:
        raise ValueError(f"Unknown study_id: {study_id}") from exc

