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
    # Correction 6: mechanism name uses trigger-process-failure format
    assert verified.mechanism == "bureau_dispute_reinvestigation_failure"
    assert not hasattr(verified, "buyer_clarity")
    assert "Verification does not assess whether software should be built." in verified.reasoning_chain


def test_verification_marks_repeated_signal_only_after_multiple_candidates():
    items = [
        candidate("1", "I disputed incorrect information and the investigation did not correct it."),
        candidate("2", "My dispute investigation failed to remove inaccurate information."),
    ]

    verified = verify_candidates(items)

    assert all(item.repeated_signal for item in verified)


def test_verification_operational_but_not_software_addressable_still_verified_candidate():
    """Correction 5: software_addressable is no longer a gate on verified_candidate status.
    A record that is operational and traceable but NOT software-addressable must
    become verified_candidate so it reaches the findings engine and ODR.
    """
    # Text has OPERATIONAL_TERMS (incorrect, inaccurate, not mine, remove) but
    # NO SOFTWARE_ADDRESSABLE_TERMS (no dispute, investigation, document, proof,
    # communication, response, timeline, resolution).
    item = candidate(
        "99",
        "Incorrect derogatory tradeline on credit file. "
        "The account listed is not mine. I contacted the company and requested "
        "they remove this inaccurate entry. They refused without explanation.",
    )
    verified = verify_candidate(item)

    assert verified.operational is True
    assert verified.traceable is True
    assert verified.software_addressable is False
    # Must be verified_candidate despite software_addressable=False
    assert verified.verification_status == "verified_candidate"


def test_verification_non_operational_produces_rejected_candidate():
    # Use a raw record where BOTH the narrative AND the issue field are non-operational.
    # The default issue "Incorrect information on your report" contains "incorrect"
    # which is an OPERATIONAL_TERM, so override it here.
    non_op_raw = {
        "complaint_id": "100",
        "product": "Credit reporting or other personal consumer reports",
        "issue": "General credit score inquiry",
        "company": "Example Financial",
        "complaint_what_happened": "My credit score is too low and I cannot get a loan.",
        "_retrieval_url": "https://consumerfinance.gov/api",
        "_retrieved_at": "2026-07-14T00:00:00Z",
    }
    item = normalise_cfpb_record(non_op_raw, cfpb_source(), get_study("GS-CF001-C"))
    verified = verify_candidate(item)
    assert verified.operational is False
    assert verified.verification_status == "rejected_candidate"


def test_verification_software_addressability_is_classification_input_not_gate():
    """Confirm the gate logic comment is reflected in reasoning chain."""
    item = candidate(
        "101",
        "Incorrect account on my credit file, not mine, they refused to remove "
        "the inaccurate tradeline.",
    )
    verified = verify_candidate(item)
    assert any("classification input" in r or "not a verification gate" in r
               for r in verified.reasoning_chain)
