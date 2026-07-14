from __future__ import annotations

from core.ids import stable_id, utc_now
from core.models import EvidenceStateTransition

SOURCE_RECORD = "SOURCE_RECORD"
NORMALISED_RECORD = "NORMALISED_RECORD"
EVIDENCE_CANDIDATE = "EVIDENCE_CANDIDATE"
VERIFIED_WITHIN_SOURCE = "VERIFIED_WITHIN_SOURCE"
CFPB_LIMITED_EVIDENCE = "CFPB_LIMITED_EVIDENCE"
INDEPENDENTLY_CORROBORATED_EVIDENCE = "INDEPENDENTLY_CORROBORATED_EVIDENCE"
FINDING_ELIGIBLE = "FINDING_ELIGIBLE"
OPPORTUNITY_ASSESSMENT_ELIGIBLE = "OPPORTUNITY_ASSESSMENT_ELIGIBLE"


def transition(
    evidence_id: str,
    previous_state: str,
    new_state: str,
    rule_or_process: str,
    inputs: list[str],
    output: str,
    confidence: float,
    limitations: list[str],
    actor_type: str = "deterministic rule",
) -> EvidenceStateTransition:
    payload = {
        "evidence_id": evidence_id,
        "previous_state": previous_state,
        "new_state": new_state,
        "rule_or_process": rule_or_process,
        "inputs": inputs,
        "output": output,
    }
    return EvidenceStateTransition(
        transition_id=stable_id("TRN", payload),
        evidence_id=evidence_id,
        previous_state=previous_state,
        new_state=new_state,
        rule_or_process=rule_or_process,
        timestamp=utc_now(),
        inputs=inputs,
        output=output,
        confidence=confidence,
        limitations=limitations,
        actor_type=actor_type,
    )
