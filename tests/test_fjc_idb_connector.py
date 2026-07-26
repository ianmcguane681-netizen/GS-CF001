"""The adjudicated source: FJC Integrated Database case outcomes.

Adopted after three other candidates were probed and rejected (see
`analysis/source_evaluation_adjudicated_findings.md`). It is the only source found
that records *who won* in coded form, which is what lets posture and direction be
read rather than guessed.

Most of these tests are about what the connector refuses. The failure mode worth
guarding is a source that looks like proof: 7,683 of the 17,204 FCRA cases in this
database ended in settlement, and admitting those would hand the study thousands of
false proofs in one retrieval.
"""
from __future__ import annotations

from core.adjudication import (
    ADJUDICATED,
    AGAINST_RESPONDENT,
    ALLEGED,
    CONSENT_ORDER,
    FOR_RESPONDENT,
    SETTLEMENT,
    SUMMARY_JUDGMENT,
    TRIAL_JUDGMENT,
    UNDETERMINED_DIRECTION,
    UNDETERMINED_POSTURE,
    classify_fjc_disposition,
    contradicts_occurrence,
    establishes_occurrence,
)
from connectors.courtlistener import courtlistener_source
from connectors.fjc_idb import FJCIDBConnector, cites_fcra, fjc_idb_source
from core.normalization import normalise_idb_records
from studies.definitions import get_study
from verification.classifier import verify_candidates

CONSENT_ROW = {
    "resource_uri": "https://www.courtlistener.com/api/rest/v4/fjc-integrated-database/99/",
    "docket_number": "2100123",
    "plaintiff": "CONSUMER",
    "defendant": "EXAMPLE BUREAU INC",
    "title": "15",
    "section": "1681",
    "nature_of_suit": 480,
    "date_filed": "2020-01-02",
    "date_terminated": "2021-03-04",
    "disposition": 5,
    "judgment": 1,
}


def fake_fetch(payload):
    def _fetch(url):
        return payload, {"Content-Type": "application/json"}, "200"

    return _fetch


# --- Admission is statutory, not nominal --------------------------------------


def test_admission_requires_the_coded_fcra_statute():
    assert cites_fcra("15", "1681") is True
    assert cites_fcra("15", "1681a") is True
    assert cites_fcra("15", "1692") is False  # Fair Debt Collection Practices Act
    assert cites_fcra("28", "1681") is False  # right section, wrong title
    assert cites_fcra(None, None) is False


def test_a_non_fcra_case_is_not_admitted_even_from_the_right_endpoint():
    payload = {"results": [dict(CONSENT_ROW, section="1692")]}
    result = FJCIDBConnector(fetch_json=fake_fetch(payload), token="t").retrieve(limit=5)

    assert result.records == []


# --- The classifier's exclusions ----------------------------------------------


def test_a_settlement_is_not_an_admission():
    """The largest group in the dataset, and the most dangerous to admit."""
    posture, direction = classify_fjc_disposition(13, 0)

    assert posture == SETTLEMENT
    assert establishes_occurrence(posture, direction) is False


def test_a_default_judgment_is_not_a_finding():
    """Nobody weighed the allegation; the defendant simply never appeared."""
    posture, direction = classify_fjc_disposition(4, 1)

    assert posture == UNDETERMINED_POSTURE
    assert establishes_occurrence(posture, direction) is False


def test_a_consent_judgment_for_the_plaintiff_establishes_occurrence():
    posture, direction = classify_fjc_disposition(5, 1)

    assert (posture, direction) == (CONSENT_ORDER, AGAINST_RESPONDENT)
    assert establishes_occurrence(posture, direction) is True


def test_trial_outcomes_are_readable_in_both_directions():
    for code in (7, 8, 9):  # jury verdict, directed verdict, court trial
        assert classify_fjc_disposition(code, 1) == (TRIAL_JUDGMENT, AGAINST_RESPONDENT)
        assert classify_fjc_disposition(code, 2) == (TRIAL_JUDGMENT, FOR_RESPONDENT)
    assert contradicts_occurrence(*classify_fjc_disposition(7, 2)) is True


