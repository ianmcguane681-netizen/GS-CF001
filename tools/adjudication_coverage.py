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

It costs that record *temporarily*. An earlier version wrote the rate limit down as
`join failed: HTTP 429` next to genuine absences, and the resume map then skipped the
row as already assessed -- so a busy API silently became a permanent statement about
what RECAP holds. Transient failures are now deferred rather than recorded: they are
retried on the next run, and no summary is written while any remain outstanding.

    python -m tools.adjudication_coverage --limit 67
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
from core.http_retry import TransientRetrievalError
from verification.rules import DEFAULT_MECHANISM, detect_mechanism

DEFAULT_OUTPUT = Path("analysis/adjudication_coverage.json")
DEFAULT_POOL_CACHE = Path("analysis/adjudication_pool.json")

# The pool is a fixed set: FCRA cases whose coded outcome went against the
# respondent. Re-walking it on every attempt was the reason every attempt was
# rate-limited before it began -- the expensive part ran first and repeatedly, and
# the cheap part never got a turn. It is enumerated once and cached.


def fetch_establishing_records(
    adapter: FJCIDBAdapter, limit: int, judgment: str = "1"
) -> tuple[list[dict[str, Any]], str]:
    """Every FCRA case whose coded outcome went against the respondent on the merits.

    Returns the records and, if pagination did not complete, why. The caller needs
    that: a walk that enumerated nothing has no denominator, and a summary written
    over it would read as authoritative while resting on no pool at all.
    """

    collected: list[dict[str, Any]] = []
    incomplete = ""
    url = adapter.build_url(min(limit, 20), judgment=judgment)
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
            # Every decided row is retained, not only those establishing occurrence.
            # Measuring archive coverage needs the defence side too: coverage rates
            # computed over confirmations alone would be a biased measurement of
            # bias, which is worse than not measuring it.
            collected.append({**row, "_posture": posture, "_direction": direction})
        url = payload.get("next")
        time.sleep(3.0)
    return collected[:limit], incomplete


def _resume_key(row: dict[str, Any]) -> str:
    """Identify an assessed record uniquely. Court first, because docket alone is not."""

    return f"{row.get('court') or '?'}/{row.get('docket') or '?'}"


# Rows written before transient failures were deferred rather than recorded. They
# have no structured marker -- the whole defect was that the outcome survived only as
# a sentence -- so repairing existing files means reading that sentence. Nothing
# written from here on can match: transient failures no longer produce a row at all,
# and this pattern is deliberately anchored to the wording the old code emitted.
_TRANSIENT_WORDING = re.compile(
    r"HTTP (?:429|502|503|504)\b|urlopen error|timed out|timeout", re.IGNORECASE
)


def _pool_key(record: dict[str, Any]) -> str:
    """The same identity as `_resume_key`, derived from a raw IDB row."""

    return _resume_key(
        {
            "court": court_id_from_district(record.get("district")),
            "docket": pacer_docket_number(record.get("office"), record.get("docket_number")),
        }
    )


def pool_fingerprint(records: list[dict[str, Any]]) -> str:
    """Identify the population a results file was measured against.

    A results file records *what was found*, never *what was searched*, so nothing in
    it distinguishes 67 plaintiff-win cases from 67 mixed-strata cases. Resuming one
    onto the other silently unions two populations, and the summary computes a
    coverage rate over a denominator that never existed. This is that missing field.
    """

    digest = hashlib.sha256()
    for key in sorted({_pool_key(record) for record in records}):
        digest.update(key.encode("utf-8") + b"\n")
    return digest.hexdigest()[:16]


