"""Occurrence is established by a decision, never by repetition.

The review board's open SEV-2 (FND3-SR-001) found that two independent forums
alleging the same mechanism is still two allegations, and accepted a remediation:
require a judgment, consent order or examination finding before asserting the
failure occurred. Nothing enforced that. The requirement existed only as prose in
a source reliability assessment, and PG-09 and PG-13 were pinned to FAIL, which
enforces nothing -- a pinned constant cannot tell a study that lacks adjudicated
evidence from one that has it.

These tests fix the rule in place, and most of them are about what must *not*
count. The failure mode this guards against is laundering an allegation into a
finding by attaching a judge's name to it.
"""
from __future__ import annotations

from dataclasses import replace

from core.adjudication import (
    ADJUDICATED,
    AGAINST_RESPONDENT,
    ALLEGED,
    APPELLATE_REVIEW,
    CONSENT_ORDER,
    FOR_RESPONDENT,
    MOTION_TO_DISMISS,
    SUMMARY_JUDGMENT,
    TRIAL_JUDGMENT,
    UNDETERMINED_DIRECTION,
    UNDETERMINED_POSTURE,
    AdjudicatedFinding,
    classify_disposition,
    contradicts_occurrence,
    establishes_occurrence,
)
from core.models import Source, VerifiedEvidence
from proof_gates.evaluator import evaluate_proof_gates, make_verdict


def evidence(
    evidence_id: str,
    *,
    family: str,
    mechanism: str = "reinvestigation_failure",
    standing: str = ALLEGED,
    posture: str = "",
    direction: str = "",
    court: str = "",
) -> VerifiedEvidence:
    return VerifiedEvidence(
        evidence_id=evidence_id,
        candidate_id=f"CAND-{evidence_id}",
        study_id="GS-CF001-C",
        source_record_id=evidence_id,
        company_name="Example Bureau",
        verification_status="verified_candidate",
        operational=True,
        traceable=True,
        software_addressable=True,
        repeated_signal=True,
        independently_corrobored=False,
        mechanism=mechanism,
        reasoning_chain=[],
        supporting_candidate_ids=[],
        missing_evidence=[],
        source_family=family,
        evidentiary_standing=standing,
        adjudication_posture=posture,
        adjudication_direction=direction,
        court=court,
        establishes_occurrence=establishes_occurrence(posture, direction),
        contradicts_occurrence=contradicts_occurrence(posture, direction),
    )


def gate(gates, gate_id):
    return next(item for item in gates if item.gate_id == gate_id)


# --- The classifier refuses to guess -----------------------------------------


def test_an_unknown_disposition_is_undetermined_not_a_guess():
    """The unauthenticated search API returns an empty disposition for every row."""
    assert classify_disposition("") == (UNDETERMINED_POSTURE, UNDETERMINED_DIRECTION)
    assert classify_disposition("partially granted in relevant part") == (
        UNDETERMINED_POSTURE,
        UNDETERMINED_DIRECTION,
    )


def test_the_vocabulary_is_exact_match_but_tolerates_spacing_and_case():
    assert classify_disposition("  Judgment  FOR Plaintiff ") == (
        TRIAL_JUDGMENT,
        AGAINST_RESPONDENT,
    )


def test_denying_a_motion_to_dismiss_establishes_nothing():
    """The trap. To decide the motion the court assumes the allegations are true.

    Admitting this as proof of occurrence would reproduce the board's finding with
    a judge's name attached, which is harder to spot rather than fixed.
    """
    posture, direction = classify_disposition("motion to dismiss denied")

    assert posture == MOTION_TO_DISMISS
    assert establishes_occurrence(posture, direction) is False
    assert contradicts_occurrence(posture, direction) is False


def test_denying_summary_judgment_establishes_nothing():
    """It establishes the opposite of a settled fact: the facts are disputed."""
    posture, direction = classify_disposition("summary judgment denied")

    assert posture == SUMMARY_JUDGMENT
    assert establishes_occurrence(posture, direction) is False


def test_an_appellate_disposition_alone_carries_no_direction():
    """'Affirmed' is relative to a judgment below that is not recorded here.

    Affirming a defence win and affirming a plaintiff win are opposite outcomes
    behind the same word.
    """
    for word in ("affirmed", "reversed", "vacated", "remanded"):
        posture, direction = classify_disposition(word)
        assert posture == APPELLATE_REVIEW
        assert direction == UNDETERMINED_DIRECTION
        assert establishes_occurrence(posture, direction) is False