def test_pre_trial_judgment_is_asymmetric_because_the_code_is_ambiguous():
    """One code covers Rule 12(b)(6) and Rule 56, and they mean opposite things.

    A plaintiff cannot win a motion to dismiss, so a plaintiff win here is summary
    judgment on the merits. A defendant win could be either, and the database does
    not say which, so it establishes nothing -- discarding the largest defence-side
    group rather than overstating it.
    """
    assert classify_fjc_disposition(6, 1) == (SUMMARY_JUDGMENT, AGAINST_RESPONDENT)
    assert classify_fjc_disposition(6, 2) == (SUMMARY_JUDGMENT, UNDETERMINED_DIRECTION)
    assert contradicts_occurrence(*classify_fjc_disposition(6, 2)) is False


def test_a_mixed_or_unknown_judgment_establishes_nothing():
    for judgment in (3, 4, 0, None, ""):
        assert establishes_occurrence(*classify_fjc_disposition(7, judgment)) is False


def test_missing_codes_do_not_crash_and_establish_nothing():
    """Recent cases carry null codes until a later dataset load."""
    assert classify_fjc_disposition(None, None) == (
        UNDETERMINED_POSTURE,
        UNDETERMINED_DIRECTION,
    )


# --- Standing, and the line it must not cross ---------------------------------


def test_the_source_declares_adjudicated_standing():
    assert fjc_idb_source().evidentiary_standing == ADJUDICATED
    assert courtlistener_source().evidentiary_standing == ALLEGED


def test_the_idb_shares_the_court_records_family_on_purpose():
    """These are the same courts RECAP covers. Counting them twice would fake
    independence out of one dispute."""
    assert fjc_idb_source().source_family == courtlistener_source().source_family


def test_a_missing_token_is_a_diagnostic_not_a_silent_empty_result():
    """Otherwise an unconfigured environment looks identical to no adjudications."""
    result = FJCIDBConnector(token="").retrieve(limit=5)

    assert result.records == []
    assert result.errors and "COURTLISTENER_API_TOKEN" in result.errors[0]
    assert result.diagnostics and result.diagnostics[0].response_status == "no_credential"


def test_the_token_never_appears_in_a_diagnostic():
    result = FJCIDBConnector(fetch_json=fake_fetch({"results": []}), token="secret-token").retrieve(
        limit=1
    )

    assert "secret-token" not in str([item.to_dict() for item in result.diagnostics or []])


def test_only_decided_cases_are_requested():
    """Settled and dismissed cases cannot establish or contradict anything."""
    url = FJCIDBConnector(token="t").build_url(limit=10)

    assert "disposition__in=5%2C6%2C7%2C8%2C9" in url
    assert "judgment__in=1%2C2" in url
    assert "title=15" in url


def test_a_retrieved_consent_judgment_reaches_verification_as_adjudicated():
    payload = {"results": [CONSENT_ROW]}
    result = FJCIDBConnector(fetch_json=fake_fetch(payload), token="t").retrieve(limit=5)
    candidates = normalise_idb_records(result.records, result.source, get_study("GS-CF001-C"))
    verified = verify_candidates(candidates)

    assert len(verified) == 1
    item = verified[0]
    assert item.evidentiary_standing == ADJUDICATED
    assert item.adjudication_posture == CONSENT_ORDER
    assert item.establishes_occurrence is True
    assert item.company_name == "EXAMPLE BUREAU INC"


def test_a_settled_case_reaching_verification_still_establishes_nothing():
    """Defence in depth: the query filters these out, and the classifier would too."""
    payload = {"results": [dict(CONSENT_ROW, disposition=13, judgment=0)]}
    result = FJCIDBConnector(fetch_json=fake_fetch(payload), token="t").retrieve(limit=5)
    verified = verify_candidates(
        normalise_idb_records(result.records, result.source, get_study("GS-CF001-C"))
    )

    assert verified[0].establishes_occurrence is False
    assert verified[0].contradicts_occurrence is False
