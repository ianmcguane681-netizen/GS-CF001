from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from core.models import Source


@dataclass(frozen=True)
class RetrievalResult:
    source: Source
    retrieval_url: str
    retrieved_at: str
    records: list[dict[str, Any]]
    errors: list[str]


class DiscoveryConnector(Protocol):
    source: Source

    def retrieve(self, limit: int = 1) -> RetrievalResult:
        ...

