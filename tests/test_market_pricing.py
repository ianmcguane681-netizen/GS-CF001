"""Published pricing, and the line it must not cross.

The lane exists to move PG-11 (existing solution maturity) and is structurally
barred from moving PG-12 or G4, because what a vendor charges and what a buyer
pays are different numbers. Being cheaper than a list price nobody actually pays
is not a strategy.

Most of these tests guard a refusal. A live probe of Credit Repair Cloud's pricing
page on 2026-07-27 found twenty distinct dollar figures on one page -- a $1 trial,
a $179 monthly plan, a $143.20 annual-discounted equivalent, and a $15,427
marketing earnings claim. No deterministic rule separates those, so the connector
records that pricing is published and refuses to say what it is.
"""
from __future__ import annotations

import pytest

from market.models import COMPETITIVE_MARKET_CLASS
from market.pricing import (
    PriceProvenance,
    PricingDisclosure,
    PricingTranscriptionError,
    classify_disclosure,
    market_disclosure_summary,
    observe_pricing_page,
    robots_allows,
    to_sv_competitor,
    transcribe_list_price,
)

STRUCTURED = """
<html><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Plan",
 "offers":{"@type":"Offer","price":"149.00","priceCurrency":"USD"}}
</script></html>
"""

# Condensed from the live Credit Repair Cloud page: a trial price, a monthly plan,
# an annual-discounted equivalent, and a marketing earnings claim.
UNSTRUCTURED = "<html><body>$1 trial then $179/mo. Pay annually: $143.20. Members earn $15,427.</body></html>"

GATED = "<html><body>Contact our sales team for a tailored quote.</body></html>"


def fetch(mapping):
    def _fetch(url):
        if url.endswith("robots.txt"):
            return mapping.get("robots", "User-agent: *\nDisallow:\n")
        return mapping["page"]

    return _fetch


# --- The refusal that is the point of the module ------------------------------


def test_a_page_full_of_figures_yields_no_price():
    disclosure, amounts, price = classify_disclosure(UNSTRUCTURED)

    assert disclosure == PricingDisclosure.PUBLISHED_UNSTRUCTURED
    assert amounts >= 4
    assert price == ""  # four candidate figures, none chosen


def test_a_price_is_read_only_from_structured_markup():
    disclosure, _amounts, price = classify_disclosure(STRUCTURED)

    assert disclosure == PricingDisclosure.PUBLISHED_STRUCTURED
    assert price == "149.00"


def test_a_gated_page_is_recorded_as_not_published():
    """Which is market information: it separates self-serve from enterprise sales."""
    disclosure, amounts, price = classify_disclosure(GATED)

    assert disclosure == PricingDisclosure.NOT_PUBLISHED
    assert (amounts, price) == (0, "")


def test_an_unstructured_observation_carries_no_figure_and_says_why():
    observation = observe_pricing_page(
        "Example", "https://example.invalid/pricing", fetch_text=fetch({"page": UNSTRUCTURED})
    )

    assert observation.list_price == ""
    assert observation.list_price_provenance == ""
    assert "human transcription" in observation.notes


# --- Publishers who refuse automated access are refused ------------------------


def test_robots_disallow_is_obeyed():
    blocked = "User-agent: *\nDisallow: /pricing\n"

    assert robots_allows("https://example.invalid/pricing", "/pricing", fetch_text=lambda _u: blocked) is False
    assert robots_allows("https://example.invalid/pricing", "/plans", fetch_text=lambda _u: blocked) is True


def test_a_disallowed_page_is_not_retrieved():
    observation = observe_pricing_page(
        "Example",
        "https://example.invalid/pricing",
        fetch_text=fetch({"robots": "User-agent: *\nDisallow: /pricing\n", "page": UNSTRUCTURED}),
    )

    assert observation.robots_permitted is False
    assert observation.disclosure == PricingDisclosure.NOT_RETRIEVED
    assert observation.content_hash == ""


def test_a_rule_for_another_agent_does_not_block_us():
    robots = "User-agent: BadBot\nDisallow: /\n\nUser-agent: *\nDisallow:\n"

    assert robots_allows("https://example.invalid/pricing", "/pricing", fetch_text=lambda _u: robots) is True


# --- Transcription is tied to the page it was read from -----------------------


def observed():
    return observe_pricing_page(
        "Example", "https://example.invalid/pricing", fetch_text=fetch({"page": UNSTRUCTURED})
    )


def test_a_human_may_transcribe_a_figure_against_the_recorded_hash():
    observation = observed()

    updated = transcribe_list_price(
        observation,
        list_price="179.00",
        unit="USD/month",
        transcribed_by="ian.mcguane",
        observed_content_hash=observation.content_hash,
    )

    assert updated.list_price == "179.00"
    assert updated.list_price_provenance == PriceProvenance.HUMAN_TRANSCRIBED
    assert updated.transcribed_by == "ian.mcguane"


