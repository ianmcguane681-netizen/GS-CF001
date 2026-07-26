"""Adjudicated FCRA outcomes from the Federal Judicial Center Integrated Database.

The review board's open SEV-2 found that consumer complaints and court filings are
both allegations, and that nothing in the study established that any alleged
failure occurred. Closing that needed a source where a forum had *decided*
something, in a form this repository could read without guessing.

Four candidates were probed first and three were rejected -- the Federal Register
is a rulemaking gazette, the FTC refuses automated access, and CFPB enforcement
publishes no machine-readable feed. See
`analysis/source_evaluation_adjudicated_findings.md`.

The IDB is the judiciary's own statistical record of every federal civil case. It
codes two things opinion prose does not:

    disposition   how the case ended        (consent, verdict, settled, ...)
    judgment      who it went for           (plaintiff, defendant, both, unknown)

So posture and direction are read off official codes. That matters, because the
alternative -- parsing dispositions out of opinion text -- is exactly the guessing
this repository refuses, and posture is where guessing does the most damage. An
opinion denying a motion to dismiss *assumes the allegations are true*; misreading
one would convert an allegation into a finding with a judge's name on it.

Admission is statutory and deterministic, matching the RECAP connector's standard:
the FJC records the statute as title and section, so FCRA cases are title 15,
section 1681. No keyword matching on party names or case captions.

What this source is not:

  * Not a new source family. These are the same federal courts RECAP already
    covers, so an IDB record must never lift the independent family count -- one
    dispute would be counted twice. It raises evidentiary standing, not
    independence.
  * Not a census of wrongdoing. Most FCRA cases settle, and a settlement is not an
    admission. The classifier discards them, along with defaults, and with
    defence-side pre-trial judgments it cannot separate from dismissals.
  * Not current. The IDB is published in periodic loads, so recent cases appear
    with null outcome codes until a later load. Absence of a judgment means the
    case is unresolved or uncoded, never that it was decided a particular way.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from connectors.base import RetrievalResult
from connectors.docket_join import DocketJoinAdapter, join_idb_record
from core.adjudication import ADJUDICATED, classify_fjc_disposition, occurrence_reasoning
from core.ids import stable_id, utc_now
from core.models import AccessDiagnostic, Source, SourceReliabilityAssessment

FJC_IDB_URL = "https://www.courtlistener.com/api/rest/v4/fjc-integrated-database/"
# Deliberately the same family as the RECAP connector. See the module docstring.
SOURCE_FAMILY = "Federal court records"
RELIABILITY_VERSION = "FJC-IDB-SRA-001"
ACCESS_TIMEOUT_SECONDS = 45
USER_AGENT = "GS-CF001/0.1 methodology proof"
TOKEN_ENV_VAR = "COURTLISTENER_API_TOKEN"

# 15 U.S.C. 1681 is the Fair Credit Reporting Act. The FJC records the statutory
# basis as separate title and section fields, so admission is a check against the
# statute rather than a guess about the case name.
FCRA_TITLE = "15"
FCRA_SECTION_PREFIX = "1681"


def fjc_idb_source() -> Source:
    return Source(
        source_id="FJC-IDB-FCRA-001",
        name="FJC Integrated Database (federal civil case outcomes)",
        source_type="federal_judicial_outcomes",
        base_url=FJC_IDB_URL,
        jurisdiction="United States",
        role="adjudication",
        source_family=SOURCE_FAMILY,
        evidentiary_standing=ADJUDICATED,
        notes=(
            "Coded case outcomes from the Federal Judicial Center. Raises evidentiary "
            "standing, never the independent source family count: these are the same "
            "courts RECAP already covers."
        ),
    )


def fjc_idb_reliability_assessment(
    access_method: str, retrieved_at: str
) -> SourceReliabilityAssessment:
    return SourceReliabilityAssessment(
        source_id="FJC-IDB-FCRA-001",
        source_name="FJC Integrated Database (federal civil case outcomes)",
        publisher="Federal Judicial Center, republished by the Free Law Project",
        publisher_type="Research and education agency of the United States federal judiciary",
        authority_level="Official judiciary statistical record of case outcomes",
        jurisdiction="United States",
        source_family=SOURCE_FAMILY,
        retrieval_method=access_method,
        retrieval_timestamp=retrieved_at,
        update_frequency="Periodic dataset loads, not continuous.",
        coverage_period="Federal civil cases from SY 1970 onward, depending on dataset.",
        record_granularity="Individual federal civil case, with coded disposition and judgment.",
        known_limitations=[
            "Outcome codes are null for pending cases and for cases not yet in a published load.",
            "Disposition code 6 covers both Rule 12(b)(6) dismissal and Rule 56 summary judgment.",
            "A settlement is coded as an ending, not as an admission of liability.",
            "A default judgment records a forfeiture, not a weighed finding.",
            "Case-level coding does not identify which specific allegation was decided.",
            "Litigation volume reflects propensity to sue, not underlying failure rates.",
            "Party names are as filed and may not identify the operationally responsible entity.",
        ],
        verification_constraints=[
            "A merits judgment for the plaintiff establishes that a violation was found.",
            "Absence of a coded judgment never means a case was decided either way.",
            "A single case establishes occurrence in that case, never market prevalence.",
        ],
        independence_constraints=[
            "NOT independent of the RECAP court records family; the same courts and cases.",
            "Must never increase the independent source family count.",
            "Corroborates only when another family independently alleges the same mechanism.",
        ],
        representativeness_warning=(
            "Cases reaching a merits judgment are a small and unrepresentative fraction: "
            "most FCRA cases settle."
        ),
        data_completeness_warning=(
            "Recent cases carry null outcome codes until a subsequent dataset load."
        ),
        permitted_uses=[
            "Establish that an alleged mechanism was adjudicated against a respondent.",
            "Supply counter-evidence where a merits judgment favoured the respondent.",
            "Raise evidentiary standing from ALLEGED to ADJUDICATED.",
        ],
        prohibited_inferences=[
            "Do not treat a settlement or voluntary dismissal as proof of wrongdoing.",
            "Do not treat a default judgment as a finding on the merits.",
            "Do not infer market prevalence from adjudicated case counts.",
            "Do not count this source toward independent source families.",
        ],
        reliability_version=RELIABILITY_VERSION,
        last_reviewed_date="2026-07-26",
    )


def cites_fcra(title: Any, section: Any) -> bool:
    """Admit a case only when its coded statutory basis is the FCRA."""

    return str(title or "").strip() == FCRA_TITLE and str(section or "").strip().startswith(
        FCRA_SECTION_PREFIX
    )


def _diagnostic(
    endpoint: str,
    access_method: str,
    request_headers: dict[str, str],
    response_status: str,
    response_headers: dict[str, str],
    response_body_summary: str,
    final_interpretation: str,
) -> AccessDiagnostic:
    attempted_at = utc_now()
    return AccessDiagnostic(
        diagnostic_id=stable_id(
            "ADIAG",
            {"endpoint": endpoint, "access_method": access_method, "status": response_status, "at": attempted_at},
        ),
        endpoint=endpoint,
        attempted_at=attempted_at,
        environment="local-urllib-transport",
        request_method="GET",
        request_headers={
            key: value
            for key, value in request_headers.items()
            if key.lower() not in {"authorization", "cookie"}
        },
        response_status=response_status,
        response_headers=response_headers,
        response_body_summary=response_body_summary[:1000],
        retry_result="not retried",
        final_interpretation=final_interpretation,
        access_method=access_method,
    )


class FJCIDBAdapter:
    method_name = "fjc_integrated_database_api"

    def __init__(
        self,
        fetch_json: Callable[[str], tuple[dict[str, Any], dict[str, str], str]] | None = None,
        *,
        token: str | None = None,
    ) -> None:
        self._fetch_json = fetch_json or self._default_fetch_json
        # Read at construction so a missing credential is a clear access
        # diagnostic rather than an unexplained empty result set.
        self.token = token if token is not None else os.environ.get(TOKEN_ENV_VAR, "")

    def build_url(self, limit: int = 1) -> str:
        params = {
            "title": FCRA_TITLE,
            "section__startswith": FCRA_SECTION_PREFIX,
            # Only cases a forum actually decided. Everything else -- settled,
            # dismissed, transferred -- cannot establish or contradict occurrence,
            # so retrieving it would only be discarded downstream.
            "disposition__in": "5,6,7,8,9",
            "judgment__in": "1,2",
            "page_size": str(max(1, min(int(limit), 100))),
        }
        return f"{FJC_IDB_URL}?{urllib.parse.urlencode(params)}"

    def retrieve(
        self, limit: int
    ) -> tuple[str, list[dict[str, Any]], list[str], list[AccessDiagnostic]]:
        url = self.build_url(limit)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if not self.token:
            diagnostic = _diagnostic(
                url,
                self.method_name,
                headers,
                "no_credential",
                {},
                f"{TOKEN_ENV_VAR} is not set in this environment.",
                "The FJC Integrated Database requires an authenticated CourtListener "
                "request. Without a token the study retrieves no adjudicated evidence, "
                "and PG-09 stays unsatisfied for want of data rather than by rule.",
            )
            return url, [], [f"FJC IDB access failed: {TOKEN_ENV_VAR} is not set"], [diagnostic]
        try:
            payload, response_headers, status = self._fetch_json(url)
            records = self._extract_records(payload, url, limit)
            diagnostic = _diagnostic(
                url,
                self.method_name,
                headers,
                status,
                response_headers,
                f"Retrieved {len(records)} adjudicated FCRA case record(s).",
                "FJC Integrated Database returned parseable JSON.",
            )
            return url, records, [], [diagnostic]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            diagnostic = _diagnostic(
                url,
                self.method_name,
                headers,
                str(exc.code),
                dict(exc.headers.items()) if exc.headers else {},
                body,
                "FJC Integrated Database request failed from this environment.",
            )
            return url, [], [f"FJC IDB access failed: HTTP {exc.code}"], [diagnostic]
        except Exception as exc:  # noqa: BLE001 - reported as a diagnostic, never swallowed
            diagnostic = _diagnostic(
                url,
                self.method_name,
                headers,
                "error",
                {},
                str(exc),
                "FJC IDB request failed before a response was parsed.",
            )
            return url, [], [f"FJC IDB access failed: {exc}"], [diagnostic]

    def _default_fetch_json(self, url: str) -> tuple[dict[str, Any], dict[str, str], str]:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Authorization": f"Token {self.token}",
            },
        )
        with urllib.request.urlopen(request, timeout=ACCESS_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="ignore")
            return json.loads(body), dict(response.headers.items()), str(response.status)

    def _extract_records(
        self, payload: dict[str, Any], retrieval_url: str, limit: int
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for row in payload.get("results") or []:
            # Deterministic admission: the coded statutory basis must be the FCRA.
            if not cites_fcra(row.get("title"), row.get("section")):
                continue
            records.append(_normalise_idb_row(row, self.method_name, retrieval_url))
            if len(records) >= limit:
                break
        return records


def _normalise_idb_row(
    row: dict[str, Any], access_method: str, retrieval_url: str
) -> dict[str, Any]:
    posture, direction = classify_fjc_disposition(row.get("disposition"), row.get("judgment"))
    resource_uri = str(row.get("resource_uri") or "")
    record_id = resource_uri.rstrip("/").rsplit("/", 1)[-1] or str(row.get("docket_number") or "")
    return {
        "idb_record_id": record_id,
        "office": row.get("office") or "",
        "docket_number": row.get("docket_number") or "",
        "plaintiff": row.get("plaintiff") or "",
        "defendant": row.get("defendant") or "",
        "district": row.get("district") or "",
        "circuit": row.get("circuit") or "",
        "date_filed": row.get("date_filed") or "",
        "date_terminated": row.get("date_terminated") or "",
        "nature_of_suit": row.get("nature_of_suit"),
        "title": row.get("title") or "",
        "section": row.get("section") or "",
        "disposition_code": row.get("disposition"),
        "judgment_code": row.get("judgment"),
        "nature_of_judgement": row.get("nature_of_judgement"),
        "adjudication_posture": posture,
        "adjudication_direction": direction,
        "occurrence_reasoning": occurrence_reasoning(posture, direction),
        "_source_record_id": record_id,
        "_retrieval_url": resource_uri or retrieval_url,
        "_source_name": fjc_idb_source().name,
        "_access_method": access_method,
    }


class FJCIDBConnector:
    source = fjc_idb_source()

    def __init__(
        self,
        access_adapter: FJCIDBAdapter | None = None,
        fetch_json: Callable[[str], tuple[dict[str, Any], dict[str, str], str]] | None = None,
        *,
        token: str | None = None,
        join_adapter: DocketJoinAdapter | None = None,
    ) -> None:
        self.access_adapter = access_adapter or FJCIDBAdapter(fetch_json=fetch_json, token=token)
        # The docket join is not optional enrichment. An IDB row states that an
        # FCRA violation was found without stating which duty was breached, and
        # the docket's nature of suit is the only field separating a consumer
        # credit claim from an enforcement action filed under the same statute.
        # Without it an off-mechanism case can establish occurrence for a
        # mechanism it has nothing to do with.
        self.join_adapter = join_adapter or DocketJoinAdapter(token=self.access_adapter.token)

    def build_url(self, limit: int = 1) -> str:
        return self.access_adapter.build_url(limit)

    def retrieve(self, limit: int = 1) -> RetrievalResult:
        retrieved_at = utc_now()
        retrieval_url, records, errors, diagnostics = self.access_adapter.retrieve(limit)
        for record in records:
            record["_retrieved_at"] = retrieved_at
            join_idb_record(record, self.join_adapter)
        return RetrievalResult(
            self.source,
            retrieval_url,
            retrieved_at,
            records,
            errors,
            access_method=self.access_adapter.method_name,
            diagnostics=diagnostics,
            source_reliability=fjc_idb_reliability_assessment(
                self.access_adapter.method_name, retrieved_at
            ),
        )