def _resume_from(
    stored: dict[str, Any], pool_keys: set[str], fingerprint: str
) -> tuple[dict[str, Any], str]:
    """Decide whether an existing results file may be resumed against this pool.

    Returns the resumable rows and, if the file belongs to a different population,
    the reason it was refused. Refusing costs a re-walk; accepting wrongly produces a
    number that reads as a measurement and is not one.
    """

    rows = stored.get("records") or []
    if not rows:
        return {}, ""

    recorded = stored.get("pool_fingerprint")
    if recorded and recorded != fingerprint:
        return {}, (
            f"results file was measured against pool {recorded}, this run enumerated "
            f"{fingerprint}. Refusing to resume: the two are different populations and "
            f"combining them would produce a coverage rate over a denominator that was "
            f"never walked. Use a different --output."
        )
    if not recorded:
        # Written before the fingerprint existed. Containment is the available check:
        # if every stored row is in this pool, resuming adds to the same population.
        strays = sorted({_resume_key(row) for row in rows} - pool_keys)
        if strays:
            return {}, (
                f"results file has no recorded pool, and {len(strays)} of its "
                f"{len(rows)} row(s) are absent from the pool this run enumerated "
                f"(e.g. {', '.join(strays[:3])}). It was measured against a different "
                f"population. Refusing to resume; use a different --output."
            )

    done = {_resume_key(row): row for row in rows if not _was_transient_failure(row)}
    readmitted = len(rows) - len(done)
    print(f"resuming: {len(done)} record(s) already assessed")
    if readmitted:
        print(f"  {readmitted} previously recorded as failures were transient; retrying them")
    return done, ""


def _was_transient_failure(row: dict[str, Any]) -> bool:
    """Is this stored row a rate limit wearing an assessment's clothes?

    Such a row must be dropped from the resume map and attempted again. Keeping it
    counts "the client was throttled" as "RECAP does not hold this docket", which
    understates archive coverage by exactly the number of requests the API refused.
    """

    text = " ".join(str(row.get(field) or "") for field in ("stopped_at", "complaint_note"))
    return bool(_TRANSIENT_WORDING.search(text))


