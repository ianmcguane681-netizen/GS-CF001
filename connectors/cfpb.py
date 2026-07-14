from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable

from connectors.base import RetrievalResult
from core.ids import utc_now
from core.models import Source

CFPB_API_BASE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
CFPB_CREDIT_REPORTING_PRODUCT = "Credit reporting or other personal consumer reports"


def cfpb_source() -> Source:
    return Source(
        source_id="CFPB-CCD-001",
        name="CFPB Consumer Complaint Database",
        source_type="public_consumer_complaint_database",
        base_url=CFPB_API_BASE_URL,
        jurisdiction="United States",
        role="discovery",
        notes="Discovery source only. Complaints must be normalised and verified before findings.",
    )


class CFPBConnector:
    source = cfpb_source()

    def __init__(self, fetch_json: Callable[[str], dict[str, Any]] | None = None) -> None:
        self._fetch_json = fetch_json or self._default_fetch_json

    def build_url(self, limit: int = 1) -> str:
        params = {
            "field": "all",
            "format": "json",
            "no_aggs": "true",
            "size": str(limit),
            "sort": "created_date_desc",
            "has_narrative": "true",
            "product": CFPB_CREDIT_REPORTING_PRODUCT,
        }
        return f"{CFPB_API_BASE_URL}?{urllib.parse.urlencode(params)}"

    def retrieve(self, limit: int = 1) -> RetrievalResult:
        url = self.build_url(limit)
        retrieved_at = utc_now()
        try:
            payload = self._fetch_json(url)
            records = self._extract_records(payload, url, retrieved_at)
            return RetrievalResult(self.source, url, retrieved_at, records, [])
        except Exception as exc:
            return RetrievalResult(self.source, url, retrieved_at, [], [f"CFPB retrieval failed: {exc}"])

    def _default_fetch_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "GS-CF001/0.1 methodology proof"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", errors="ignore"))

    def _extract_records(self, payload: dict[str, Any], retrieval_url: str, retrieved_at: str) -> list[dict[str, Any]]:
        hits = payload.get("hits", {}).get("hits", [])
        records: list[dict[str, Any]] = []
        for hit in hits:
            source_record = dict(hit.get("_source") or {})
            complaint_id = str(source_record.get("complaint_id") or hit.get("_id") or "")
            source_record["_cfpb_hit_id"] = str(hit.get("_id") or complaint_id)
            source_record["_source_record_id"] = complaint_id
            source_record["_retrieval_url"] = retrieval_url
            source_record["_retrieved_at"] = retrieved_at
            source_record["_source_name"] = self.source.name
            records.append(source_record)
        return records

