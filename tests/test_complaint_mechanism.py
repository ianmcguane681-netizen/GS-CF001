"""Where an adjudicated record finally gets a mechanism.

The board's open SEV-2 left the study here: the IDB records that an FCRA violation
was found but never which duty was breached, and docket metadata carries a cause
and a suit-nature category but no narrative. So adjudicated records classified to
the unclassified fallback and could corroborate nothing.

A complaint document closes that. It is the plaintiff's own account of what
happened -- the same evidentiary class as a CFPB consumer narrative -- so the
study's existing classifier applies to it unchanged rather than needing a new kind
of inference. Verified live: the complaint in Proctor v Experian (41,983 characters)
classifies to `bureau_dispute_reinvestigation_failure`.

Two guards matter more than the happy path. Document 1 is the complaint only in an
original proceeding, and the pairing of a pleaded mechanism with a judgment carries
a caveat that has to travel with it.
"""
from __future__ import annotations

from connectors.docket_join import (
    COMPLAINT_LIMITATIONS,
    FJC_ORIGIN_ORIGINAL_PROCEEDING,
    fetch_complaint_text,
)
from verification.rules import detect_mechanism

# Condensed from the live complaint in Washington v Equifax, 5:20-cv-00294.
COMPLAINT = (
    "Plaintiff submitted a written dispute to the credit reporting agency regarding "
    "an inaccurate tradeline. Defendant failed to conduct a reasonable reinvestigation "
    "and did not remove the disputed information."
)


def documents(rows):
    def _fetch(_url):
        return {"results": rows}

    return _fetch


def test_a_complaint_classifies_to_the_studys_mechanism():
    """Verified against the live document, not only this fixture."""
    assert detect_mechanism(COMPLAINT) == "bureau_dispute_reinvestigation_failure"


def test_document_one_of_an_original_proceeding_is_the_complaint():
    text, note = fetch_complaint_text(
        "18429337",
        FJC_ORIGIN_ORIGINAL_PROCEEDING,
        fetch_json=documents([{"document_number": "1", "plain_text": COMPLAINT}]),
    )

    assert text.startswith("Plaintiff submitted")
    assert "original proceeding" in note


def test_a_removed_case_does_not_open_with_a_complaint():
    """Origin 2 is removal from state court, so document 1 is a notice of removal.

    The IDB records origin, so this is read rather than assumed -- and it matters:
    classifying a notice of removal as the plaintiff's account would attribute a
    mechanism to a document that does not describe one.
    """
    text, note = fetch_complaint_text(
        "18429337", 2, fetch_json=documents([{"document_number": "1", "plain_text": COMPLAINT}])
    )

    assert text == ""
    assert "not an original proceeding" in note


def test_a_transferred_or_reopened_case_is_also_refused():
    for origin in (4, 5, 6):
        text, _note = fetch_complaint_text(
            "1", origin, fetch_json=documents([{"document_number": "1", "plain_text": COMPLAINT}])
        )
        assert text == ""


def test_a_missing_origin_is_refused_rather_than_assumed():
    text, note = fetch_complaint_text(
        "1", None, fetch_json=documents([{"document_number": "1", "plain_text": COMPLAINT}])
    )

    assert text == ""
    assert "origin not recorded" in note


def test_only_document_one_is_read():
    """A later filing is not the plaintiff's account of the dispute."""
    text, _note = fetch_complaint_text(
        "1",
        FJC_ORIGIN_ORIGINAL_PROCEEDING,
        fetch_json=documents([{"document_number": "25", "plain_text": "Order on motion to dismiss"}]),
    )

    assert text == ""


def test_absent_document_text_is_an_absence_not_a_finding():
    """RECAP coverage is contributed by users, so a missing document proves nothing."""
    text, note = fetch_complaint_text(
        "1",
        FJC_ORIGIN_ORIGINAL_PROCEEDING,
        fetch_json=documents([{"document_number": "1", "plain_text": ""}]),
    )

    assert text == ""
    assert "no document 1 text available" in note


def test_a_retrieval_failure_is_reported_not_swallowed():
    def failing(_url):
        raise TimeoutError("read timed out")

    text, note = fetch_complaint_text("1", FJC_ORIGIN_ORIGINAL_PROCEEDING, fetch_json=failing)

    assert text == ""
    assert "document retrieval failed" in note


def test_the_pleading_caveat_travels_with_the_text():
    """A complaint states what was alleged; the judgment establishes what was found.

    Reading them together assumes the judgment was entered on the pleaded claim,
    which is usually but not always true where several counts are pleaded.
    """
    limitations = " ".join(COMPLAINT_LIMITATIONS).lower()

    assert "alleged mechanism" in limitations
    assert "several counts" in limitations
    assert "user contributions" in limitations
