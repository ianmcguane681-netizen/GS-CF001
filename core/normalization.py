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


def normalise_idb_record(
    raw_record: dict[str, Any], source: Source, study: Study
) -> EvidenceCandidate | None:
    """Normalise one FJC Integrated Database case outcome.

    Admission repeats the connector's statutory check rather than trusting it, so a
    record cannot enter the study by arriving through the right pipeline branch.
    """

    from connectors.fjc_idb import cites_fcra as idb_cites_fcra

    if not idb_cites_fcra(raw_record.get("title"), raw_record.get("section")):
        return None

    record_id = str(raw_record.get("idb_record_id") or raw_record.get("_source_record_id") or "")
    source_url = str(raw_record.get("_retrieval_url") or source.base_url)
    posture = str(raw_record.get("adjudication_posture") or "")
    direction = str(raw_record.get("adjudication_direction") or "")
    parsed_fields = {
        "idb_record_id": record_id,
        "docket_number": raw_record.get("docket_number") or "",
        "plaintiff": raw_record.get("plaintiff") or "",
        # The defendant is a coded party field here, not a caption guess.
        "company": raw_record.get("defendant") or "",
        "district": raw_record.get("district") or "",
        "date_filed": raw_record.get("date_filed") or "",
        "date_terminated": raw_record.get("date_terminated") or "",
        "date_received": raw_record.get("date_terminated") or raw_record.get("date_filed") or "",
        "disposition_code": raw_record.get("disposition_code"),
        "judgment_code": raw_record.get("judgment_code"),
        "adjudication_posture": posture,
        "adjudication_direction": direction,
        "adjudication_citation": raw_record.get("pacer_docket_number") or raw_record.get("docket_number") or "",
        # From the RECAP docket join. False whenever the join did not confirm a
        # single consumer-credit docket, including when it could not run at all:
        # unknown subject matter is not permission to count the case.
        "on_study_suit_nature": bool(raw_record.get("on_study_suit_nature")),
        "joined_case_name": raw_record.get("joined_case_name") or "",
        "joined_suit_nature": raw_record.get("joined_suit_nature") or "",
        "join_verified": bool(raw_record.get("join_verified")),
        "join_note": raw_record.get("join_note") or "",
        "occurrence_reasoning": raw_record.get("occurrence_reasoning") or "",
        # The complaint document, where RECAP has it. An outcome code is not a
        # narrative and must never be read as one, but a complaint is the
        # plaintiff's own account of what happened -- the same evidentiary class as
        # a CFPB consumer narrative -- so the classifier applies to it unchanged.
        # Empty whenever the document could not be identified with certainty.
        "narrative": raw_record.get("complaint_text") or "",
        "narrative_source": raw_record.get("complaint_text_note") or "",
        "product": "Credit reporting or other personal consumer reports",
        "issue": "Adjudicated Fair Credit Reporting Act claim",
        "sub_issue": f"disposition={raw_record.get('disposition_code')}; judgment={raw_record.get('judgment_code')}",
    }
    traceability = [
        f"Retrieved FJC Integrated Database case outcome from {source_url}",
        f"Admitted case {record_id} on coded statute title {raw_record.get('title')!r} section {raw_record.get('section')!r}",
        f"Classified posture {posture!r} direction {direction!r} from official FJC codes",
        f"Docket join {'confirmed' if raw_record.get('join_verified') else 'not confirmed'}: {raw_record.get('join_note') or 'not attempted'}",
        f"Suit nature {raw_record.get('joined_suit_nature') or 'unknown'!r}; on study subject matter: {bool(raw_record.get('on_study_suit_nature'))}",
        f"Mechanism narrative: {raw_record.get('complaint_text_note') or 'not attempted'}",
        "Normalised coded case outcome into source-agnostic EvidenceCandidate",
    ]
    candidate_id = stable_id(
        "CAN",
        {"source": source.source_id, "study": study.study_id, "idb": record_id, "raw": raw_record},
    )
    transitions = [
        transition(
            record_id or candidate_id,
            SOURCE_RECORD,
            NORMALISED_RECORD,
            "FJC IDB case outcome normalisation v1",
            [record_id],
            "Normalised coded federal case outcome.",
            1.0,
            ["Outcome codes describe who prevailed, not the operational mechanism."],
        ).to_dict(),
        transition(
            candidate_id,
            NORMALISED_RECORD,
            EVIDENCE_CANDIDATE,
            "GS-CF001-C coded statutory basis mapping rule v1",
            [record_id],
            "Mapped FCRA statutory basis to Credit Reporting Disputes evidence candidate.",
            1.0,
            [str(raw_record.get("occurrence_reasoning") or "")],
        ).to_dict(),
    ]
    return EvidenceCandidate(
        candidate_id=candidate_id,
        source=source,
        study=study,
        source_record_id=record_id,
        source_url=source_url,
        retrieved_at=str(raw_record.get("_retrieved_at") or ""),
        raw_record=raw_record,
        parsed_fields=parsed_fields,
        study_mapping_reason="Case arises under the Fair Credit Reporting Act by coded statute.",
        traceability=traceability,
        state_transitions=transitions,
    )


def normalise_idb_records(
    raw_records: list[dict[str, Any]], source: Source, study: Study
) -> list[EvidenceCandidate]:
    candidates = []
    for raw_record in raw_records:
        candidate = normalise_idb_record(raw_record, source, study)
        if candidate:
            candidates.append(candidate)
    return candidates


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
