"""Deterministic evidence qualification and mechanism rules.

Generic vocabulary is not enough to establish an operational failure. Narrative evidence
must describe both a process and an alleged failure. In the absence of a public
narrative, only explicit taxonomy phrases that name a failed process can establish a
taxonomy-limited signal.

That rule is sector-neutral and stays here. The words it applies are not, and no longer
do: term lists and mechanism rules now come from `sectors/`, and every function takes a
pack defaulting to the registered sector. The module-level names below are kept as views
onto the default pack because callers and tests import them, but they are no longer the
only statement of the vocabulary.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import cycle: models.py imports contains_any
    from sectors.models import SectorPack


def _default_pack() -> "SectorPack":
    """Resolved on call, not at import: `sectors` imports this module."""

    from sectors import get

    return get()


def matched_terms(text: str, terms: list[str]) -> list[str]:
    """Return exact case-insensitive term matches without substring leakage."""

    return [
        term
        for term in terms
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE)
    ]


def contains_any(text: str, terms: list[str]) -> bool:
    return bool(matched_terms(text, terms))


def operational_assessment(
    parsed_fields: dict[str, object], pack: "SectorPack | None" = None
) -> tuple[bool, str, list[str]]:
    """Determine whether a record identifies an operational failure and why.

    The two-limb rule -- a narrative naming both a process and a failure, or an explicit
    taxonomy phrase that names a failed process -- is the engine's, and applies to any
    sector. Only the vocabulary changes.
    """

    pack = pack or _default_pack()
    narrative = str(parsed_fields.get("narrative") or "").strip()
    if narrative:
        process_matches = matched_terms(narrative, list(pack.process_terms))
        failure_matches = matched_terms(narrative, list(pack.failure_terms))
        if process_matches and failure_matches:
            return True, "consumer_narrative_process_and_failure", sorted(
                set(process_matches + failure_matches)
            )

    taxonomy = " ".join(
        str(parsed_fields.get(key) or "") for key in ("issue", "sub_issue")
    )
    taxonomy_matches = matched_terms(taxonomy, list(pack.taxonomy_phrases))
    if taxonomy_matches:
        return True, "explicit_cfpb_taxonomy_process_failure", taxonomy_matches

    return False, "operational_failure_not_established", []


def detect_mechanism(text: str, pack: "SectorPack | None" = None) -> str:
    """Classify text to one of the sector's mechanisms, or to its fallback.

    This was an if-ladder naming four credit-reporting mechanisms. The ordering and the
    conditions are unchanged -- they now live in the pack as declared rules, and this
    walks them. First match wins, exactly as the ladder's early returns did.
    """

    return (pack or _default_pack()).classify(text)


def default_mechanism(pack: "SectorPack | None" = None) -> str:
    """The sector's unclassified fallback.

    Never compare two records by this value. Two records that both failed to classify
    once matched each other on a shared fallback and produced a corroboration PASS from
    evidence that had corroborated nothing.
    """

    return (pack or _default_pack()).default_mechanism


def __getattr__(name: str) -> Any:
    """Module constants, resolved from the default pack at access time.

    Import-time resolution is impossible here -- `sectors` imports this module for
    `contains_any` -- and a stale copy taken at import would silently diverge from the
    pack if a caller ever switched sectors. These exist for the callers that predate
    packs; new code should take a pack.
    """

    views = {
        "DEFAULT_MECHANISM": lambda pack: pack.default_mechanism,
        "NARRATIVE_PROCESS_TERMS": lambda pack: list(pack.process_terms),
        "OPERATIONAL_TERMS": lambda pack: list(pack.process_terms),
        "NARRATIVE_FAILURE_TERMS": lambda pack: list(pack.failure_terms),
        "EXPLICIT_OPERATIONAL_TAXONOMY_PHRASES": lambda pack: list(pack.taxonomy_phrases),
        "SOFTWARE_ADDRESSABLE_TERMS": lambda pack: list(pack.software_addressable_terms),
    }
    if name in views:
        return views[name](_default_pack())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