def test_a_settlement_is_not_an_admission():
    posture, direction = classify_disposition("settled")
    assert establishes_occurrence(posture, direction) is False


def test_a_merits_disposition_against_the_respondent_establishes_occurrence():
    for value in ("judgment for plaintiff", "summary judgment for plaintiff", "consent order entered"):
        posture, direction = classify_disposition(value)
        assert establishes_occurrence(posture, direction) is True


def test_a_merits_disposition_for_the_respondent_is_counter_evidence():
    posture, direction = classify_disposition("summary judgment for defendant")

    assert direction == FOR_RESPONDENT
    assert contradicts_occurrence(posture, direction) is True
    assert establishes_occurrence(posture, direction) is False


def test_occurrence_cannot_be_asserted_by_setting_a_flag():
    """It is derived from posture and direction, so a caller cannot declare it."""
    finding = AdjudicatedFinding(
        adjudication_id="ADJ-1",
        forum="N.D. Cal.",
        citation="No. 3:24-cv-00001",
        respondent="Example Bureau",
        mechanism="reinvestigation_failure",
        posture=MOTION_TO_DISMISS,
        direction=AGAINST_RESPONDENT,
    )

    assert finding.establishes_occurrence is False
    assert "assumed the allegations were true" in finding.to_dict()["occurrence_reasoning"]
    assert "establishes_occurrence" not in AdjudicatedFinding.__dataclass_fields__


# --- The gates now compute rather than assert --------------------------------


def test_two_alleging_families_do_not_pass_corroboration():
    """The board's finding, as a test. This is the current state of the study."""
    items = [
        evidence("E1", family="CFPB complaints"),
        evidence("E2", family="Federal court records"),
    ]

    gates = evaluate_proof_gates(items, [], [])

    assert gate(gates, "PG-15").status == "PASS"  # independence is satisfied
    assert gate(gates, "PG-09").status == "FAIL"  # corroboration is not
    assert gate(gates, "PG-09").constrains_max_verdict is True


def corroborating(name: str, court: str):
    return evidence(
        name,
        family="Federal court records",
        standing=ADJUDICATED,
        posture=CONSENT_ORDER,
        direction=AGAINST_RESPONDENT,
        court=court,
    )


def test_one_corroborating_district_is_not_enough_for_pg09():
    """The threshold comes from the remediation plan accepted in review 0007.

    The sceptical seat refused to let a single California judgment carry a
    market-wide operational claim: "one case, in one district, against one
    collection agency". Three distinct districts are required, and until then the
    gate reports how far short it is rather than simply failing.
    """
    items = [evidence("E1", family="CFPB complaints"), corroborating("E2", "caed")]

    result = gate(evaluate_proof_gates(items, [], []), "PG-09")

    assert result.status == "WEAK"
    assert result.constrains_max_verdict is True
    assert "1 district(s); 3 required" in result.observed_value


def test_three_distinct_districts_pass_pg09():
    items = [
        evidence("E1", family="CFPB complaints"),
        corroborating("E2", "caed"),
        corroborating("E3", "gand"),
        corroborating("E4", "ilnd"),
    ]

    result = gate(evaluate_proof_gates(items, [], []), "PG-09")

    assert result.status == "PASS"
    assert result.constrains_max_verdict is False


def test_three_records_from_one_district_are_still_one_district():
    """Volume in a single court is not geographic spread."""
    items = [
        evidence("E1", family="CFPB complaints"),
        corroborating("E2", "caed"),
        corroborating("E3", "caed"),
        corroborating("E4", "caed"),
    ]

    assert gate(evaluate_proof_gates(items, [], []), "PG-09").status == "WEAK"


def test_records_without_a_court_do_not_count_as_districts():
    """An absent value is never a distinct value -- otherwise three unknowns would
    satisfy a three-district threshold, which is the placeholder failure again."""
    items = [
        evidence("E1", family="CFPB complaints"),
        corroborating("E2", ""),
        corroborating("E3", ""),
        corroborating("E4", ""),
    ]

    result = gate(evaluate_proof_gates(items, [], []), "PG-09")

    assert result.status == "WEAK"
    assert "0 district(s)" in result.observed_value


def test_an_adjudication_corroborated_only_by_its_own_family_does_not_pass():
    """One forum talking to itself is not independent corroboration."""
    items = [
        evidence("E1", family="Federal court records"),
        evidence(
            "E2",
            family="Federal court records",
            standing=ADJUDICATED,
            posture=TRIAL_JUDGMENT,
            direction=AGAINST_RESPONDENT,
        ),
    ]

    gates = evaluate_proof_gates(items, [], [])

    assert gate(gates, "PG-09").status == "WEAK"


