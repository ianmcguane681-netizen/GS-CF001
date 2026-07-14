from __future__ import annotations

from collections import Counter

from core.ids import stable_id
from core.models import EvidenceCandidate, VerifiedEvidence
from verification.rules import OPERATIONAL_TERMS, SOFTWARE_ADDRESSABLE_TERMS, contains_any, detect_mechanism


def _candidate_text(candidate: EvidenceCandidate) -> str:
    fields = candidate.parsed_fields
    return " ".join(
        str(fields.get(key) or "")
        for key in ["product", "sub_product", "issue", "sub_issue", "company", "company_response", "narrative"]
    )


def verify_candidate(candidate: EvidenceCandidate, repeated_mechanisms: set[str] | None = None) -> VerifiedEvidence:
    repeated_mechanisms = repeated_mechanisms or set()
    text = _candidate_text(candidate)
    company_name = str(candidate.parsed_fields.get("company") or "")
    mechanism = detect_mechanism(text)
    operational = contains_any(text, OPERATIONAL_TERMS)
    traceable = bool(candidate.source_url and candidate.raw_record and candidate.source_record_id)
    software_addressable = contains_any(text, SOFTWARE_ADDRESSABLE_TERMS)
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

    status = "verified_candidate" if operational and traceable and software_addressable else "rejected_candidate"
    evidence_id = stable_id("EVD", {"candidate": candidate.candidate_id, "mechanism": mechanism})
    reasoning = [
        f"Verified candidate {candidate.candidate_id} for operational content.",
        f"Mechanism classified as {mechanism}.",
        f"Traceability is {'present' if traceable else 'missing'}.",
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
    )


def verify_candidates(candidates: list[EvidenceCandidate]) -> list[VerifiedEvidence]:
    mechanisms = [detect_mechanism(_candidate_text(candidate)) for candidate in candidates]
    counts = Counter(mechanisms)
    repeated_mechanisms = {mechanism for mechanism, count in counts.items() if count >= 2}
    return [verify_candidate(candidate, repeated_mechanisms) for candidate in candidates]
