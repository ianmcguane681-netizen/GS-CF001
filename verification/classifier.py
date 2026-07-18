"""verification/classifier.py — Deterministic evidence verification.

Verification answers: "Is this complaint about a traceable operational workflow
failure?" It does NOT answer: "Can software fix this?" That question is
answered downstream by the mechanism classifier (findings/mechanism_classifier.py).

verified_candidate status requires:
    operational=True  (narrative process + failure, or explicit operational taxonomy)
    traceable=True    (source URL, raw record, and record ID all present)

software_addressable is recorded as a flag but is NOT a gate on
verified_candidate status. Moving software addressability to the classification
layer (rather than the verification gate) ensures that complaints describing
operational failures that are not software-addressable (e.g., legal violations,
staffing issues, regulatory non-compliance) are not silently discarded before
reaching the findings engine and ODR — they reach both and correctly produce
REJECTED outcomes via the non_software_problem classification.
"""
from __future__ import annotations

from collections import Counter

from core.evidence_states import CFPB_LIMITED_EVIDENCE, EVIDENCE_CANDIDATE, VERIFIED_WITHIN_SOURCE, transition
from core.ids import stable_id
from core.models import EvidenceCandidate, VerifiedEvidence
from verification.rules import (
    SOFTWARE_ADDRESSABLE_TERMS,
    detect_mechanism,
    matched_terms,
    operational_assessment,
)


def _candidate_text(candidate: EvidenceCandidate) -> str:
    fields = candidate.parsed_fields
    return " ".join(
        str(fields.get(key) or "")
        for key in ["product", "sub_product", "issue", "sub_issue", "company", "company_response", "narrative"]
    )


def verify_candidate(candidate: EvidenceCandidate, repeated_mechanisms: set[str] | None = None) -> VerifiedEvidence:
    repeated_mechanisms = repeated_mechanisms or set()
    text = _candidate_text(candidate)
    narrative = str(candidate.parsed_fields.get("narrative") or "").strip()
    company_name = str(candidate.parsed_fields.get("company") or "")
    mechanism = detect_mechanism(text)
    operational, operational_basis, operational_matches = operational_assessment(
        candidate.parsed_fields
    )
    traceable = bool(candidate.source_url and candidate.raw_record and candidate.source_record_id)
    software_matches = matched_terms(text, SOFTWARE_ADDRESSABLE_TERMS)
    software_addressable = bool(software_matches)
    repeated_signal = mechanism in repeated_mechanisms
    independently_corrobored = False
    missing = []
    if not operational:
        missing.append("operational complaint mechanism")
    if not traceable:
        missing.append("traceable source URL and raw record")
    if not software_addressable:
        missing.append("software-addressable workflow mechanism")
    if not repeated_signal:
        missing.append("independent complaint repetition")
    missing.append("independent non-CFPB corroboration")

    # Gate: operational AND traceable. software_addressable is intentionally
    # NOT a gate here — it is a classification input, not a verification
    # criterion. Operationally-real but non-software-addressable complaints
    # must reach the findings engine so they can produce REJECTED ODR outcomes.
    status = "verified_candidate" if operational and traceable else "rejected_candidate"

    evidence_id = stable_id("EVD", {"candidate": candidate.candidate_id, "mechanism": mechanism})
    new_state = CFPB_LIMITED_EVIDENCE if candidate.source.source_family == "CFPB complaints" and status == "verified_candidate" else VERIFIED_WITHIN_SOURCE
    state_transition = transition(
        evidence_id,
        EVIDENCE_CANDIDATE,
        new_state,
        "Verification V1 deterministic classification",
        [candidate.candidate_id],
        status,
        0.75 if status == "verified_candidate" else 0.35,
        ["CFPB data alone cannot independently corroborate the underlying allegation."],
    )
    reasoning = [
        (
            f"Operational qualification basis: {operational_basis}; "
            f"matched terms: {', '.join(operational_matches) or 'none'}."
        ),
        f"Mechanism classified as {mechanism}.",
        f"Traceability is {'present' if traceable else 'missing'}.",
        f"Software addressability: {software_addressable} (classification input only, not a verification gate).",
        "Verification does not assess whether software should be built.",
    ]
    return VerifiedEvidence(
        evidence_id=evidence_id,
        candidate_id=candidate.candidate_id,
        study_id=candidate.study.study_id,
        source_record_id=candidate.source_record_id,
        company_name=company_name,
        verification_status=status,
        operational=operational,
        traceable=traceable,
        software_addressable=software_addressable,
        repeated_signal=repeated_signal,
        independently_corrobored=independently_corrobored,
        mechanism=mechanism,
        reasoning_chain=reasoning,
        supporting_candidate_ids=[candidate.candidate_id],
        missing_evidence=missing,
        evidence_state=new_state,
        source_family=candidate.source.source_family,
        product=str(candidate.parsed_fields.get("product") or ""),
        issue=str(candidate.parsed_fields.get("issue") or ""),
        date_received=str(candidate.parsed_fields.get("date_received") or ""),
        source_limitations=[
            "CFPB consumer narratives are not independently verified.",
            "CFPB complaint repetition does not prove operational failure.",
            "CFPB records do not establish market prevalence.",
        ],
        alternative_explanations=[
            "Complaint may reflect misunderstanding, missing documentation, or company-specific handling.",
            "Repeated complaint terms may reflect CFPB taxonomy rather than a common root cause.",
        ],
        state_transitions=[state_transition.to_dict()],
        narrative_available=bool(narrative),
        operational_basis=operational_basis,
        operational_terms_matched=operational_matches,
        software_terms_matched=software_matches,
    )


def verify_candidates(candidates: list[EvidenceCandidate]) -> list[VerifiedEvidence]:
    mechanisms = [detect_mechanism(_candidate_text(candidate)) for candidate in candidates]
    counts = Counter(mechanisms)
    repeated_mechanisms = {mechanism for mechanism, count in counts.items() if count >= 2}
    return [verify_candidate(candidate, repeated_mechanisms) for candidate in candidates]
