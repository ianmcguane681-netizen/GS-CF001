"""A rate limit is a fact about the run, not about the world.

The coverage census walks every occurrence-establishing FCRA case and asks, for each
one, whether RECAP holds a complaint. Most answers are "no", and that "no" is the
measurement: it is how the study knows its adjudicated sample is archive-selected.

An exhausted 429 produced the same shape of answer. `join failed: HTTP 429` was
written into the records file beside `no RECAP docket matched the reconstructed
number`, and the resume map then skipped the row on the next run as already assessed.
Nine rows across two census files carried that -- a busy afternoon recorded as a
permanent statement about archive coverage, understating it with nothing in the file
to say so.

This is the sixth instance in this repository of a partial state presenting as a
complete one, so the fix is structural rather than a wider except clause: a failure
that could succeed later raises, and the caller defers the record instead of storing
one.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from connectors.docket_join import DocketJoinAdapter, join_idb_record
from core.http_retry import TransientRetrievalError, is_transient
from tools.adjudication_coverage import (
    _pool_key,
    _resume_from,
    _was_transient_failure,
    pool_fingerprint,
)


def raising(error):
    def _fetch(_url):
        raise error

    return _fetch


def http_error(code):
    return urllib.error.HTTPError("https://example.test", code, "err", {}, None)


class TestWhichFailuresCouldSucceedLater:
    def test_rate_limiting_and_gateway_errors_are_transient(self):
        for code in (429, 502, 503, 504):
            assert is_transient(http_error(code)) is True

    def test_a_real_answer_is_not_transient(self):
        """404 and 401 are answers. Retrying them wastes everyone's time and, worse,
        would let a genuine absence be deferred forever rather than recorded."""

        for code in (400, 401, 403, 404):
            assert is_transient(http_error(code)) is False

    def test_network_level_failures_are_transient(self):
        assert is_transient(TimeoutError("read timed out")) is True
        assert is_transient(ConnectionResetError(104, "Connection reset by peer")) is True
        assert is_transient(urllib.error.URLError("dns")) is True

    def test_a_programming_error_is_not_transient(self):
        """Retrying a bug just runs the bug again."""

        assert is_transient(ValueError("malformed JSON")) is False


class TestTheJoinRefusesToRecordWhatItDidNotLookUp:
    def test_a_rate_limited_lookup_raises(self):
        adapter = DocketJoinAdapter(fetch_json=raising(http_error(429)))

        with pytest.raises(TransientRetrievalError):
            adapter.lookup("gand", "1:19-cv-00679")

    def test_a_genuine_absence_is_still_a_recorded_absence(self):
        """The point is the contrast: this one *is* an observation and is kept."""

        adapter = DocketJoinAdapter(fetch_json=lambda _url: ({"results": []}, {}, "200"))

        outcome = adapter.lookup("laed", "2:17-cv-13000")

        assert outcome["join_verified"] is False
        assert outcome["join_retryable"] is False
        assert "no RECAP docket matched" in outcome["join_note"]

    def test_a_404_is_an_answer_and_is_recorded(self):
        adapter = DocketJoinAdapter(fetch_json=raising(http_error(404)))

        outcome = adapter.lookup("gand", "1:19-cv-00679")

        assert outcome["join_verified"] is False
        assert outcome["join_retryable"] is False

    def test_the_pipeline_marks_a_deferred_record_rather_than_dying(self):
        """A pipeline run must survive a busy API, but must not pretend it succeeded."""

        record = {"office": "1", "docket_number": "1900679", "district": "11", "origin": 1}

        joined = join_idb_record(record, DocketJoinAdapter(fetch_json=raising(http_error(429))))

        assert joined["join_verified"] is False
        assert joined["join_retryable"] is True
        assert "deferred" in joined["join_note"]


class TestRepairingFilesWrittenBeforeTheFix:
    def test_a_recorded_rate_limit_is_readmitted_for_retry(self):
        row = {"stopped_at": "join failed: docket lookup failed: HTTP 429"}

        assert _was_transient_failure(row) is True

    def test_a_recorded_connection_reset_is_readmitted(self):
        row = {"stopped_at": "join failed: docket lookup failed: <urlopen error [Errno 104]>"}

        assert _was_transient_failure(row) is True

    def test_a_genuine_absence_is_not_readmitted(self):
        """Re-walking these would cost hundreds of requests to learn nothing new."""

        for stopped_at in (
            "no document 1 text available in RECAP for this docket",
            "join failed: no RECAP docket matched the reconstructed number",
            "off-study suit nature: '890 Other Statutory Actions'",
            "origin 2 is not an original proceeding, so document 1 is not the complaint",
            "reached mechanism",
        ):
            assert _was_transient_failure({"stopped_at": stopped_at}) is False


class TestAResultsFileKnowsWhichPopulationItMeasured:
    """Found while repairing the rate-limit defect, and worse than it.

    The 67-record sweep was walked over the plaintiff-win strata. Its pool cache
    predated strata labelling, so a rerun defaulting to `judgment=1,2` read the cache
    as mismatched, re-enumerated a different 67 cases -- sharing only 7 with the
    original -- and appended their assessments to the same results file. The strata
    guard printed a warning and continued. A guard that detects a condition and
    proceeds anyway is not a guard.

    Nothing in a results file recorded what was searched, only what was found, so no
    later check could have caught it either.
    """

    def pool(self, dockets):
        """`district` arrives from the IDB as a CourtListener court URL, not a code."""

        return [
            {
                "district": f"https://www.courtlistener.com/api/rest/v4/courts/{court}/",
                "office": office,
                "docket_number": number,
            }
            for court, office, number in dockets
        ]

    def test_the_fingerprint_depends_on_the_population_not_its_order(self):
        one = self.pool([("gand", "1", "1900679"), ("nyed", "1", "1904805")])
        other = self.pool([("nyed", "1", "1904805"), ("gand", "1", "1900679")])

        assert pool_fingerprint(one) == pool_fingerprint(other)

    def test_a_different_population_gets_a_different_fingerprint(self):
        one = self.pool([("gand", "1", "1900679")])
        other = self.pool([("gand", "1", "1900680")])

        assert pool_fingerprint(one) != pool_fingerprint(other)

    def test_resuming_a_file_from_another_population_is_refused(self):
        pool = self.pool([("gand", "1", "1900679")])
        stored = {"pool_fingerprint": "0000deadbeef0000", "records": [{"court": "gand", "docket": "x"}]}

        done, error = _resume_from(stored, {_pool_key(r) for r in pool}, pool_fingerprint(pool))

        assert done == {}
        assert "different populations" in error

    def test_a_legacy_file_is_checked_by_containment(self):
        """Files written before the fingerprint existed still have to be caught."""

        pool = self.pool([("gand", "1", "1900679")])
        stored = {"records": [{"court": "cand", "docket": "3:14-cv-05200"}]}

        done, error = _resume_from(stored, {_pool_key(r) for r in pool}, pool_fingerprint(pool))

        assert done == {}
        assert "different population" in error

    def test_a_legacy_file_of_the_same_population_still_resumes(self):
        """Refusing everything would be safe and useless: the 67-record sweep must
        still be resumable, because re-walking it costs hundreds of API calls."""

        pool = self.pool([("gand", "1", "1900679")])
        stored = {"records": [{"court": "gand", "docket": "1:19-cv-00679", "stopped_at": "reached mechanism"}]}

        done, error = _resume_from(stored, {_pool_key(r) for r in pool}, pool_fingerprint(pool))

        assert error == ""
        assert list(done) == ["gand/1:19-cv-00679"]


class TestThePublishedCensusFiles:
    """The repaired files are checked in, so the repair is verifiable and not a claim."""

    @pytest.mark.parametrize(
        "path",
        ["analysis/adjudication_coverage.json", "analysis/adjudication_coverage_census.json"],
    )
    def test_no_stored_record_is_a_transient_failure(self, path):
        import pathlib

        stored = pathlib.Path(path)
        if not stored.is_file():  # pragma: no cover - census is regenerated, not required
            pytest.skip(f"{path} not present")
        records = json.loads(stored.read_text(encoding="utf-8")).get("records", [])
        poisoned = [r for r in records if _was_transient_failure(r)]

        assert poisoned == [], f"{len(poisoned)} row(s) record a transient failure as an assessment"
