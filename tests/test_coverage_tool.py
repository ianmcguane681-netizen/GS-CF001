"""The coverage sweep must not lose records, or measure bias with a biased sample.

Two defects sat in this tool, and both would have produced a confident wrong
number rather than an obvious failure.

The resume map was keyed on the PACER docket number alone. That number omits the
court, so `2:20-cv-00294` exists in many districts at once and every case after the
first sharing a number would have been skipped as already assessed. The 67-record
run happened not to collide -- verified, 67 distinct keys for 67 rows -- but a walk
across ninety districts would, and the loss would have looked like completion.

The pool cache recorded nothing about which judgment strata produced it, so a
plaintiff-only pool could be reused for a run meant to cover both sides, reporting
a coverage rate over a population that was never walked.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.adjudication_coverage import _resume_key


def test_the_same_docket_in_two_courts_is_two_records():
    """The latent bug. Docket numbers are unique within a court, not across them."""
    left = {"court": "caed", "docket": "2:20-cv-00294"}
    right = {"court": "gamd", "docket": "2:20-cv-00294"}

    assert _resume_key(left) != _resume_key(right)
    assert len({_resume_key(left), _resume_key(right)}) == 2


def test_a_missing_court_still_yields_a_distinct_key():
    """An unjoined record must not collide with every other unjoined record."""
    assert _resume_key({"docket": "1:20-cv-00001"}) != _resume_key({"docket": "1:20-cv-00002"})


def test_the_existing_sweep_had_no_collisions_under_the_new_key():
    """The published 67-record measurement stands: the fix is forward-looking."""
    path = Path("analysis/adjudication_coverage.json")
    if not path.is_file():  # pragma: no cover - only present after a live run
        return
    rows = json.loads(path.read_text(encoding="utf-8"))["records"]

    assert len({_resume_key(row) for row in rows}) == len(rows)


def test_the_pool_cache_records_its_strata():
    """Without this a plaintiff-only pool is reusable for a both-sides run."""
    path = Path("analysis/adjudication_pool.json")
    if not path.is_file():  # pragma: no cover
        return
    cached = json.loads(path.read_text(encoding="utf-8"))

    assert "records" in cached
    # Older caches predate the field; the tool treats absence as judgment="1",
    # which is what they were, so it re-enumerates for any other strata.
    assert cached.get("judgment", "1") in {"1", "2", "1,2"}


def test_defence_side_rows_survive_enumeration():
    """Coverage measured over confirmations alone is a biased measure of bias.

    The tool used to filter the pool through establishes_occurrence, which drops
    every judgment-for-defendant row. Those are the majority of decided cases and
    they carry exactly the same archive-coverage question.
    """
    import inspect

    from tools import adjudication_coverage

    source = inspect.getsource(adjudication_coverage.fetch_establishing_records)
    assert "if establishes_occurrence(posture, direction):" not in source
    assert "judgment: str" in source
