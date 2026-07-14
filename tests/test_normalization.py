from connectors.cfpb import cfpb_source
from core.normalization import normalise_cfpb_record
from studies.definitions import get_study


def test_normalisation_maps_credit_reporting_record_to_evidence_candidate():
    source = cfpb_source()
    study = get_study("GS-CF001-C")
    raw = {
        "complaint_id": "123",
        "product": "Credit reporting or other personal consumer reports",
        "issue": "Incorrect information on your report",
        "company": "Example Bank",
        "complaint_what_happened": "The company did not correct information after my dispute.",
        "_retrieval_url": "https://consumerfinance.gov/api",
        "_retrieved_at": "2026-07-14T00:00:00Z",
    }

    candidate = normalise_cfpb_record(raw, source, study)

    assert candidate is not None
    assert candidate.study.study_id == "GS-CF001-C"
    assert candidate.source.role == "discovery"
    assert candidate.parsed_fields["complaint_id"] == "123"
    assert candidate.raw_record == raw
    assert "Normalised" in candidate.traceability[-1]


def test_normalisation_rejects_non_credit_reporting_record_for_current_scope():
    source = cfpb_source()
    study = get_study("GS-CF001-C")
    raw = {"complaint_id": "999", "product": "Mortgage", "_retrieval_url": "https://consumerfinance.gov/api"}

    assert normalise_cfpb_record(raw, source, study) is None

