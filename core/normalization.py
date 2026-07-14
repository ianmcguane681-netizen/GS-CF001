from __future__ import annotations

from typing import Any

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
    )


def normalise_cfpb_records(raw_records: list[dict[str, Any]], source: Source, study: Study) -> list[EvidenceCandidate]:
    candidates = []
    for raw_record in raw_records:
        candidate = normalise_cfpb_record(raw_record, source, study)
        if candidate:
            candidates.append(candidate)
    return candidates

