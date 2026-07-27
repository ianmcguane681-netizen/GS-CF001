"""What incumbents publish about their pricing, and what that does not tell you.

PG-11 (existing solution maturity) and PG-12 (commercial relevance) have failed in
every run of the study. Published vendor pricing moves the first and must never be
allowed to move the second, because the two questions are different:

    what does a vendor charge?   published, retrievable, documentary
    what does a buyer pay?       negotiated, discounted, only obtainable from a person

Those numbers routinely differ by a factor of two or more once discount,
implementation and staff time are counted. A strategy of being cheaper than a list
price nobody actually pays is not a strategy, so this module is structurally barred
from supporting the buyer gates. It links to G7 and C8 only.

**What this module refuses to do is the point of it.** Five vendor pricing pages
were probed on 2026-07-27. Two publish figures openly, three gate them behind
contact-sales. Not one carries structured pricing markup -- no schema.org Offer,
no microdata -- so reading "the price" off a page means running a regex across
prose. A single pricing page carries a $1 trial, a $179 monthly plan, a $143.20
annual-discounted equivalent and a "$1000 saved" marketing claim, and no rule
distinguishes them reliably. Guessing here produces a number that looks
authoritative and is wrong, which is worse than having none.

So the connector records only what it can verify:

  * that the page resolved, and its HTTP status
  * the content hash at retrieval, so the observation is reproducible and any later
    change is detectable
  * whether the vendor publishes pricing publicly at all -- a presence question,
    which is deterministic, unlike a value question
  * how many distinct currency amounts appear, as a count and never as a price

A figure only ever enters this lane from structured markup, or from a human who
read the page and transcribed it against the recorded hash. Whether a vendor
publishes at all is itself useful: it separates self-serve markets from
enterprise-negotiated ones without anyone naming a number.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable

from core.ids import stable_hash, stable_id, utc_now
from market.models import COMPETITIVE_MARKET_CLASS

USER_AGENT = "GS-CF001/0.1 methodology proof (+market pricing lane)"
ACCESS_TIMEOUT_SECONDS = 30

# Currency amounts in the forms a pricing page actually uses. Used to count
# whether figures are present, never to decide which one is the price.
CURRENCY_PATTERN = re.compile(r"(?:[$£€]\s?\d[\d,]*(?:\.\d{2})?)|(?:\d[\d,]*(?:\.\d{2})?\s?(?:USD|GBP|EUR))")
JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
MICRODATA_PRICE_PATTERN = re.compile(r'itemprop=["\']price["\']', re.I)


class PricingDisclosure(StrEnum):
    """How a vendor discloses price, which is market information in itself."""

    PUBLISHED_STRUCTURED = "PUBLISHED_STRUCTURED"      # schema.org Offer; machine-readable
    PUBLISHED_UNSTRUCTURED = "PUBLISHED_UNSTRUCTURED"  # figures visible, needs human transcription
    NOT_PUBLISHED = "NOT_PUBLISHED"                    # gated behind contact-sales
    NOT_RETRIEVED = "NOT_RETRIEVED"                    # the page did not resolve


class PriceProvenance(StrEnum):
    """Where a recorded figure came from. Absent means no figure was recorded."""

    STRUCTURED_MARKUP = "STRUCTURED_MARKUP"
    HUMAN_TRANSCRIBED = "HUMAN_TRANSCRIBED"


@dataclass(frozen=True)
class PricingObservation:
    """One retrieval of one vendor's pricing page.

    `list_price` is empty unless it came from structured markup or a human, and it
    is a *list* price in either case. Nothing here records what anyone pays.
    """

    observation_id: str
    vendor: str
    pricing_url: str
    retrieved_at: str
    http_status: str
    disclosure: str
    content_hash: str
    currency_amounts_found: int
    robots_permitted: bool
    list_price: str = ""
    list_price_provenance: str = ""
    list_price_unit: str = ""
    transcribed_by: str = ""
    evidence_class: str = COMPETITIVE_MARKET_CLASS
    notes: str = ""
    limitations: tuple[str, ...] = ()
    # No source_family, matching MarketEvidence: this can never reach the proof
    # gates or the independent source family count.

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["limitations"] = list(self.limitations)
        return value


LIST_PRICE_LIMITATIONS = (
    "A published list price is not what any buyer pays after discount or negotiation.",
    "List price excludes implementation, migration and internal staff cost.",
    "A vendor may change or withdraw published pricing at any time.",
    "Absence of published pricing means the vendor gates it, not that it is free or unknown to buyers.",
    "Pricing observed for one plan tier does not describe the vendor's realised revenue per customer.",
)


def robots_allows(base_url: str, path: str, fetch_text: Callable[[str], str] | None = None) -> bool:
    """Whether robots.txt permits retrieving this path.

    A publisher refusing automated access is refusing it. The FTC legal library was
    dropped from this study for exactly that reason, and a vendor's pricing page
    gets the same treatment.
    """

    parsed = urllib.parse.urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        body = (fetch_text or _default_fetch_text)(robots_url)
    except Exception:
        # No robots.txt is permission by convention; an unreachable one is not a
        # licence to assume, but refusing on a transient failure would be wrong.
        return True

    applies = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            applies = value == "*"
        elif field_name == "disallow" and applies and value:
            if path.startswith(value.rstrip("*")):
                return False
    return True


def classify_disclosure(html: str) -> tuple[str, int, str]:
    """Determine how pricing is disclosed. Presence, never value.

    Returns the disclosure mode, how many distinct currency amounts appear, and any
    structured price found. The count is diagnostic: it says figures are on the
    page, not what they mean.
    """

    structured = _structured_price(html)
    amounts = {match.group(0).strip() for match in CURRENCY_PATTERN.finditer(html)}
    if structured:
        return PricingDisclosure.PUBLISHED_STRUCTURED, len(amounts), structured
    if amounts or MICRODATA_PRICE_PATTERN.search(html):
        return PricingDisclosure.PUBLISHED_UNSTRUCTURED, len(amounts), ""
    return PricingDisclosure.NOT_PUBLISHED, 0, ""


def _structured_price(html: str) -> str:
    """Read a price from schema.org markup only. Never from prose."""

    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "Offer" in str(node.get("@type", "")):
                for key in ("price", "lowPrice"):
                    if node.get(key) not in (None, ""):
                        found.append(str(node[key]))
                        return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for block in JSON_LD_PATTERN.findall(html):
        try:
            walk(json.loads(block))
        except (ValueError, TypeError):
            continue
    return found[0] if found else ""


def _default_fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=ACCESS_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="ignore")


def observe_pricing_page(
    vendor: str,
    pricing_url: str,
    *,
    fetch_text: Callable[[str], str] | None = None,
    check_robots: bool = True,
) -> PricingObservation:
    """Retrieve one vendor's pricing page and record only what is verifiable."""

    fetch = fetch_text or _default_fetch_text
    retrieved_at = utc_now()
    path = urllib.parse.urlparse(pricing_url).path or "/"

    permitted = robots_allows(pricing_url, path, fetch_text=fetch) if check_robots else True
    if not permitted:
        return _observation(
            vendor,
            pricing_url,
            retrieved_at,
            http_status="not_attempted",
            disclosure=PricingDisclosure.NOT_RETRIEVED,
            content_hash="",
            amounts=0,
            robots_permitted=False,
            notes="robots.txt disallows this path; not retrieved.",
        )

    try:
        html = fetch(pricing_url)
    except urllib.error.HTTPError as error:
        return _observation(
            vendor,
            pricing_url,
            retrieved_at,
            http_status=str(error.code),
            disclosure=PricingDisclosure.NOT_RETRIEVED,
            content_hash="",
            amounts=0,
            robots_permitted=True,
            notes=f"Pricing page did not resolve: HTTP {error.code}.",
        )
    except Exception as error:  # noqa: BLE001 - recorded, never swallowed
        return _observation(
            vendor,
            pricing_url,
            retrieved_at,
            http_status="error",
            disclosure=PricingDisclosure.NOT_RETRIEVED,
            content_hash="",
            amounts=0,
            robots_permitted=True,
            notes=f"Pricing page retrieval failed: {error}.",
        )

    disclosure, amounts, structured_price = classify_disclosure(html)
    return _observation(
        vendor,
        pricing_url,
        retrieved_at,
        http_status="200",
        disclosure=disclosure,
        content_hash=stable_hash(html),
        amounts=amounts,
        robots_permitted=True,
        list_price=structured_price,
        list_price_provenance=PriceProvenance.STRUCTURED_MARKUP if structured_price else "",
        notes=(
            "Figures are present but not machine-readable; a price requires human "
            "transcription against the recorded content hash."
            if disclosure == PricingDisclosure.PUBLISHED_UNSTRUCTURED
            else ""
        ),
    )


