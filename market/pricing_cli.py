"""Observe incumbent pricing pages, and transcribe figures against what was seen.

    python -m market.pricing_cli observe --vendors market/vendors.json
    python -m market.pricing_cli transcribe --vendor "Credit Repair Cloud" \
        --price 179.00 --unit "USD/month" --by ian.mcguane
    python -m market.pricing_cli status

`observe` records what is verifiable: that the page resolved, its content hash,
and whether pricing is published at all. It does not record a price, because no
observed vendor publishes structured pricing markup and picking a figure out of a
page carrying a trial price, a monthly plan, an annual-discounted equivalent and a
marketing earnings claim is a guess.

`transcribe` is how a figure enters: a human reads the page and records what it
says, checked against the hash from the observation so the number is tied to the
page it was actually read from.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from market.pricing import (
    PricingObservation,
    PricingTranscriptionError,
    market_disclosure_summary,
    observe_pricing_page,
    to_sv_competitor,
    transcribe_list_price,
)

DEFAULT_LEDGER = Path("data/market_pricing.json")
DEFAULT_VENDORS = Path("market/vendors.json")


def _load(path: Path) -> list[PricingObservation]:
    if not path.is_file():
        return []
    return [
        PricingObservation(**{**row, "limitations": tuple(row.get("limitations", ()))})
        for row in json.loads(path.read_text(encoding="utf-8"))
    ]


def _save(path: Path, records: list[PricingObservation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([item.to_dict() for item in records], indent=2) + "\n", encoding="utf-8"
    )


def cmd_observe(args: argparse.Namespace) -> int:
    vendors = json.loads(Path(args.vendors).read_text(encoding="utf-8"))
    records = []
    for entry in vendors:
        observation = observe_pricing_page(entry["vendor"], entry["pricing_url"])
        records.append(observation)
        figure = observation.list_price or "-"
        print(
            f"  {observation.vendor:<26} {observation.http_status:<6} "
            f"{observation.disclosure:<24} figures={observation.currency_amounts_found:<3} price={figure}"
        )
    _save(Path(args.ledger), records)
    print(f"\nWritten to {args.ledger}")
    print("Next: market.pricing_cli status, then transcribe any published figure by hand.")
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    path = Path(args.ledger)
    records = _load(path)
    index = next(
        (position for position, item in enumerate(records) if item.vendor == args.vendor), None
    )
    if index is None:
        print(f"No observation for {args.vendor!r}. Run observe first.")
        return 1
    try:
        records[index] = transcribe_list_price(
            records[index],
            list_price=args.price,
            unit=args.unit,
            transcribed_by=args.by,
            observed_content_hash=args.hash or records[index].content_hash,
        )
    except PricingTranscriptionError as error:
        print(f"Refused [{error.code}]: {error}")
        return 1
    _save(path, records)
    print(f"Recorded {args.price} {args.unit} for {args.vendor}, transcribed by {args.by}")
    print("  This is a list price. It is not what any buyer pays.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    records = _load(Path(args.ledger))
    if not records:
        print("No pricing observed yet.")
        return 0
    for item in records:
        figure = f"{item.list_price} {item.list_price_unit}".strip() if item.list_price else "not transcribed"
        print(f"  {item.vendor:<26} {item.disclosure:<24} {figure}")
    print("\n" + json.dumps(market_disclosure_summary(records), indent=1))
    if args.export:
        target = Path(args.export)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps([to_sv_competitor(item) for item in records], indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nSV competitor records written to {target} (G7 only, PENDING_REVIEW)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market.pricing_cli")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = parser.add_subparsers(dest="command", required=True)

    observe = sub.add_parser("observe", help="Retrieve each vendor's pricing page")
    observe.add_argument("--vendors", default=str(DEFAULT_VENDORS))
    observe.set_defaults(func=cmd_observe)

    transcribe = sub.add_parser("transcribe", help="Record a figure a human read")
    transcribe.add_argument("--vendor", required=True)
    transcribe.add_argument("--price", required=True)
    transcribe.add_argument("--unit", required=True, help='e.g. "USD/month"')
    transcribe.add_argument("--by", required=True)
    transcribe.add_argument("--hash", default="", help="Content hash the figure was read from")
    transcribe.set_defaults(func=cmd_transcribe)

    status = sub.add_parser("status", help="What has been observed")
    status.add_argument("--export", help="Write SV Engine competitor records here")
    status.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
