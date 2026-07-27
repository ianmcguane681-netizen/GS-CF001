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
from connectors.docket_join import (
    DocketJoinAdapter,
    court_id_from_district,
    is_consumer_credit_suit,
    pacer_docket_number,
)
from connectors.fjc_idb import FJCIDBConnector, cites_fcra, fjc_idb_source
from core.normalization import normalise_idb_records
from studies.definitions import get_study
from verification.classifier import verify_candidates

CONSENT_ROW = {
    "resource_uri": "https://www.courtlistener.com/api/rest/v4/fjc-integrated-database/99/",
    "office": "1",
    "district": "https://www.courtlistener.com/api/rest/v4/courts/gand/",
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


def fake_fetch(payload, defendant_payload=None):
    """Serve one payload per stratum.

    Retrieval is stratified by which way the case went, so a stub that ignores the
    URL returns the same row twice and hides the stratification entirely.
    """

    def _fetch(url):
        if defendant_payload is not None and "judgment__in=2" in url:
            return defendant_payload, {"Content-Type": "application/json"}, "200"
        if defendant_payload is None and "judgment__in=2" in url:
            return {"results": []}, {"Content-Type": "application/json"}, "200"
        return payload, {"Content-Type": "application/json"}, "200"

    return _fetch


def join_returning(suit_nature: str, case_name: str = "Consumer v. Example Bureau"):
    """A docket join stub that resolves to exactly one docket."""

    payload = {
        "results": [
            {
                "caseName": case_name,
                "cause": "15:1681 Fair Credit Reporting Act",
                "suitNature": suit_nature,
                "docket_id": "12345",
            }
        ]
    }
    return DocketJoinAdapter(fetch_json=fake_fetch(payload))


def connector_for(row: dict, suit_nature: str = "480 Consumer Credit", **kwargs):
    return FJCIDBConnector(
        fetch_json=fake_fetch({"results": [row]}),
        token="t",
        join_adapter=join_returning(suit_nature, **kwargs),
    )


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


def test_retrieval_is_stratified_by_direction():
    """Defence decisions outnumber plaintiff ones roughly 366 to 67 in this data.

    An unstratified sample of any practical size is almost all defence wins, so the
    study never sees an adjudicated finding of occurrence. Retrieving only
    plaintiff wins would be the opposite error -- a source that can only confirm is
    not a test -- so both directions are requested deliberately.
    """
    connector = FJCIDBConnector(token="t")

    assert "judgment__in=1" in connector.build_url(4, judgment="1")
    assert "judgment__in=2" in connector.build_url(4, judgment="2")

    seen = []

    def recording_fetch(url):
        seen.append(url)
        return {"results": []}, {"Content-Type": "application/json"}, "200"

    FJCIDBConnector(fetch_json=recording_fetch, token="t").retrieve(limit=6)

    assert any("judgment__in=1&" in url or url.endswith("judgment__in=1") for url in seen)
    assert any("judgment__in=2" in url for url in seen)


def test_a_retrieved_consent_judgment_reaches_verification_as_adjudicated():
    result = connector_for(CONSENT_ROW).retrieve(limit=5)
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
    result = connector_for(dict(CONSENT_ROW, disposition=13, judgment=0)).retrieve(limit=5)
    verified = verify_candidates(
        normalise_idb_records(result.records, result.source, get_study("GS-CF001-C"))
    )

    assert verified[0].establishes_occurrence is False
    assert verified[0].contradicts_occurrence is False


# --- The docket join, and the case that made it mandatory ---------------------


def test_the_pacer_docket_number_is_rebuilt_from_coded_fields():
    """Verified against live data: utd 2:21-cv-00267 is FJC office 2, docket 2100267."""
    assert pacer_docket_number("2", "2100267") == "2:21-cv-00267"
    assert pacer_docket_number("1", "2004737") == "1:20-cv-04737"


def test_a_malformed_docket_number_produces_no_join_key():
    """Better no lookup than a lookup for the wrong case."""
    for office, docket in (("", "2100267"), ("2", "123"), ("2", ""), (None, None)):
        assert pacer_docket_number(office, docket) == ""


def test_the_court_id_is_read_from_the_district_resource_url():
    assert court_id_from_district("https://www.courtlistener.com/api/rest/v4/courts/utd/") == "utd"
    assert court_id_from_district("gand") == "gand"
    assert court_id_from_district(None) == ""


def test_consumer_credit_suit_nature_is_recognised_in_every_rendering():
    for value in ("480", "480 Consumer Credit", "Consumer Credit", "consumer credit"):
        assert is_consumer_credit_suit(value) is True
    for value in ("890 Other Statutory Actions", "190 Contract", "", None):
        assert is_consumer_credit_suit(value) is False


def test_an_enforcement_action_does_not_establish_this_studys_mechanism():
    """United States v. Vivint Smart Home, the record that made the join mandatory.

    A genuine FCRA violation, consent judgment against the respondent, and about
    improperly *using* consumer reports rather than failing to reinvestigate a
    dispute. It satisfies posture and direction and must still establish nothing.
    """
    vivint = dict(
        CONSENT_ROW,
        office="2",
        district="https://www.courtlistener.com/api/rest/v4/courts/utd/",
        docket_number="2100267",
        defendant="VIVINT SMART HOME",
        disposition=5,
        judgment=1,
    )
    result = connector_for(
        vivint,
        suit_nature="890 Other Statutory Actions",
        case_name="United States v. Vivint Smart Home",
    ).retrieve(limit=5)
    verified = verify_candidates(
        normalise_idb_records(result.records, result.source, get_study("GS-CF001-C"))
    )

    assert verified[0].adjudication_posture == CONSENT_ORDER
    assert verified[0].adjudication_direction == AGAINST_RESPONDENT
    assert verified[0].establishes_occurrence is False


def test_an_unjoined_record_establishes_nothing():
    """Unknown subject matter is not permission. A failed join must not read the
    same as a confirmed consumer credit case."""
    result = FJCIDBConnector(
        fetch_json=fake_fetch({"results": [CONSENT_ROW]}),
        token="t",
        join_adapter=DocketJoinAdapter(fetch_json=fake_fetch({"results": []})),
    ).retrieve(limit=5)
    verified = verify_candidates(
        normalise_idb_records(result.records, result.source, get_study("GS-CF001-C"))
    )

    assert verified[0].establishes_occurrence is False
    assert result.records[0]["join_verified"] is False


def test_an_ambiguous_join_is_not_a_join():
    two = {"results": [{"caseName": "A", "suitNature": "480"}, {"caseName": "B", "suitNature": "480"}]}
    outcome = DocketJoinAdapter(fetch_json=fake_fetch(two)).lookup("gand", "1:21-cv-00123")

    assert outcome["join_verified"] is False
    assert "ambiguous" in outcome["join_note"]
    assert outcome["on_study_suit_nature"] is False
