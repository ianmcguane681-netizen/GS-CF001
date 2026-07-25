from __future__ import annotations

from typing import Any

from core.evidence_states import EVIDENCE_CANDIDATE, NORMALISED_RECORD, SOURCE_RECORD, transition
from core.ids import stable_id
from core.models import EvidenceCandidate, Source, Study


def normalise_cfpb_record(raw_record: dict[str, Any], source: Source, study: Study) -> EvidenceCandidate | None:
    product = str(raw_record.get("product") or "")
    if "credit reporting" not in product.lower() and "consumer reports" not in product.lower():
        return None

    complaint_id = str(raw_record.get("complaint_id") or raw_record.get("_source_record_id") or raw_record.get("_cfpb_hit_id") or "")
    source_url = str(raw_record.get("_retrieval_url") or source.base_url)
    parsed_fields = {
        "complaint_id": complaint_id,
        "product": product,
        "sub_product": raw_record.get("sub_product") or "",
        "issue": raw_record.get("issue") or "",
        "sub_issue": raw_record.get("sub_issue") or "",
        "company": raw_record.get("company") or "",
        "state": raw_record.get("state") or "",
        "date_received": raw_record.get("date_received") or "",
        "submitted_via": raw_record.get("submitted_via") or "",
        "company_response": raw_record.get("company_response") or "",
        "timely": raw_record.get("timely") or "",
        "consumer_disputed": raw_record.get("consumer_disputed") or "",
        "narrative": raw_record.get("complaint_what_happened") or "",
    }
    traceability = [
        f"Retrieved raw CFPB record from {source_url}",
        f"Mapped CFPB complaint {complaint_id} to {study.study_id}",
        "Normalised CFPB fields into source-agnostic EvidenceCandidate",
    ]
    candidate_id = stable_id("CAN", {"source": source.source_id, "study": study.study_id, "complaint_id": complaint_id, "raw": raw_record})
    transitions = [
        transition(
            complaint_id or candidate_id,
            SOURCE_RECORD,
            NORMALISED_RECORD,
            "CFPB field normalisation v1",
            [complaint_id],
            "Normalised CFPB raw record fields.",
            1.0,
            ["Normalisation does not verify complaint truth."],
        ).to_dict(),
        transition(
            candidate_id,
            NORMALISED_RECORD,
            EVIDENCE_CANDIDATE,
            "GS-CF001-C product mapping rule v1",
            [complaint_id],
            "Mapped to Credit Reporting Disputes evidence candidate.",
            1.0,
            ["Product mapping is deterministic but source record fields may be incomplete."],
        ).to_dict(),
    ]
    return EvidenceCandidate(
        candidate_id=candidate_id,
        source=source,
        study=study,
        source_record_id=complaint_id,
        source_url=source_url,
        retrieved_at=str(raw_record.get("_retrieved_at") or ""),
        raw_record=raw_record,
        parsed_fields=parsed_fields,
        study_mapping_reason="CFPB product maps to Credit Reporting Disputes.",
        traceability=traceability,
        state_transitions=transitions,
    )


def normalise_court_record(raw_record: dict[str, Any], source: Source, study: Study) -> EvidenceCandidate | None:
    """Normalise a federal docket into a source-agnostic evidence candidate.

    Admission is deterministic on the statutory cause: a docket is only mapped to
    this study when the court itself records the claim as arising under the FCRA.
    The narrative is left empty on purpose - a docket caption is not a consumer
    account of what happened, and must not be mined as though it were one.
    """

    from connectors.courtlistener import cites_fcra

    cause = str(raw_record.get("cause") or "")
    suit_nature = str(raw_record.get("suit_nature") or "")
    if not cites_fcra(cause, suit_nature):
        return None

    docket_id = str(raw_record.get("docket_id") or raw_record.get("_source_record_id") or "")
    source_url = str(raw_record.get("_retrieval_url") or source.base_url)
    parsed_fields = {
        "docket_id": docket_id,
        "case_name": raw_record.get("case_name") or "",
        "court": raw_record.get("court") or "",
        "court_id": raw_record.get("court_id") or "",
        "docket_number": raw_record.get("docket_number") or "",
        "date_filed": raw_record.get("date_filed") or "",
        "date_terminated": raw_record.get("date_terminated") or "",
        "cause": cause,
        "suit_nature": suit_nature,
        "parties": raw_record.get("parties") or [],
        "company": _defendant_from_caption(str(raw_record.get("case_name") or "")),
        # No consumer narrative exists in docket metadata. Leaving this empty keeps
        # the verification rules from treating a case caption as a first-hand account.
        "narrative": "",
        "issue": cause,
        "sub_issue": suit_nature,
    }
    traceability = [
        f"Retrieved federal docket record from {source_url}",
        f"Admitted docket {docket_id} on statutory cause {cause!r}",
        "Normalised docket metadata into source-agnostic EvidenceCandidate",
    ]
    candidate_id = stable_id(
        "CAN",
        {"source": source.source_id, "study": study.study_id, "docket_id": docket_id, "raw": raw_record},
    )
    transitions = [
        transition(
            docket_id or candidate_id,
            SOURCE_RECORD,
            NORMALISED_RECORD,
            "Court docket normalisation v1",
            [docket_id],
            "Normalised federal docket metadata.",
            1.0,
            ["A filed claim is an allegation, not a finding of fact."],
        ).to_dict(),
        transition(
            candidate_id,
            NORMALISED_RECORD,
            EVIDENCE_CANDIDATE,
            "GS-CF001-C statutory cause mapping rule v1",
            [docket_id],
            "Mapped FCRA statutory cause to Credit Reporting Disputes evidence candidate.",
            1.0,
            ["Statutory cause is deterministic but does not describe the operational mechanism."],
        ).to_dict(),
    ]
    return EvidenceCandidate(
        candidate_id=candidate_id,
        source=source,
        study=study,
        source_record_id=docket_id,
        source_url=source_url,
        retrieved_at=str(raw_record.get("_retrieved_at") or ""),
        raw_record=raw_record,
        parsed_fields=parsed_fields,
        study_mapping_reason="Docket cause arises under the Fair Credit Reporting Act.",
        traceability=traceability,
        state_transitions=transitions,
    )


def _defendant_from_caption(case_name: str) -> str:
    """Best-effort defendant from a 'PLAINTIFF v. DEFENDANT' caption.

    Reported as a caption-derived label only. Case captions do not reliably name
    the operationally responsible party, so this must not be treated as a verified
    company attribution.
    """

    for separator in (" v. ", " vs. ", " v ", " VS. "):
        if separator in case_name:
            return case_name.split(separator, 1)[1].strip()
    return ""


def normalise_court_records(raw_records: list[dict[str, Any]], source: Source, study: Study) -> list[EvidenceCandidate]:
    candidates = []
    for raw_record in raw_records:
        candidate = normalise_court_record(raw_record, source, study)
        if candidate:
            candidates.append(candidate)
    return candidates


def normalise_cfpb_records(raw_records: list[dict[str, Any]], source: Source, study: Study) -> list[EvidenceCandidate]:
    candidates = []
    for raw_record in raw_records:
        candidate = normalise_cfpb_record(raw_record, source, study)
        if candidate:
            candidates.append(candidate)
    return candidates