def _observation(
    vendor: str,
    pricing_url: str,
    retrieved_at: str,
    *,
    http_status: str,
    disclosure: str,
    content_hash: str,
    amounts: int,
    robots_permitted: bool,
    list_price: str = "",
    list_price_provenance: str = "",
    notes: str = "",
) -> PricingObservation:
    return PricingObservation(
        observation_id=stable_id(
            "PRC", {"vendor": vendor, "url": pricing_url, "at": retrieved_at, "hash": content_hash}
        ),
        vendor=vendor,
        pricing_url=pricing_url,
        retrieved_at=retrieved_at,
        http_status=http_status,
        disclosure=str(disclosure),
        content_hash=content_hash,
        currency_amounts_found=amounts,
        robots_permitted=robots_permitted,
        list_price=list_price,
        list_price_provenance=str(list_price_provenance) if list_price_provenance else "",
        notes=notes,
        limitations=LIST_PRICE_LIMITATIONS,
    )


class PricingTranscriptionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def transcribe_list_price(
    observation: PricingObservation,
    *,
    list_price: str,
    unit: str,
    transcribed_by: str,
    observed_content_hash: str,
) -> PricingObservation:
    """Attach a human-read figure to an observation, tied to the page it was read from.

    The hash must match the retrieval. If the page changed between retrieval and
    transcription the figure describes a page that no longer exists, and attaching
    it would silently backdate a number onto the wrong evidence.
    """

    if not str(list_price).strip() or not str(unit).strip() or not str(transcribed_by).strip():
        raise PricingTranscriptionError(
            "PRICING_TRANSCRIPTION_INCOMPLETE",
            "A transcribed price needs a figure, a unit, and the person who read it",
        )
    # An allowlist, because the first version of this denylisted NOT_PUBLISHED and
    # silently accepted a figure for a page that returned 404: the vendor's page
    # never resolved, and "99 USD/month" was recorded against it. A denylist misses
    # every state nobody thought of; an allowlist cannot.
    if observation.disclosure not in {
        PricingDisclosure.PUBLISHED_STRUCTURED,
        PricingDisclosure.PUBLISHED_UNSTRUCTURED,
    }:
        raise PricingTranscriptionError(
            "PRICING_NOT_PUBLISHED",
            f"No published pricing page was observed for this vendor ({observation.disclosure}); "
            "a figure cannot have been read from it",
        )
    # A failed retrieval leaves the hash empty, and an empty hash matches an empty
    # hash -- so the tie to a specific page would hold only when there was a page.
    if not observation.content_hash:
        raise PricingTranscriptionError(
            "PRICING_NO_CONTENT_HASH",
            "The observation carries no content hash, so a figure cannot be tied to what was seen",
        )
    if observed_content_hash != observation.content_hash:
        raise PricingTranscriptionError(
            "PRICING_CONTENT_CHANGED",
            "The page has changed since retrieval; re-observe before transcribing",
        )
    return PricingObservation(
        **{
            **observation.to_dict(),
            "limitations": observation.limitations,
            "list_price": list_price,
            "list_price_unit": unit,
            "list_price_provenance": str(PriceProvenance.HUMAN_TRANSCRIBED),
            "transcribed_by": transcribed_by,
        }
    )