def assess(record: dict[str, Any], join: DocketJoinAdapter) -> dict[str, Any]:
    """Walk one record through every condition, recording where it stops.

    Raises `TransientRetrievalError` if any step could not be attempted. That is not
    a stopping point on the path -- it is the walk not happening -- and the caller
    must defer the record rather than store a row saying where it stopped.
    """

    docket_number = pacer_docket_number(record.get("office"), record.get("docket_number"))
    court_id = court_id_from_district(record.get("district"))
    result = {
        "docket": docket_number,
        "court": court_id,
        "defendant": record.get("defendant") or "",
        "posture": record["_posture"],
        "direction": record.get("_direction", ""),
        "origin": record.get("origin"),
        # Retained so district and filing-year grouping needs no second pass over
        # the API. The pool cache holds these already; dropping them here was why
        # the first sweep could not answer "coverage by year".
        "date_filed": record.get("date_filed") or "",
        "district": record.get("district") or "",
        "judgment": record.get("judgment"),
        "disposition": record.get("disposition"),
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
    parser.add_argument(
        "--judgment",
        default="1,2",
        help="FJC judgment codes to walk: 1 plaintiff, 2 defendant. Both by default, "
             "because coverage measured over confirmations alone is a biased measure of bias.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    stored_document: dict[str, Any] = {}
    if output.is_file():
        stored_document = json.loads(output.read_text(encoding="utf-8"))

    idb = FJCIDBAdapter()
    if not idb.token:
        print("COURTLISTENER_API_TOKEN is not set")
        return 1
    join = DocketJoinAdapter(token=idb.token)

    cache = Path(args.pool_cache)
    incomplete = ""
    records: list[dict[str, Any]] = []
    if cache.is_file():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        # A cache is only reusable for the strata that produced it. Reusing a
        # plaintiff-only pool for a judgment=1,2 run would report a coverage rate
        # over a population that was never walked, and the file gives no hint.
        cached_judgment = cached.get("judgment", "1")
        if cached_judgment != args.judgment:
            # This branch used to print and carry on, re-enumerating and then
            # overwriting the cache -- which destroyed the enumerated pool the
            # existing results were measured against. Detecting a mismatch and then
            # proceeding is not a guard.
            print(
                f"pool cache {cache} was built for judgment={cached_judgment!r}, this run "
                f"wants {args.judgment!r}. Refusing to overwrite it: pass --pool-cache "
                f"with a different path so both strata survive."
            )
            return 2
        records = cached["records"]
        print(f"pool from cache: {len(records)} decided record(s) [judgment={cached_judgment}]")
    if not records:
        records, incomplete = fetch_establishing_records(idb, args.limit, judgment=args.judgment)
        print(f"decided records retrieved: {len(records)} [judgment={args.judgment}]")
        if records and not incomplete:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(
                json.dumps({"enumerated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "judgment": args.judgment, "limit": args.limit,
                            "records": records}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"pool cached to {cache} [judgment={args.judgment}]")
    records = records[: args.limit]
    pool_keys = {_pool_key(record) for record in records}
    fingerprint = pool_fingerprint(records)

    done, resume_error = _resume_from(stored_document, pool_keys, fingerprint)
    if resume_error:
        print(resume_error)
        return 2

    results = list(done.values())
    deferred: list[dict[str, Any]] = []

    def _write(payload: dict[str, Any]) -> None:
        # The fingerprint goes on every write, including the refusals. A partial file
        # is the one most likely to be resumed, so it is the one that most needs to
        # say which population it belongs to.
        output.parent.mkdir(parents=True, exist_ok=True)
        document = {"pool_fingerprint": fingerprint, "pool_judgment": args.judgment, **payload}
        output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    for index, record in enumerate(records, start=1):
        key = _pool_key(record)
        if key in done:
            continue
        try:
            row = assess(record, join)
        except TransientRetrievalError as error:
            # Deliberately not appended to `results`, and deliberately not keyed into
            # `done`: the next run must attempt this record again. Writing it as an
            # assessment is the defect this guard exists for.
            deferred.append({"key": key, "reason": str(error)})
            _write({"records": results, "deferred": deferred})
            print(f"  [{index}/{len(records)}] {key} -> DEFERRED (will retry): {str(error)[:60]}")
            time.sleep(5.0)
            continue
        results.append(row)
        _write({"records": results, "deferred": deferred})
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
        _write(
            {
                "pool_incomplete": incomplete,
                "note": (
                    "No summary: the occurrence-establishing pool could not be "
                    "enumerated on this run, so the assessed records have no "
                    "denominator. Re-run to complete."
                ),
                "records": results,
                "deferred": deferred,
            }
        )
        print(f"\nPOOL NOT ENUMERATED: {incomplete}")
        print(f"{len(results)} record(s) assessed, but with no denominator. Re-run to complete.")
        return 2

    if deferred:
        # Same rule, applied to the numerator. A coverage rate computed while records
        # remain unattempted understates coverage by exactly the number the API
        # refused, and nothing in the file would say so. The measurement is not
        # finished, so it is not published.
        _write(
            {
                "note": (
                    f"No summary: {len(deferred)} record(s) could not be retrieved on this "
                    "run and were deferred rather than recorded. They are not absences, "
                    "so the coverage rate would be understated. Re-run to complete."
                ),
                "pool_size_enumerated": len(records),
                "records": results,
                "deferred": deferred,
            }
        )
        print(f"\nDEFERRED: {len(deferred)} record(s) could not be retrieved.")
        print(f"{len(results)} of {len(records)} assessed. No summary written. Re-run to complete.")
        return 2

    def _rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        with_text = sum(1 for r in rows if r.get("complaint_chars"))
        return {"assessed": len(rows), "with_complaint_text": with_text,
                "coverage": round(with_text / len(rows), 4) if rows else None}

    by_district: dict[str, Any] = {}
    for row in results:
        by_district.setdefault(row.get("court") or "unknown", []).append(row)
    by_year: dict[str, Any] = {}
    for row in results:
        by_year.setdefault((row.get("date_filed") or "")[:4] or "unknown", []).append(row)

    summary = {
        "assessed": len(results),
        "by_district": {k: _rate(v) for k, v in sorted(by_district.items())},
        "by_filing_year": {k: _rate(v) for k, v in sorted(by_year.items())},
        "pool_size_enumerated": len(records),
        "pool_incomplete": incomplete or None,
        "deferred": 0,
        "joined": sum(1 for r in results if r.get("joined")),
        "on_study_suit_nature": sum(1 for r in results if r.get("on_study_suit_nature")),
        "with_complaint_text": sum(1 for r in results if r.get("complaint_chars")),
        "reached_a_mechanism": len(reached),
        "mechanisms": sorted({r["mechanism"] for r in reached}),
    }
    _write({"summary": summary, "records": results, "deferred": deferred})
    print("\n" + json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
