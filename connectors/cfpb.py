from __future__ import annotations

import csv
import json
import queue
import ssl
import threading
import urllib.parse
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Protocol

from connectors.base import RetrievalResult
from core.ids import stable_id, utc_now
from core.models import AccessDiagnostic, Source, SourceReliabilityAssessment

CFPB_API_BASE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
CFPB_BULK_DOWNLOAD_URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
CFPB_CREDIT_REPORTING_PRODUCT = "Credit reporting or other personal consumer reports"
RELIABILITY_VERSION = "CFPB-SRA-001"
ACCESS_TIMEOUT_SECONDS = 45


def cfpb_source() -> Source:
    return Source(
        source_id="CFPB-CCD-001",
        name="CFPB Consumer Complaint Database",
        source_type="public_consumer_complaint_database",
        base_url=CFPB_API_BASE_URL,
        jurisdiction="United States",
        role="discovery",
        source_family="CFPB complaints",
        notes="Discovery source only. Complaints must be normalised and verified before findings.",
    )


def cfpb_reliability_assessment(access_method: str, retrieved_at: str) -> SourceReliabilityAssessment:
    return SourceReliabilityAssessment(
        source_id="CFPB-CCD-001",
        source_name="CFPB Consumer Complaint Database",
        publisher="Consumer Financial Protection Bureau",
        publisher_type="U.S. federal consumer financial regulator",
        authority_level="U.S. federal consumer financial regulator",
        jurisdiction="United States",
        source_family="CFPB complaints",
        retrieval_method=access_method,
        retrieval_timestamp=retrieved_at,
        update_frequency="Published by CFPB; update cadence should be confirmed per access method.",
        coverage_period="Depends on retrieved official dataset or query result.",
        record_granularity="Individual consumer complaint record.",
        known_limitations=[
            "Consumer narratives are not independently verified.",
            "Complaint volume alone does not prove operational failure.",
            "The dataset is not statistically representative of the full market.",
            "Complaint volume may reflect company size, consumer awareness, reporting behaviour, or market share.",
            "Similar complaints do not automatically prove a common root cause.",
            "Company response status does not independently validate every consumer allegation.",
            "Records may contain missing or withheld fields.",
            "Public narratives may be unavailable for some records.",
        ],
        verification_constraints=[
            "CFPB complaint repetition can support a repeated complaint signal.",
            "CFPB alone cannot independently corroborate the underlying allegation.",
            "CFPB alone cannot establish a BUILD CANDIDATE verdict.",
            "Independent source evidence is required for stronger commercial conclusions.",
        ],
        independence_constraints=[
            "Multiple CFPB complaints count as one source family.",
            "Different CFPB distribution methods do not create source-family independence.",
            "CFPB complaint records do not independently verify consumer allegations.",
        ],
        representativeness_warning="CFPB complaint records are not a statistically representative market sample.",
        data_completeness_warning="Some CFPB fields may be missing, withheld, amended, or unavailable in public data.",
        permitted_uses=[
            "Discover recurring complaint mechanisms.",
            "Analyse repeated CFPB complaint signals across companies.",
            "Generate CFPB-limited findings requiring independent corroboration.",
        ],
        prohibited_inferences=[
            "Do not infer that alleged failures definitely occurred.",
            "Do not infer market prevalence from complaint volume alone.",
            "Do not infer that software is the best intervention.",
            "Do not produce BUILD CANDIDATE from CFPB data alone.",
        ],
        reliability_version=RELIABILITY_VERSION,
        last_reviewed_date="2026-07-14",
    )


class CFPBAccessAdapter(Protocol):
    method_name: str

    def retrieve(self, limit: int) -> tuple[str, list[dict[str, Any]], list[str], list[AccessDiagnostic]]:
        ...


def _diagnostic(
    endpoint: str,
    access_method: str,
    request_headers: dict[str, str],
    response_status: str,
    response_headers: dict[str, str],
    response_body_summary: str,
    final_interpretation: str,
    request_method: str = "GET",
    retry_result: str = "not retried",
) -> AccessDiagnostic:
    attempted_at = utc_now()
    payload = {
        "endpoint": endpoint,
        "access_method": access_method,
        "status": response_status,
        "at": attempted_at,
    }
    return AccessDiagnostic(
        diagnostic_id=stable_id("ADIAG", payload),
        endpoint=endpoint,
        attempted_at=attempted_at,
        environment="local-python-urllib",
        request_method=request_method,
        request_headers={key: value for key, value in request_headers.items() if key.lower() not in {"authorization", "cookie"}},
        response_status=response_status,
        response_headers=response_headers,
        response_body_summary=response_body_summary[:1000],
        retry_result=retry_result,
        final_interpretation=final_interpretation,
        access_method=access_method,
    )