def to_sv_competitor(observation: PricingObservation) -> dict[str, Any]:
    """Emit in the SV Engine's competitor shape for G7 and C8 only.

    Strengths and weaknesses are left empty rather than filled with a placeholder:
    identifying an incumbent is not assessing one, and G7 refuses records whose
    comparative fields say nothing. A pricing observation is not a competitive
    assessment and must not be dressed as one.
    """

    published = observation.disclosure in {
        PricingDisclosure.PUBLISHED_STRUCTURED,
        PricingDisclosure.PUBLISHED_UNSTRUCTURED,
    }
    pricing = (
        f"{observation.list_price} {observation.list_price_unit}".strip()
        if observation.list_price
        else ("published, not transcribed" if published else "not published by the vendor")
    )
    return {
        "competitor_id": f"PRC-{observation.vendor.upper().replace(' ', '-')}",
        "name": observation.vendor,
        "alternative_type": "incumbent dispute-management software vendor",
        "strengths": [],
        "weaknesses": [],
        "pricing": pricing,
        "pricing_is_list_not_paid": True,
        "switching_cost": "",
        "differentiation": "",
        "evidence_ids": [observation.observation_id],
        "source_locator": observation.pricing_url,
        "content_hash": observation.content_hash,
        "retrieval_timestamp": observation.retrieved_at,
        "linked_categories": ["C8_MARKET_COMPETITION"],
        # Never G4 or the buyer gates. A list price cannot establish what a buyer
        # pays, and this lane must not be able to claim it does.
        "linked_gates": ["G7_COMPETITIVE_VIABILITY"],
        "review_state": "PENDING_REVIEW",
        "limitations": list(observation.limitations),
    }


def market_disclosure_summary(observations: list[PricingObservation]) -> dict[str, Any]:
    """How the market prices itself, without naming a single figure.

    Whether vendors publish at all separates a self-serve market from an
    enterprise-negotiated one, and that is knowable even when every price is not.
    """

    counts: dict[str, int] = {}
    for item in observations:
        counts[item.disclosure] = counts.get(item.disclosure, 0) + 1
    retrieved = [item for item in observations if item.http_status == "200"]
    published = [
        item
        for item in retrieved
        if item.disclosure
        in {PricingDisclosure.PUBLISHED_STRUCTURED, PricingDisclosure.PUBLISHED_UNSTRUCTURED}
    ]
    return {
        "vendors_observed": len(observations),
        "pages_retrieved": len(retrieved),
        "publishing_pricing": len(published),
        "gating_pricing": len(retrieved) - len(published),
        "by_disclosure": counts,
        "transcribed_figures": sum(1 for item in observations if item.list_price),
        "interpretation": (
            "Published pricing establishes what vendors charge. It does not establish "
            "what any buyer pays, and cannot support the buyer gates."
        ),
    }
