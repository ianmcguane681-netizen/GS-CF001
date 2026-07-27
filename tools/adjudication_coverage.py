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


def fetch_establishing_records(adapter: FJCIDBAdapter, limit: int) -> list[dict[str, Any]]:
    """Every FCRA case whose coded outcome went against the respondent on the merits."""

    collected: list[dict[str, Any]] = []
    url = adapter.build_url(min(limit, 100), judgment="1")
    while url and len(collected) < limit:
        try:
            payload, _headers, _status = adapter._fetch_json(url)  # noqa: SLF001 - same package
        except Exception as error:  # noqa: BLE001 - a partial pool is still usable
            # Pagination failing part-way is a smaller sample, not a lost run. The
            # caller assesses what was retrieved and the shortfall is visible in
            # the summary rather than silently changing the denominator.
            print(f"  pagination stopped early: {error}")
            break
        for row in payload.get("results") or []:
            if not cites_fcra(row.get("title"), row.get("section")):
                continue
            posture, direction = classify_fjc_disposition(row.get("disposition"), row.get("judgment"))
            if establishes_occurrence(posture, direction):
                collected.append({**row, "_posture": posture, "_direction": direction})
        url = payload.get("next")
        time.sleep(1.0)
    return collected[:limit]


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

    records = fetch_establishing_records(idb, args.limit)
    print(f"occurrence-establishing records retrieved: {len(records)}")

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
    summary = {
        "assessed": len(results),
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