def _open_without_proxy_autodetect(request: urllib.request.Request, context: ssl.SSLContext | None = None):
    handlers = [urllib.request.ProxyHandler({})]
    if context:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    return opener.open(request, timeout=ACCESS_TIMEOUT_SECONDS)


def _run_bounded_access(callable_to_run: Callable[[], Any]) -> Any:
    output: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            output.put((True, callable_to_run()))
        except BaseException as exc:  # noqa: BLE001 - transport exceptions are captured as diagnostics.
            output.put((False, exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(ACCESS_TIMEOUT_SECONDS)
    if thread.is_alive():
        raise TimeoutError(f"Official CFPB request exceeded {ACCESS_TIMEOUT_SECONDS} seconds.")
    succeeded, value = output.get_nowait()
    if succeeded:
        return value
    raise value


class CFPBAPIAccessAdapter:
    method_name = "official_cfpb_search_api"

    def __init__(self, fetch_json: Callable[[str], tuple[dict[str, Any], dict[str, str], str]] | None = None) -> None:
        self._fetch_json = fetch_json or self._default_fetch_json

    def build_url(self, limit: int = 1) -> str:
        params = {
            "format": "json",
            "no_aggs": "true",
            "size": str(limit),
            "product": CFPB_CREDIT_REPORTING_PRODUCT,
        }
        return f"{CFPB_API_BASE_URL}?{urllib.parse.urlencode(params)}"

    def retrieve(self, limit: int) -> tuple[str, list[dict[str, Any]], list[str], list[AccessDiagnostic]]:
        url = self.build_url(limit)
        headers = {"User-Agent": "GS-CF001/0.1 methodology proof", "Accept": "application/json"}
        try:
            fetched = self._fetch_json(url)
            if isinstance(fetched, tuple):
                payload, response_headers, status = fetched
            else:
                payload, response_headers, status = fetched, {}, "200"
            records = self._extract_records(payload, url)
            diagnostic = _diagnostic(
                url,
                self.method_name,
                headers,
                status,
                response_headers,
                f"Retrieved {len(records)} record(s).",
                "Official CFPB search API returned parseable JSON.",
            )
            return url, records, [], [diagnostic]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            diagnostic = _diagnostic(
                url,
                self.method_name,
                headers,
                str(exc.code),
                dict(exc.headers.items()),
                body,
                "Official CFPB search API request failed from this environment.",
            )
            return url, [], [f"CFPB API access failed: HTTP {exc.code}"], [diagnostic]
        except Exception as exc:
            diagnostic = _diagnostic(url, self.method_name, headers, "error", {}, str(exc), "CFPB API request failed before response.")
            return url, [], [f"CFPB API access failed: {exc}"], [diagnostic]

    def _default_fetch_json(self, url: str) -> tuple[dict[str, Any], dict[str, str], str]:
        def fetch() -> tuple[dict[str, Any], dict[str, str], str]:
            request = urllib.request.Request(url, headers={"User-Agent": "GS-CF001/0.1 methodology proof", "Accept": "application/json"})
            with _open_without_proxy_autodetect(request) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
                return payload, dict(response.headers.items()), str(response.status)

        return _run_bounded_access(fetch)

    def _extract_records(self, payload: dict[str, Any], retrieval_url: str) -> list[dict[str, Any]]:
        hits = payload.get("hits", {}).get("hits", [])
        records: list[dict[str, Any]] = []
        for hit in hits:
            source_record = dict(hit.get("_source") or {})
            complaint_id = str(source_record.get("complaint_id") or hit.get("_id") or "")
            source_record["_cfpb_hit_id"] = str(hit.get("_id") or complaint_id)
            source_record["_source_record_id"] = complaint_id
            source_record["_retrieval_url"] = retrieval_url
            source_record["_source_name"] = cfpb_source().name
            source_record["_access_method"] = self.method_name
            records.append(source_record)
        return records


class CFPBBulkDownloadAccessAdapter:
    method_name = "official_cfpb_bulk_download"

    def __init__(self, opener: Callable[[str], bytes] | None = None) -> None:
        self._opener = opener or self._default_open

    def retrieve(self, limit: int) -> tuple[str, list[dict[str, Any]], list[str], list[AccessDiagnostic]]:
        headers = {"User-Agent": "GS-CF001/0.1 methodology proof", "Accept": "application/zip,text/csv"}
        try:
            content = self._opener(CFPB_BULK_DOWNLOAD_URL)
            records = self._extract_from_zip(content, limit)
            diagnostic = _diagnostic(
                CFPB_BULK_DOWNLOAD_URL,
                self.method_name,
                headers,
                "200",
                {},
                f"Retrieved bulk file and extracted {len(records)} matching record(s).",
                "Official CFPB bulk download returned readable records.",
            )
            return CFPB_BULK_DOWNLOAD_URL, records, [], [diagnostic]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            diagnostic = _diagnostic(
                CFPB_BULK_DOWNLOAD_URL,
                self.method_name,
                headers,
                str(exc.code),
                dict(exc.headers.items()),
                body,
                "Official CFPB bulk download failed from this environment.",
            )
            return CFPB_BULK_DOWNLOAD_URL, [], [f"CFPB bulk download failed: HTTP {exc.code}"], [diagnostic]
        except Exception as exc:
            diagnostic = _diagnostic(CFPB_BULK_DOWNLOAD_URL, self.method_name, headers, "error", {}, str(exc), "CFPB bulk download failed.")
            return CFPB_BULK_DOWNLOAD_URL, [], [f"CFPB bulk download failed: {exc}"], [diagnostic]

    def _default_open(self, url: str) -> bytes:
        def fetch() -> bytes:
            request = urllib.request.Request(url, headers={"User-Agent": "GS-CF001/0.1 methodology proof"})
            context = ssl.create_default_context()
            with _open_without_proxy_autodetect(request, context=context) as response:
                return response.read()

        return _run_bounded_access(fetch)

    def _extract_from_zip(self, content: bytes, limit: int) -> list[dict[str, Any]]:
        import io

        records: list[dict[str, Any]] = []
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
            with archive.open(csv_name) as handle:
                text = io.TextIOWrapper(handle, encoding="utf-8-sig", errors="ignore")
                for row in csv.DictReader(text):
                    if row.get("Product") == CFPB_CREDIT_REPORTING_PRODUCT:
                        records.append(_normalise_bulk_row(row, self.method_name, CFPB_BULK_DOWNLOAD_URL))
                        if len(records) >= limit:
                            break
        return records


class CFPBLocalOfficialSnapshotAdapter:
    method_name = "local_official_cfpb_snapshot"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def retrieve(self, limit: int) -> tuple[str, list[dict[str, Any]], list[str], list[AccessDiagnostic]]:
        headers: dict[str, str] = {}
        endpoint = str(self.path)
        try:
            rows = list(csv.DictReader(self.path.open("r", encoding="utf-8-sig", errors="ignore")))
            records = [
                _normalise_bulk_row(row, self.method_name, endpoint)
                for row in rows
                if row.get("Product") == CFPB_CREDIT_REPORTING_PRODUCT
            ][:limit]
            diagnostic = _diagnostic(endpoint, self.method_name, headers, "local_file_read", {}, f"Read {len(records)} matching record(s).", "Local official snapshot was readable.")
            return endpoint, records, [], [diagnostic]
        except Exception as exc:
            diagnostic = _diagnostic(endpoint, self.method_name, headers, "error", {}, str(exc), "Local official snapshot failed.")
            return endpoint, [], [f"CFPB local official snapshot failed: {exc}"], [diagnostic]


def _normalise_bulk_row(row: dict[str, Any], access_method: str, retrieval_url: str) -> dict[str, Any]:
    complaint_id = str(row.get("Complaint ID") or row.get("complaint_id") or "")
    return {
        "complaint_id": complaint_id,
        "product": row.get("Product") or "",
        "sub_product": row.get("Sub-product") or "",
        "issue": row.get("Issue") or "",
        "sub_issue": row.get("Sub-issue") or "",
        "company": row.get("Company") or "",
        "state": row.get("State") or "",
        "date_received": row.get("Date received") or "",
        "submitted_via": row.get("Submitted via") or "",
        "company_response": row.get("Company response to consumer") or "",
        "timely": row.get("Timely response?") or "",
        "consumer_disputed": row.get("Consumer disputed?") or "",
        "complaint_what_happened": row.get("Consumer complaint narrative") or "",
        "_source_record_id": complaint_id,
        "_retrieval_url": retrieval_url,
        "_source_name": cfpb_source().name,
        "_access_method": access_method,
    }


class CFPBConnector:
    source = cfpb_source()

    def __init__(self, access_adapter: CFPBAccessAdapter | None = None, fetch_json: Callable[[str], tuple[dict[str, Any], dict[str, str], str]] | None = None) -> None:
        self.access_adapter = access_adapter or CFPBAPIAccessAdapter(fetch_json=fetch_json)

    def build_url(self, limit: int = 1) -> str:
        if isinstance(self.access_adapter, CFPBAPIAccessAdapter):
            return self.access_adapter.build_url(limit)
        return self.source.base_url

    def retrieve(self, limit: int = 1) -> RetrievalResult:
        retrieved_at = utc_now()
        retrieval_url, records, errors, diagnostics = self.access_adapter.retrieve(limit)
        for record in records:
            record["_retrieved_at"] = retrieved_at
        return RetrievalResult(
            self.source,
            retrieval_url,
            retrieved_at,
            records,
            errors,
            access_method=self.access_adapter.method_name,
            diagnostics=diagnostics,
            source_reliability=cfpb_reliability_assessment(self.access_adapter.method_name, retrieved_at),
        )
