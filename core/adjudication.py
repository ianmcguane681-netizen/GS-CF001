"""Whether an alleged failure actually occurred, and what is allowed to establish it.

The second source family made the alleged mechanism independent: consumer
allegations made to a regulator, and claims filed in court by different parties in
a different forum. The review board accepted that independence and then named the
gap it leaves open:

    "Complaints are consumer allegations to a regulator and filings are claims put
    to a court. Two independent forums now allege the same mechanism, which
    establishes independence, but neither establishes that the alleged failures
    occurred."                                            -- FND3-SR-001, SEV-2

The accepted remediation was a requirement: a judgment, consent order or
examination finding before asserting the failure occurred. This module is that
requirement. It adds a second axis to evidence, orthogonal to source family:

    source family        does this share an origin with evidence we already hold?
    evidentiary standing is this an allegation, or has a forum decided it?

Adding forums moves the first axis. Only a decision moves the second. The study
could retrieve ten independent complaint databases and remain at ALLEGED.

The rule is deliberately hard to satisfy, because for most records the honest
answer is "this establishes nothing". Procedural posture governs, and posture is
routinely misread:

  * Denying a motion to dismiss establishes nothing. To decide that motion the
    court *assumes the allegations are true*. Treating it as proof of occurrence
    would launder an allegation into a finding under a judge's name -- precisely
    the error the board flagged, made harder to see.
  * Denying summary judgment establishes the opposite of a settled fact: that the
    facts are genuinely disputed and must go to trial.
  * An appellate disposition is relative to the judgment below. "Affirmed" against
    an unknown lower judgment is not a direction. Affirming a defence win and
    affirming a plaintiff win are opposite outcomes behind one word.
  * A settlement or voluntary dismissal is not an admission.

So the classifier refuses to guess. Anything it cannot resolve from explicit
structured values is UNDETERMINED, and UNDETERMINED never establishes occurrence.
Being wrong in this direction costs a research step; being wrong in the other
direction puts an unproven claim into a build decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# --- Axis one is source_family, defined on Source. This is axis two. -----------

ALLEGED = "ALLEGED"
ADJUDICATED = "ADJUDICATED"
EVIDENTIARY_STANDINGS = (ALLEGED, ADJUDICATED)

# --- Posture: what kind of decision this was ----------------------------------

MOTION_TO_DISMISS = "MOTION_TO_DISMISS"
SUMMARY_JUDGMENT = "SUMMARY_JUDGMENT"
TRIAL_JUDGMENT = "TRIAL_JUDGMENT"
CONSENT_ORDER = "CONSENT_ORDER"
EXAMINATION_FINDING = "EXAMINATION_FINDING"
SETTLEMENT = "SETTLEMENT"
APPELLATE_REVIEW = "APPELLATE_REVIEW"
UNDETERMINED_POSTURE = "UNDETERMINED"

# The postures capable of resolving the merits. Membership here is necessary, not
# sufficient: direction still has to have gone against the respondent.
#
# CONSENT_ORDER is included because the board named it, and it is worth being
# explicit about what that costs. A consent order records findings made by the
# regulator, and the respondent typically consents to entry without admitting or
# denying them. It is an official adjudicated finding, which is what was asked
# for; it is not a confession, and nothing here should be read as calling it one.
MERITS_POSTURES = frozenset(
    {SUMMARY_JUDGMENT, TRIAL_JUDGMENT, CONSENT_ORDER, EXAMINATION_FINDING}
)

# Deciding these resolves no fact about whether the failure happened.
NON_MERITS_POSTURES = frozenset(
    {MOTION_TO_DISMISS, SETTLEMENT, APPELLATE_REVIEW, UNDETERMINED_POSTURE}
)

# --- Direction: who the decision went against --------------------------------

AGAINST_RESPONDENT = "AGAINST_RESPONDENT"
FOR_RESPONDENT = "FOR_RESPONDENT"
UNDETERMINED_DIRECTION = "UNDETERMINED"

# Exact-match vocabulary for a forum's own structured disposition value. Free text
# is not parsed and near-matches are not accepted: an unrecognised value is
# UNDETERMINED, which is the safe answer.
#
# Appellate words map to APPELLATE_REVIEW with no direction on purpose. They
# describe what happened to the judgment below, and until that judgment is also
# recorded they carry no direction of their own.
DISPOSITION_VOCABULARY: dict[str, tuple[str, str]] = {
    "judgment for plaintiff": (TRIAL_JUDGMENT, AGAINST_RESPONDENT),
    "judgment for defendant": (TRIAL_JUDGMENT, FOR_RESPONDENT),
    "summary judgment for plaintiff": (SUMMARY_JUDGMENT, AGAINST_RESPONDENT),
    "summary judgment for defendant": (SUMMARY_JUDGMENT, FOR_RESPONDENT),
    "consent order entered": (CONSENT_ORDER, AGAINST_RESPONDENT),
    "examination finding issued": (EXAMINATION_FINDING, AGAINST_RESPONDENT),
    "affirmed": (APPELLATE_REVIEW, UNDETERMINED_DIRECTION),
    "reversed": (APPELLATE_REVIEW, UNDETERMINED_DIRECTION),
    "vacated": (APPELLATE_REVIEW, UNDETERMINED_DIRECTION),
    "remanded": (APPELLATE_REVIEW, UNDETERMINED_DIRECTION),
    "affirmed in part": (APPELLATE_REVIEW, UNDETERMINED_DIRECTION),
    "reversed in part": (APPELLATE_REVIEW, UNDETERMINED_DIRECTION),
    "settled": (SETTLEMENT, UNDETERMINED_DIRECTION),
    "dismissed": (UNDETERMINED_POSTURE, UNDETERMINED_DIRECTION),
    "motion to dismiss denied": (MOTION_TO_DISMISS, UNDETERMINED_DIRECTION),
    "motion to dismiss granted": (MOTION_TO_DISMISS, UNDETERMINED_DIRECTION),
    "summary judgment denied": (SUMMARY_JUDGMENT, UNDETERMINED_DIRECTION),
}


def classify_disposition(disposition: str) -> tuple[str, str]:
    """Map a forum's structured disposition value to (posture, direction).

    Deterministic and total: every input returns a pair, and anything outside the
    vocabulary -- including the empty string the unauthenticated CourtListener
    search API returns for `disposition` -- is UNDETERMINED on both axes.
    """

    key = " ".join(str(disposition or "").strip().lower().split())
    return DISPOSITION_VOCABULARY.get(key, (UNDETERMINED_POSTURE, UNDETERMINED_DIRECTION))


def establishes_occurrence(posture: str, direction: str) -> bool:
    """True only when a forum resolved the merits against the respondent."""

    return posture in MERITS_POSTURES and direction == AGAINST_RESPONDENT


def contradicts_occurrence(posture: str, direction: str) -> bool:
    """True when a forum resolved the merits in the respondent's favour.

    This is counter-evidence on the same mechanism, and it is why the adjudicated
    tier cuts both ways. A source that can only ever confirm is not a source.
    """

    return posture in MERITS_POSTURES and direction == FOR_RESPONDENT


def occurrence_reasoning(posture: str, direction: str) -> str:
    """Say plainly why this record does or does not establish occurrence."""

    if establishes_occurrence(posture, direction):
        return f"{posture} resolved against the respondent: occurrence established."
    if contradicts_occurrence(posture, direction):
        return f"{posture} resolved in the respondent's favour: occurrence contradicted."
    if posture == MOTION_TO_DISMISS:
        return (
            "Motion-to-dismiss posture: the court assumed the allegations were true "
            "to decide the motion, so it found no fact."
        )
    if posture == APPELLATE_REVIEW:
        return (
            "Appellate disposition is relative to the judgment below, which is not "
            "recorded here, so it carries no direction."
        )
    if posture == SETTLEMENT:
        return "A settlement is not an admission and establishes no fact."
    if posture in MERITS_POSTURES:
        return f"{posture} reached the merits but no direction was determinable."
    return "Posture not determinable from the available structured metadata."


@dataclass(frozen=True)
class AdjudicatedFinding:
    """One forum decision, and what it is permitted to support.

    `establishes_occurrence` is derived rather than supplied, so a caller cannot
    assert occurrence by setting a flag. It has to come from posture and direction.
    """

    adjudication_id: str
    forum: str
    citation: str
    respondent: str
    mechanism: str
    posture: str
    direction: str
    decided_date: str = ""
    source_url: str = ""
    reasoning_chain: list[str] = field(default_factory=list)

    @property
    def establishes_occurrence(self) -> bool:
        return establishes_occurrence(self.posture, self.direction)

    @property
    def contradicts_occurrence(self) -> bool:
        return contradicts_occurrence(self.posture, self.direction)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["establishes_occurrence"] = self.establishes_occurrence
        data["contradicts_occurrence"] = self.contradicts_occurrence
        data["occurrence_reasoning"] = occurrence_reasoning(self.posture, self.direction)
        return data