def test_transcription_is_refused_when_the_page_has_changed():
    """Otherwise a figure is silently backdated onto evidence that no longer exists."""
    with pytest.raises(PricingTranscriptionError) as error:
        transcribe_list_price(
            observed(),
            list_price="179.00",
            unit="USD/month",
            transcribed_by="ian.mcguane",
            observed_content_hash="sha256:something-else",
        )

    assert error.value.code == "PRICING_CONTENT_CHANGED"


def test_a_figure_cannot_be_transcribed_against_a_page_that_never_resolved():
    """Found by running it: ScoreCEO returned 404 and "99 USD/month" was accepted.

    The guard denylisted NOT_PUBLISHED and missed NOT_RETRIEVED, and the hash check
    passed because a failed retrieval leaves an empty hash that matches an empty
    hash. It is an allowlist now.
    """
    import urllib.error

    def failing(url):
        if url.endswith("robots.txt"):
            return "User-agent: *\nDisallow:\n"
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    missing = observe_pricing_page("Gone", "https://gone.invalid/pricing", fetch_text=failing)
    assert missing.disclosure == PricingDisclosure.NOT_RETRIEVED
    assert missing.content_hash == ""

    with pytest.raises(PricingTranscriptionError) as error:
        transcribe_list_price(
            missing,
            list_price="99",
            unit="USD/month",
            transcribed_by="ian.mcguane",
            observed_content_hash=missing.content_hash,
        )

    assert error.value.code in {"PRICING_NOT_PUBLISHED", "PRICING_NO_CONTENT_HASH"}


def test_a_figure_cannot_be_transcribed_from_a_page_that_publishes_none():
    gated = observe_pricing_page(
        "Example", "https://example.invalid/pricing", fetch_text=fetch({"page": GATED})
    )

    with pytest.raises(PricingTranscriptionError) as error:
        transcribe_list_price(
            gated,
            list_price="179.00",
            unit="USD/month",
            transcribed_by="ian.mcguane",
            observed_content_hash=gated.content_hash,
        )

    assert error.value.code == "PRICING_NOT_PUBLISHED"


@pytest.mark.parametrize(
    ("price", "unit", "who"),
    [("", "USD/month", "ian"), ("179", "", "ian"), ("179", "USD/month", "")],
)
def test_a_transcription_needs_a_figure_a_unit_and_a_person(price, unit, who):
    with pytest.raises(PricingTranscriptionError) as error:
        transcribe_list_price(
            observed(),
            list_price=price,
            unit=unit,
            transcribed_by=who,
            observed_content_hash=observed().content_hash,
        )

    assert error.value.code == "PRICING_TRANSCRIPTION_INCOMPLETE"


# --- The line into the buyer gates --------------------------------------------


def test_pricing_evidence_never_links_a_buyer_gate():
    """A list price cannot establish what a buyer pays, and must not claim to."""
    competitor = to_sv_competitor(observed())

    assert competitor["linked_gates"] == ["G7_COMPETITIVE_VIABILITY"]
    assert "G4_BUYER_CREDIBILITY" not in competitor["linked_gates"]
    assert competitor["linked_categories"] == ["C8_MARKET_COMPETITION"]
    assert competitor["pricing_is_list_not_paid"] is True


def test_a_pricing_observation_is_not_a_competitive_assessment():
    """Empty rather than "not assessed": G7 refuses records that say nothing, and
    filling these would be the placeholder failure the board raised three times."""
    competitor = to_sv_competitor(observed())

    assert competitor["strengths"] == []
    assert competitor["weaknesses"] == []
    assert competitor["differentiation"] == ""


def test_pricing_observations_carry_no_source_family():
    """Matching MarketEvidence: this can never reach the proof gates."""
    assert "source_family" not in observed().to_dict()
    assert observed().evidence_class == COMPETITIVE_MARKET_CLASS


def test_the_limitations_state_that_list_is_not_paid():
    limitations = " ".join(observed().limitations).lower()

    assert "not what any buyer pays" in limitations
    assert "implementation" in limitations


# --- What the market discloses, without naming a figure -----------------------


def test_the_summary_describes_disclosure_not_price():
    observations = [
        observed(),
        observe_pricing_page("Gated", "https://gated.invalid/pricing", fetch_text=fetch({"page": GATED})),
    ]

    summary = market_disclosure_summary(observations)

    assert summary["vendors_observed"] == 2
    assert summary["publishing_pricing"] == 1
    assert summary["gating_pricing"] == 1
    assert summary["transcribed_figures"] == 0
    assert "does not establish what any buyer pays" in summary["interpretation"]
