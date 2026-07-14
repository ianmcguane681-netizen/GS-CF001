from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from core.models import AccessDiagnostic, Source, SourceReliabilityAssessment


@dataclass(frozen=True)
class RetrievalResult:
    source: Source
    retrieval_url: str
    retrieved_at: str
    records: list[dict[str, Any]]
    errors: list[str]
    access_method: str = ""
    diagnostics: list[AccessDiagnostic] | None = None
    source_reliability: SourceReliabilityAssessment | None = None


class DiscoveryConnector(Protocol):
    source: Source

    def retrieve(self, limit: int = 1) -> RetrievalResult:
        ...
