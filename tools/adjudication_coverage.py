"""How many adjudicated findings can actually corroborate this study's mechanism?

PG-09 needs a conjunction, and each condition eliminates records:

    1. a merits judgment for the plaintiff        67 of 17,204 FCRA cases
    2. on a consumer credit case                  excludes enforcement actions
    3. an original proceeding                     removals open with a notice, not a complaint
    4. with complaint text in RECAP               coverage is contributed by users
    5. classifying to a mechanism another
       source family independently alleges

Sampling six records at a time cannot answer whether that conjunction exists, so
this walks the whole occurrence-establishing pool once and reports where records
fall out. The answer is useful in either direction: it either finds corroborating
adjudications, or it establishes that these sources cannot supply them, which is
a finding the review board can act on rather than a guess.

Progress is written after every record. A rate limit or a timeout costs one record,
not the run, and re-running resumes rather than starting again.

    python -m tools.adjudication_coverage --limit 67
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

from connectors.docket_join import (
    DocketJoinAdapter,
    court_id_from_district,
    fetch_complaint_text,
    is_consumer_credit_suit,
    pacer_docket_number,
)
from connectors.fjc_idb import FJCIDBAdapter, cites_fcra
from core.adjudication import classify_fjc_disposition, establishes_occurrence
from verification.rules import DEFAULT_MECHANISM, detect_mechanism

DEFAULT_OUTPUT = Path("analysis/adjudication_coverage.json")
DEFAULT_POOL_CACHE = Path("analysis/adjudication_pool.json")

# The pool is a fixed set: FCRA cases whose coded outcome went against the
# respondent. Re-walking it on every attempt was the reason every attempt was
# rate-limited before it began -- the expensive part ran first and repeatedly, and
# the cheap part never got a turn. It is enumerated once and cached.


def fetch_establishing_records(
    adapter: FJCIDBAdapter, limit: int
) -> tuple[list[dict[str, Any]], str]:
    """Every FCRA case whose coded outcome went against the respondent on the merits.

    Returns the records and, if pagination did not complete, why. The caller needs
    that: a walk that enumerated nothing has no denominator, and a summary written
    over it would read as authoritative while resting on no pool at all.
    """

    collected: list[dict[str, Any]] = []
    incomplete = ""
    url = adapter.build_url(min(limit, 20), judgment="1")
    while url and len(collected) < limit:
        try:
            payload, _headers, _status = adapter._fetch_json(url)  # noqa: SLF001 - same package
        except Exception as error:  # noqa: BLE001 - a partial pool is still usable
            # Pagination failing part-way is a smaller sample, not a lost run. The
            # caller assesses what was retrieved and the shortfall is visible in
            # the summary rather than silently changing the denominator.
            incomplete = f"pagination stopped early: {error}"
            print(f"  {incomplete}")
            break
        for row in payload.get("results") or []:
            if not cites_fcra(row.get("title"), row.get("section")):
                continue
            posture, direction = classify_fjc_disposition(row.get("disposition"), row.get("judgment"))
            if establishes_occurrence(posture, direction):
                collected.append({**row, "_posture": posture, "_direction": direction})
        url = payload.get("next")
        time.sleep(3.0)
    return collected[:limit], incomplete


def assess(record: dict[str, Any], join: DocketJoinAdapter) -> dict[str, Any]:
    """Walk one record through every condition, recording where it stops."""

    docket_number = pacer_docket_number(record.get("office"), record.get("docket_number"))
    court_id = court_id_from_district(record.get("district"))
    result = {
        "docket": docket_number,
        "court": court_id,
        "defendant": record.get("defendant") or "",
        "posture": record["_posture"],
        "origin": record.get("origin"),
        "joined": False,
        "on_study_suit_nature": False,
        "complaint_chars": 0,
        "mechanism": "",
        "stopped_at": "",
    }
    if not docket_number or not court_id:
        result["stopped_at"] = "no join key"
        return result

    joined = join.lookup(court_id, docket_number)
    result["joined"] = bool(joined.get("join_verified"))
    result["suit_nature"] = joined.get("joined_suit_nature", "")
    result["case_name"] = joined.get("joined_case_name", "")
    if not result["joined"]:
        result["stopped_at"] = f"join failed: {joined.get('join_note')}"
        return result

    result["on_study_suit_nature"] = is_consumer_credit_suit(joined.get("joined_suit_nature"))
    if not result["on_study_suit_nature"]:
        result["stopped_at"] = f"off-study suit nature: {joined.get('joined_suit_nature')!r}"
        return result

    time.sleep(0.5)
    text, note = fetch_complaint_text(joined.get("joined_docket_id", ""), record.get("origin"))
    result["complaint_chars"] = len(text)
    result["complaint_note"] = note
    if not text:
        result["stopped_at"] = note
        return result

    mechanism = detect_mechanism(text)
    result["mechanism"] = mechanism
    if mechanism == DEFAULT_MECHANISM:
        result["stopped_at"] = "complaint text did not classify to a mechanism"
        return result
    result["stopped_at"] = "reached mechanism"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure adjudicated corroboration coverage.")
    parser.add_argument("--limit", type=int, default=67)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pool-cache", default=str(DEFAULT_POOL_CACHE))
    args = parser.parse_args()

    output = Path(args.output)
    done: dict[str, Any] = {}
    if output.is_file():
        done = {row["docket"]: row for row in json.loads(output.read_text(encoding="utf-8"))["records"]}
        print(f"resuming: {len(done)} record(s) already assessed")

    idb = FJCIDBAdapter()
    if not idb.token:
        print("COURTLISTENER_API_TOKEN is not set")
        return 1
    join = DocketJoinAdapter(token=idb.token)

    cache = Path(args.pool_cache)
    incomplete = ""
    if cache.is_file():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        records = cached["records"][: args.limit]
        print(f"pool from cache: {len(records)} occurrence-establishing record(s)")
    else:
        records, incomplete = fetch_establishing_records(idb, args.limit)
        print(f"occurrence-establishing records retrieved: {len(records)}")
        if records and not incomplete:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(
                json.dumps({"enumerated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "records": records}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"pool cached to {cache}")

    results = list(done.values())
    for index, record in enumerate(records, start=1):
        docket = pacer_docket_number(record.get("office"), record.get("docket_number"))
        if docket in done:
            continue
        row = assess(record, join)
        results.append(row)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"records": results}, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"  [{index}/{len(records)}] {row['court']}/{row['docket']} "
            f"{(row['defendant'] or '')[:26]:<26} -> {row['stopped_at'][:52]}"
        )
        time.sleep(0.5)

    reached = [r for r in results if r.get("mechanism") and r["mechanism"] != DEFAULT_MECHANISM]
    if incomplete and not records:
        # The pool was never enumerated, so there is no denominator. Writing a
        # summary here would present a run that retrieved nothing as a finished
        # measurement -- the precise failure this repository keeps finding in its
        # own gates. The assessed records are kept; the claim is not made.
        output.write_text(
            json.dumps(
                {
                    "pool_incomplete": incomplete,
                    "note": (
                        "No summary: the occurrence-establishing pool could not be "
                        "enumerated on this run, so the assessed records have no "
                        "denominator. Re-run to complete."
                    ),
                    "records": results,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nPOOL NOT ENUMERATED: {incomplete}")
        print(f"{len(results)} record(s) assessed, but with no denominator. Re-run to complete.")
        return 2

    summary = {
        "assessed": len(results),
        "pool_size_enumerated": len(records),
        "pool_incomplete": incomplete or None,
        "joined": sum(1 for r in results if r.get("joined")),
        "on_study_suit_nature": sum(1 for r in results if r.get("on_study_suit_nature")),
        "with_complaint_text": sum(1 for r in results if r.get("complaint_chars")),
        "reached_a_mechanism": len(reached),
        "mechanisms": sorted({r["mechanism"] for r in reached}),
    }
    output.write_text(
        json.dumps({"summary": summary, "records": results}, indent=2) + "\n", encoding="utf-8"
    )
    print("\n" + json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
