from connectors.cfpb import cfpb_source
from core.normalization import normalise_cfpb_record
from findings.engine import generate_findings
from studies.definitions import get_study
from verification.classifier import verify_candidates


def candidate(complaint_id: str, narrative: str):
    return normalise_cfpb_record(
        {
            "complaint_id": complaint_id,
            "product": "Credit reporting or other personal consumer reports",
            "issue": "Incorrect information on your report",
            "company": f"Company {complaint_id}",
            "complaint_what_happened": narrative,
            "_retrieval_url": "https://consumerfinance.gov/api",
            "_retrieved_at": "2026-07-14T00:00:00Z",
        },
        cfpb_source(),
        get_study("GS-CF001-C"),
    )


def test_finding_stays_blocked_with_single_verified_candidate():
    verified = verify_candidates([candidate("1", "I disputed incorrect information and the investigation did not correct it.")])

    findings = generate_findings(verified)

    assert findings[0].status == "needs_more_evidence"
    assert "minimum 3 verified evidence items" in findings[0].missing_evidence


def test_finding_can_identify_repeated_operational_mechanism_but_requires_corroboration():
    verified = verify_candidates(
        [
            candidate("1", "I disputed incorrect information and the investigation did not correct it."),
            candidate("2", "My dispute investigation failed to remove inaccurate information."),
            candidate("3", "The credit report dispute investigation did not correct wrong information."),
        ]
    )

    findings = generate_findings(verified)

    assert findings[0].status == "finding_supported_cfpb_only"
    assert "independent non-CFPB corroboration" in findings[0].missing_evidence