def test_an_adjudication_on_a_different_mechanism_does_not_corroborate():
    items = [
        evidence("E1", family="CFPB complaints", mechanism="reinvestigation_failure"),
        evidence(
            "E2",
            family="Federal court records",
            mechanism="mixed_file_failure",
            standing=ADJUDICATED,
            posture=TRIAL_JUDGMENT,
            direction=AGAINST_RESPONDENT,
        ),
    ]

    gates = evaluate_proof_gates(items, [], [])

    assert gate(gates, "PG-09").status == "WEAK"


def test_counter_evidence_needs_a_disposition_that_went_the_other_way():
    """Claimant-submitted sources cannot produce counter-evidence at all."""
    alleged_only = [
        evidence("E1", family="CFPB complaints"),
        evidence("E2", family="Federal court records"),
    ]
    assert gate(evaluate_proof_gates(alleged_only, [], []), "PG-13").status == "FAIL"

    with_defence_win = alleged_only + [
        evidence(
            "E3",
            family="Federal court records",
            standing=ADJUDICATED,
            posture=SUMMARY_JUDGMENT,
            direction=FOR_RESPONDENT,
        )
    ]
    assert gate(evaluate_proof_gates(with_defence_win, [], []), "PG-13").status == "PASS"


def test_an_unclassified_mechanism_does_not_corroborate_itself():
    """The bug the first live three-source run exposed.

    IDB rows are outcome codes with no narrative, so they classify to the default
    mechanism. So did the complaints in that run. PG-09 reported PASS because the
    two "matched" -- on both being unclassified. Two records agreeing that neither
    has been classified is not corroboration.
    """
    unclassified = "unclassified_credit_reporting_complaint"
    items = [
        evidence("E1", family="CFPB complaints", mechanism=unclassified),
        evidence(
            "E2",
            family="Federal court records",
            mechanism=unclassified,
            standing=ADJUDICATED,
            posture=CONSENT_ORDER,
            direction=AGAINST_RESPONDENT,
        ),
    ]

    gates = evaluate_proof_gates(items, [], [])

    assert gate(gates, "PG-09").status == "WEAK"
    assert gate(gates, "PG-09").constrains_max_verdict is True


def test_an_unclassified_contradiction_is_not_counter_evidence_either():
    items = [
        evidence("E1", family="CFPB complaints"),
        evidence(
            "E2",
            family="Federal court records",
            mechanism="unclassified_credit_reporting_complaint",
            standing=ADJUDICATED,
            posture=TRIAL_JUDGMENT,
            direction=FOR_RESPONDENT,
        ),
    ]

    assert gate(evaluate_proof_gates(items, [], []), "PG-13").status == "WEAK"


def test_adjudicated_evidence_does_not_inflate_the_source_family_count():
    """Court opinions are the courts deciding the same disputes RECAP records.

    Standing and independence are separate axes, and letting an adjudication count
    as a new forum would double-count one dispute as two.
    """
    items = [
        evidence("E1", family="CFPB complaints"),
        evidence("E2", family="Federal court records"),
        evidence(
            "E3",
            family="Federal court records",
            standing=ADJUDICATED,
            posture=TRIAL_JUDGMENT,
            direction=AGAINST_RESPONDENT,
        ),
    ]

    verdict = make_verdict("GS-CF001-C", evaluate_proof_gates(items, [], []), [], [], items)

    assert verdict.independent_source_family_count == 2
    assert verdict.occurrence_established_count == 1


def test_adding_forums_never_changes_standing():
    """Ten independent complaint databases still yield zero adjudications."""
    items = [evidence(f"E{index}", family=f"Complaints {index}") for index in range(10)]

    verdict = make_verdict("GS-CF001-C", evaluate_proof_gates(items, [], []), [], [], items)

    assert verdict.independent_source_family_count == 10
    assert verdict.occurrence_established_count == 0


def test_a_source_defaults_to_alleged_standing():
    """Nothing becomes adjudicated by being added to the study."""
    source = Source(
        source_id="S1",
        name="Any source",
        source_type="whatever",
        base_url="https://example.invalid",
        jurisdiction="United States",
        role="discovery",
    )

    assert source.evidentiary_standing == ALLEGED
    assert replace(source, evidentiary_standing=ADJUDICATED).evidentiary_standing == ADJUDICATED
