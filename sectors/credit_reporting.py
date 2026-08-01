"""GS-CF001-C: US credit-reporting dispute handling.

Every term list and every mechanism rule here was previously a module constant in
`verification/rules.py` or an if-branch in `detect_mechanism`. Nothing has been
rephrased, reordered, or widened: the existing tests are the regression suite for this
extraction, and a "tidy-up" that changed a classification would change the study.

The one addition is the group names. The if-ladder's conditions were anonymous, so a
record that classified for a surprising reason could not say which condition carried it.
"""

from __future__ import annotations

from connectors.cfpb import CFPBConnector
from connectors.courtlistener import CourtListenerConnector
from connectors.fjc_idb import FJCIDBConnector
from sectors.models import MechanismRule, SectorPack, TermGroup

PROCESS_TERMS = (
    "contacted",
    "dispute",
    "disputed",
    "documentation",
    "documents",
    "evidence",
    "investigation",
    "proof",
    "reinvestigation",
    "remove",
    "requested",
    "response",
    "submitted",
)

FAILURE_TERMS = (
    "did not",
    "failed",
    "ignored",
    "no response",
    "not considered",
    "not corrected",
    "not fixed",
    "not removed",
    "rejected",
    "refused",
    "refuses",
    "remained",
    "still inaccurate",
    "unresolved",
)

# These phrases describe an operational step and an alleged failure in the official
# structured taxonomy. Broad labels such as "Incorrect information on your report" are
# deliberately absent: they name a complaint subject, not a process that failed.
TAXONOMY_PHRASES = (
    "investigation into an existing problem",
    "investigation did not fix an error",
    "did not receive notice of the results",
    "was not notified of investigation status or results",
    "problem with fraud alerts or security freezes",
)

SOFTWARE_ADDRESSABLE_TERMS = (
    "communication",
    "dispute",
    "document",
    "evidence",
    "investigation",
    "notification",
    "proof",
    "response",
    "resolution",
    "status",
    "timeline",
)

_ANY_FAILURE = TermGroup("any_failure", FAILURE_TERMS)
_DISPUTE = TermGroup("dispute", ("dispute", "disputed"))
_INVESTIGATION = TermGroup("investigation", ("investigation", "reinvestigation"))
_SUPPORTING_EVIDENCE = TermGroup(
    "supporting_evidence", ("documentation", "documents", "evidence", "proof")
)
_NOTIFICATION = TermGroup("notification", ("notification", "status", "communication", "response"))
_DATA_ERROR = TermGroup("data_error", ("incorrect", "inaccurate", "not mine", "tradeline"))
_PERSISTENCE = TermGroup("persistence", ("persist", "remain", "still"))

MECHANISM_RULES = (
    MechanismRule("bureau_dispute_reinvestigation_failure", ((_DISPUTE,), (_INVESTIGATION,))),
    MechanismRule("dispute_supporting_evidence_rejection", ((_SUPPORTING_EVIDENCE,), (_ANY_FAILURE,))),
    MechanismRule("investigation_outcome_notification_failure", ((_NOTIFICATION,), (_ANY_FAILURE,))),
    # The one disjunctive limb: persistent bad data is alleged either by a failure term
    # or by a persistence term, because "the tradeline is still there" alleges a failure
    # without using any of the failure vocabulary.
    MechanismRule(
        "furnisher_tradeline_data_error_persistence",
        ((_DATA_ERROR,), (_ANY_FAILURE, _PERSISTENCE)),
    ),
)

DEFAULT_MECHANISM = "unclassified_credit_reporting_complaint"

MECHANISM_DEFINITIONS = {
    "bureau_dispute_reinvestigation_failure": {
        "trigger": "Consumer disputes credit-report information.",
        "operational_step": "Credit bureau dispute intake and reinvestigation.",
        "failure_mode": "The complaint alleges that reinvestigation did not correct or resolve the disputed information.",
        "expected_process": "Receive the dispute, assess supplied information, reinvestigate, and communicate the outcome.",
        "software_addressability_hypothesis": "A dispute-intake, evidence-routing, deadline, and outcome-tracking component may support the workflow.",
    },
    "furnisher_tradeline_data_error_persistence": {
        "trigger": "Consumer identifies allegedly inaccurate or unrecognised tradeline data.",
        "operational_step": "Data-furnisher verification and credit-report correction.",
        "failure_mode": "The complaint alleges that disputed tradeline data persisted after a correction request.",
        "expected_process": "Route the disputed data to the responsible party, investigate it, and update or explain the result.",
        "software_addressability_hypothesis": "A correction-case routing and evidence reconciliation component may support the workflow.",
    },
    "dispute_supporting_evidence_rejection": {
        "trigger": "Consumer supplies documents or other evidence for a dispute.",
        "operational_step": "Supporting-evidence intake, matching, and investigation routing.",
        "failure_mode": "The complaint alleges that supporting evidence was rejected, ignored, or not considered.",
        "expected_process": "Receive, identify, preserve, and route supporting evidence into the investigation.",
        "software_addressability_hypothesis": "An evidence-intake, matching, and audit-trail component may support the workflow.",
    },
    "investigation_outcome_notification_failure": {
        "trigger": "A consumer awaits the status or outcome of a dispute investigation.",
        "operational_step": "Investigation status and outcome communication.",
        "failure_mode": "The complaint alleges that required status or outcome communication was absent or inadequate.",
        "expected_process": "Track the investigation and communicate status and outcome through a traceable channel.",
        "software_addressability_hypothesis": "A deadline-aware notification and communication-record component may support the workflow.",
    },
    DEFAULT_MECHANISM: {
        "trigger": "Consumer reports a credit-reporting concern.",
        "operational_step": "A specific operational step has not yet been established.",
        "failure_mode": "A specific repeated failure mode has not yet been established.",
        "expected_process": "Further evidence is required to define the expected process.",
        "software_addressability_hypothesis": "No component hypothesis should be treated as supported until the mechanism is classified.",
    },
}

CREDIT_REPORTING = SectorPack(
    sector_id="GS-CF001-C",
    name="Credit Reporting Disputes",
    research_question=(
        "Is there enough verified, repeated operational pain in U.S. credit-reporting "
        "dispute handling to justify building a reusable workflow component?"
    ),
    primary_source_family="CFPB complaints",
    process_terms=PROCESS_TERMS,
    failure_terms=FAILURE_TERMS,
    taxonomy_phrases=TAXONOMY_PHRASES,
    software_addressable_terms=SOFTWARE_ADDRESSABLE_TERMS,
    mechanism_rules=MECHANISM_RULES,
    default_mechanism=DEFAULT_MECHANISM,
    mechanism_definitions=MECHANISM_DEFINITIONS,
    # The FJC connector deliberately shares the court records family: it raises
    # evidentiary standing without adding an independent forum.
    connectors={
        "cfpb": CFPBConnector,
        "court": CourtListenerConnector,
        "fjc": FJCIDBConnector,
    },
)
