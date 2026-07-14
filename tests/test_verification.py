from connectors.cfpb import cfpb_source
from core.normalization import normalise_cfpb_record
from studies.definitions import get_study
from verification.classifier import verify_candidate, verify_candidates


def raw_record(complaint_id: str, narrative: str):
    return {
        "complaint_id": complaint_id,
        "product": "Credit reporting or other personal consumer reports",
        "issue": "Incorrect information on your report",
        "company": "Example Financial",
        "complaint_what_happened": narrative,
        "_retrieval_url": "https://consumerfinance.gov/api",
        "_retrieved_at": "2026-07-14T00:00:00Z",
    }


def candidate(complaint_id: str, narrative: str):
    return normalise_cfpb_record(raw_record(complaint_id, narrative), cfpb_source(), get_study("GS-CF001-C"))


def test_verification_classifies_operational_traceable_candidate_without_opportunity_decision():
    item = candidate("1", "I disputed incorrect information on my credit report and the investigation did not correct it.")

    verified = verify_candidate(item)

    assert verified.operational is True
    assert verified.traceable is True
    assert verified.software_addressable is True
    assert verified.mechanism == "credit_report_dispute_investigation"
    assert not hasattr(verified, "buyer_clarity")
    assert "Verification does not assess whether software should be built." in verified.reasoning_chain


def test_verification_marks_repeated_signal_only_after_multiple_candidates():
    items = [
        candidate("1", "I disputed incorrect information and the investigation did not correct it."),
        candidate("2", "My dispute investigation failed to remove inaccurate information."),
    ]

    verified = verify_candidates(items)

    assert all(item.repeated_signal for item in verified)

