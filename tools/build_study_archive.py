"""build_study_archive.py — Reusable study-archive generator.

Usage
-----
# Archive the most-recent run recorded in the run index:
    python -m tools.build_study_archive --latest

# Archive a specific run by run_id:
    python -m tools.build_study_archive --run-id RUN-ABEC4DE8FEE1

# Override the default run-index and archive-root locations:
    python -m tools.build_study_archive --latest \
        --run-index data/exports/run_index.json \
        --archive-root study_archives

What it does
------------
1. Looks up the requested run in the run index (data/exports/run_index.json by
   default) to obtain every artifact path and the run's metadata.
2. Creates study_archives/{study_id}_{run_id}_{timestamp}/ — refuses to
   continue if that directory already exists, so no archive is ever silently
   overwritten.
3. Copies artifact files into the archive, applying narrative redaction (see
   below) to any file that may contain free-text consumer data.
4. Verifies each copied file's checksum against the value recorded in the run
   manifest at the time the pipeline produced the file. Reports any mismatch
   as a hard error.
5. Writes a machine-readable metadata file (archive_metadata.json) with the
   full run record, verdict, Evidence Ceiling, source access method, and a
   list of every file in the archive with its checksum.
6. Writes a human-readable README.md documenting the run, provenance, archive
   contents, redaction policy, and instructions for independent verification.
7. Writes checksums.txt (sha256) over every file in the archive, in the same
   format produced by the manual proof_bundle/ process, so `sha256sum -c` works
   out of the box.

Redaction policy
----------------
Free-text consumer narrative fields are replaced with the literal string
  "[REDACTED: free-text consumer narrative — not preserved in archive]"
in the following artifact types:
  - raw records (normalised_candidates / cfpb_credit_reporting_raw):
      top-level field  "complaint_what_happened"
      nested field     "raw_record" -> "complaint_what_happened"
      nested field     "parsed_fields" -> "narrative"
  - report_json: same fields wherever they appear, recursively.

Structured provenance fields (complaint ID, product, issue, company, dates,
sub-product, sub-issue, state, zip, tags, submission channel, company response)
are preserved unmodified.

The live data directory (data/) remains gitignored. This tool copies only the
selected run's artifacts into study_archives/, which is git-tracked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ids import stable_hash as _core_stable_hash

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REDACTION_MARKER = "[REDACTED: free-text consumer narrative — not preserved in archive]"

# Fields that carry uncontrolled free-text consumer narrative. These are
# redacted wherever they appear in any of the artifact types that may contain
# them. Structural / provenance fields are never touched.
NARRATIVE_FIELDS = {"complaint_what_happened", "narrative"}

# Artifact keys (as stored in the run index artifact_paths dict) that may
# contain consumer narrative and therefore need redaction before archiving.
REDACT_ARTIFACT_KEYS = {
    "raw",                    # cfpb_credit_reporting_raw_*.json
    "normalised_candidates",  # normalised_candidates_*.json
    "report_json",            # gs_cf001_c_report_*.json (machine-readable)
}

# Artifact keys whose content is safe to copy verbatim (no consumer narrative
# by construction). All other artifact keys fall into this set implicitly.
VERBATIM_ARTIFACT_KEYS = {
    "access_diagnostics",
    "source_reliability",
    "analysis_artifacts",
    "verification_artifacts",
    "proof_gate_results",
    "audit_trail",
    "findings",
    "opportunities",
    "mechanism_classifications",
    "odr_json",
    "odr_markdown",
    "processed",
    "report_markdown",
    "run_manifest",
}

# Default filesystem locations — can be overridden via CLI args or the
# Python API (archive_run / build_archive_for_run).
DEFAULT_RUN_INDEX = Path("data/exports/run_index.json")
DEFAULT_ARCHIVE_ROOT = Path("study_archives")


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------

def _redact_value(value: Any) -> Any:
    """Return the redaction marker if value is a non-empty string; otherwise
    return the value unchanged (empty strings, None, and non-string types are
    left as-is so the structure is preserved for provenance verification)."""
    if isinstance(value, str) and value.strip():
        return REDACTION_MARKER
    return value


def _redact_record(record: Any) -> Any:
    """Recursively walk a JSON-deserialisable value and replace any dict value
    whose key is in NARRATIVE_FIELDS with the redaction marker."""
    if isinstance(record, dict):
        return {
            k: (_redact_value(v) if k in NARRATIVE_FIELDS else _redact_record(v))
            for k, v in record.items()
        }
    if isinstance(record, list):
        return [_redact_record(item) for item in record]
    return record


def redact_artifact(data: Any) -> Any:
    """Top-level redaction entry point. Accepts any JSON-deserialisable
    structure and returns a new structure with all narrative fields replaced."""
    return _redact_record(data)


# ---------------------------------------------------------------------------
# Checksum helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """SHA-256 hex digest of *path* (the already-written archive copy)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash_text(text: str) -> str:
    """Hash a file's text content using the same algorithm as core.ids.stable_hash.

    core.ids.stable_hash JSON-serialises its payload before hashing, so
    passing a plain string wraps it in quotes first. This function replicates
    that behaviour exactly so archive checksum verification agrees with the
    checksums recorded by build_run_manifest / file_checksum at pipeline time.
    """
    return _core_stable_hash(text)


# ---------------------------------------------------------------------------
# Run-index lookup
# ---------------------------------------------------------------------------

def _load_run_index(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Run index not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Run index is not valid JSON: {path}") from exc
    if not isinstance(data, list):
        raise ValueError(f"Run index must be a JSON list: {path}")
    return data


def find_run_entry(run_index_path: Path, run_id: str | None = None, latest: bool = False) -> dict[str, Any]:
    """Return one run-index entry, either by run_id or the most-recent entry.

    Raises ValueError for ambiguous / missing entries.
    """
    entries = _load_run_index(run_index_path)
    if not entries:
        raise ValueError("Run index is empty — run the pipeline at least once before archiving.")
    if latest and run_id:
        raise ValueError("Specify either --latest or --run-id, not both.")
    if not latest and not run_id:
        raise ValueError("Specify either --latest or --run-id.")
    if latest:
        return entries[-1]
    matches = [e for e in entries if e.get("run_id") == run_id]
    if not matches:
        raise ValueError(f"No run with run_id={run_id!r} found in {run_index_path}")
    if len(matches) > 1:
        raise ValueError(f"Multiple entries with run_id={run_id!r} in {run_index_path} — index is corrupt.")
    return matches[0]


# ---------------------------------------------------------------------------
# Core archive builder
# ---------------------------------------------------------------------------

def build_archive(
    run_entry: dict[str, Any],
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    *,
    test_results_path: Path | None = None,
) -> Path:
    """Build a sanitised, git-committable archive for *run_entry*.

    Parameters
    ----------
    run_entry:
        One entry from the run index (as returned by find_run_entry).
    archive_root:
        Parent directory under which the archive subdirectory is created.
        Defaults to study_archives/ (git-tracked, not gitignored).
    test_results_path:
        If supplied, the file at this path is copied verbatim into the archive
        as test_results.txt (for milestone runs that capture test output).

    Returns
    -------
    Path to the new archive directory.

    Raises
    ------
    FileExistsError:
        If the target archive directory already exists — never overwrites.
    FileNotFoundError:
        If a required artifact file is missing from the workspace.
    ValueError:
        If a checksum mismatch is detected after copying.
    """
    run_id = run_entry["run_id"]
    study_id = run_entry["study_id"]
    stamp = run_entry["timestamp"]
    artifact_paths = run_entry.get("artifact_paths", {})
    artifact_checksums = run_entry.get("artifact_checksums", {})

    # ---- 1. Resolve archive directory -------------------------------------
    archive_dir_name = f"{study_id}_{run_id}_{stamp}"
    archive_dir = archive_root / archive_dir_name
    if archive_dir.exists():
        raise FileExistsError(
            f"Archive directory already exists: {archive_dir}\n"
            "Delete it manually if you intend to regenerate it."
        )
    archive_dir.mkdir(parents=True)

    # ---- 2. Copy / redact artifacts ---------------------------------------
    archive_checksums: dict[str, str] = {}  # filename -> sha256 of archive copy

    def _verify_source_checksum(key: str, src_path_str: str, raw_text: str) -> None:
        """Raise ValueError immediately if *raw_text* does not match the stored
        checksum. Called BEFORE any JSON parsing so that a tampered or corrupt
        file always surfaces as 'Checksum mismatch', not a JSONDecodeError."""
        expected = artifact_checksums.get(src_path_str)
        if not expected:
            return
        actual = stable_hash_text(raw_text)
        if actual != expected:
            shutil.rmtree(archive_dir)  # remove the partial archive
            raise ValueError(
                f"Checksum mismatch — artifact '{key}' has been modified since the "
                f"pipeline produced it. The archive has NOT been written.\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}\n"
                f"  path:     {src_path_str}"
            )

    def _copy_artifact(key: str, dest_name: str, *, redact: bool) -> str | None:
        """Copy one artifact into the archive. Returns the dest filename or None
        if the artifact path is not in the run entry (tolerated as optional)."""
        src_path_str = artifact_paths.get(key)
        if not src_path_str:
            return None
        src = Path(src_path_str)
        if not src.exists():
            raise FileNotFoundError(
                f"Artifact '{key}' recorded in run index does not exist on disk: {src}\n"
                "Has the data/ directory been cleared since this run was executed?"
            )

        raw_text = src.read_text(encoding="utf-8")

        # Verify checksum BEFORE parsing — tampered content raises ValueError
        # ("Checksum mismatch …") rather than a downstream JSONDecodeError.
        _verify_source_checksum(key, src_path_str, raw_text)

        dest = archive_dir / dest_name
        if redact:
            data = json.loads(raw_text)
            redacted = redact_artifact(data)
            dest.write_text(
                json.dumps(redacted, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        else:
            dest.write_text(raw_text, encoding="utf-8")

        archive_checksums[dest_name] = sha256_file(dest)
        return dest_name

    # Raw records — redact narrative.
    _copy_artifact("raw", "raw_records_redacted.json", redact=True)
    # Normalised candidates — redact narrative.
    _copy_artifact("normalised_candidates", "normalised_candidates_redacted.json", redact=True)
    # Report JSON — redact narrative.
    _copy_artifact("report_json", "report.json", redact=True)
    # All verbatim artifacts.
    _copy_artifact("run_manifest", "run_manifest.json", redact=False)
    _copy_artifact("access_diagnostics", "access_diagnostics.json", redact=False)
    _copy_artifact("source_reliability", "source_reliability_assessment.json", redact=False)
    _copy_artifact("verification_artifacts", "verification_artifacts.json", redact=False)
    _copy_artifact("proof_gate_results", "proof_gate_results.json", redact=False)
    _copy_artifact("audit_trail", "audit_trail.json", redact=False)
    _copy_artifact("findings", "findings.json", redact=False)
    _copy_artifact("opportunities", "opportunities.json", redact=False)
    _copy_artifact("mechanism_classifications", "mechanism_classifications.json", redact=False)
    _copy_artifact("odr_json", "odr.json", redact=False)
    _copy_artifact("odr_markdown", "odr.md", redact=False)
    _copy_artifact("report_markdown", "report.md", redact=False)

    # ---- 3. Optional test results -----------------------------------------
    if test_results_path and Path(test_results_path).exists():
        dest = archive_dir / "test_results.txt"
        dest.write_text(Path(test_results_path).read_text(encoding="utf-8"), encoding="utf-8")
        archive_checksums["test_results.txt"] = sha256_file(dest)

    # ---- 4. Machine-readable archive metadata -----------------------------
    metadata: dict[str, Any] = {
        "archive_generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "study_id": study_id,
        "run_timestamp": stamp,
        "verdict": run_entry.get("verdict"),
        "evidence_ceiling": run_entry.get("evidence_ceiling"),
        "source_access_method": run_entry.get("source_access_method"),
        "archive_files": {fname: cksum for fname, cksum in archive_checksums.items()},
        "source_artifact_paths": artifact_paths,
        "redaction_policy": {
            "redacted_fields": sorted(NARRATIVE_FIELDS),
            "redacted_artifact_keys": sorted(REDACT_ARTIFACT_KEYS),
            "redaction_marker": REDACTION_MARKER,
        },
    }
    meta_dest = archive_dir / "archive_metadata.json"
    meta_dest.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    archive_checksums["archive_metadata.json"] = sha256_file(meta_dest)

    # ---- 5. README.md -----------------------------------------------------
    readme_lines = _build_readme(run_entry, archive_checksums)
    readme_dest = archive_dir / "README.md"
    readme_dest.write_text("\n".join(readme_lines), encoding="utf-8")
    archive_checksums["README.md"] = sha256_file(readme_dest)

    # ---- 6. checksums.txt (sha256sum-compatible) --------------------------
    checksum_lines = [
        f"{cksum}  {fname}"
        for fname, cksum in sorted(archive_checksums.items())
    ]
    checksum_lines.append("")  # trailing newline
    checksums_dest = archive_dir / "checksums.txt"
    checksums_dest.write_text("\n".join(checksum_lines), encoding="utf-8")

    return archive_dir


def _build_readme(run_entry: dict[str, Any], archive_checksums: dict[str, str]) -> list[str]:
    """Return lines for the archive README.md."""
    run_id = run_entry["run_id"]
    study_id = run_entry["study_id"]
    stamp = run_entry["timestamp"]
    verdict = run_entry.get("verdict", "unknown")
    evidence_ceiling = run_entry.get("evidence_ceiling", "unknown")
    source_access_method = run_entry.get("source_access_method", "unknown")

    # Derive human-readable timestamp from stamp string
    try:
        # stamp is like 20260714T232733123456Z — parse and reformat
        dt = datetime.strptime(stamp, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        human_ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        human_ts = stamp

    files = {
        "run_manifest.json": "Run ID, code commit hash, methodology versions, retrieval timestamps, input record IDs, artifact checksums, final verdict. No personal data.",
        "access_diagnostics.json": "Request/response metadata (endpoint, method, headers, status, interpretation). No personal data.",
        "source_reliability_assessment.json": "CFPB source-reliability record: publisher, authority level, limitations, verification constraints. No personal data.",
        "raw_records_redacted.json": "Raw CFPB records as retrieved. Free-text narrative (complaint_what_happened) replaced by redaction marker; all structured provenance fields preserved.",
        "normalised_candidates_redacted.json": "Normalised EvidenceCandidate records. Same narrative redaction applied to raw_record.complaint_what_happened and parsed_fields.narrative.",
        "verification_artifacts.json": "Deterministic verification output per candidate. No consumer narrative by construction.",
        "proof_gate_results.json": "All Proof Gate results: status, threshold, observed value, confidence, missing evidence, ceiling constraint flag.",
        "audit_trail.json": "State transitions for each candidate through the pipeline stages.",
        "findings.json": "Structured findings generated from verified evidence.",
        "opportunities.json": "Opportunity assessments derived from findings.",
        "report.json": "Machine-readable verdict report. Narrative fields redacted.",
        "report.md": "Full human-readable Markdown verdict report.",
        "archive_metadata.json": "Archive provenance: generated timestamp, run record, file checksums, redaction policy.",
        "checksums.txt": "SHA-256 checksums of every file in this archive.",
        "test_results.txt": "pytest output captured immediately before this run (if included).",
    }

    lines: list[str] = []
    lines.append(f"# {study_id} Study Archive — {run_id}")
    lines.append("")
    lines.append(f"Sanitised, independently-reviewable archive of one live {study_id} pipeline run.")
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Run ID | `{run_id}` |")
    lines.append(f"| Study ID | `{study_id}` |")
    lines.append(f"| Run timestamp | `{human_ts}` |")
    lines.append(f"| Verdict | **{verdict}** |")
    lines.append(f"| Evidence Ceiling | **{evidence_ceiling}** |")
    lines.append(f"| Source access method | `{source_access_method}` |")
    lines.append("")
    lines.append("## Contents")
    lines.append("")
    lines.append("| File | Contents |")
    lines.append("|---|---|")
    for fname, desc in files.items():
        if fname in archive_checksums:
            lines.append(f"| `{fname}` | {desc} |")
    lines.append("")
    lines.append("## Redaction policy")
    lines.append("")
    lines.append(
        "Free-text consumer narrative fields (`complaint_what_happened`, `narrative`) "
        "are replaced with a literal redaction marker in all artifact types that may "
        "contain them (raw records, normalised candidates, report JSON). The marker is:"
    )
    lines.append("")
    lines.append(f"    {REDACTION_MARKER}")
    lines.append("")
    lines.append(
        "Structured provenance fields — complaint ID, product, issue, sub-issue, "
        "company, dates, state, zip, submission channel, company response — are "
        "preserved unmodified. Nothing in this archive represents an interpretation "
        "of any consumer's free-text narrative."
    )
    lines.append("")
    lines.append("## What is deliberately excluded")
    lines.append("")
    lines.append(
        "- The full CFPB complaint dataset is not included; only the records "
        "retrieved and processed in this specific run are present."
    )
    lines.append(
        "- Raw workspace artifacts (data/) remain gitignored; this archive is the "
        "only committed representation of this run's output."
    )
    lines.append("")
    lines.append("## Evidence Ceiling guarantee")
    lines.append("")
    lines.append(
        "The Evidence Ceiling is enforced by the methodology (Proof Gates PG-15 "
        "Source Independence and PG-16 Evidence Ceiling Compliance), not by access "
        "limitations. CFPB complaint data alone — regardless of record volume — "
        "can never produce a BUILD CANDIDATE verdict under this methodology. "
        "The ceiling must never be bypassed."
    )
    lines.append("")
    lines.append("## How a run becomes an archive")
    lines.append("")
    lines.append(
        "1. Run `python -m core.pipeline --limit N` to execute the pipeline and "
        "record the run in `data/exports/run_index.json`."
    )
    lines.append(
        "2. Run `python -m tools.build_study_archive --latest` (or `--run-id RUN-...`) "
        "to build a sanitised archive from that run."
    )
    lines.append(
        "3. The tool verifies all artifact checksums against the run manifest, "
        "redacts narrative fields, writes this README and `checksums.txt`, and "
        "creates `study_archives/{study_id}_{run_id}_{timestamp}/`."
    )
    lines.append(
        "4. Commit the new `study_archives/` subdirectory to git. The live `data/` "
        "directory stays gitignored and is never committed."
    )
    lines.append("")
    lines.append("## Independent verification")
    lines.append("")
    lines.append(
        "To verify archive integrity: run `sha256sum -c checksums.txt` from within "
        "this directory."
    )
    lines.append(
        "To verify reproducibility: re-run `python -m pytest -q` then "
        "`python -m core.pipeline --limit 3` in the repository "
        "(requires `curl` on PATH and outbound access to consumerfinance.gov)."
    )
    lines.append("")

    return lines


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a sanitised, git-committable study archive from one pipeline run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--latest", action="store_true", help="Archive the most-recent run in the run index.")
    group.add_argument("--run-id", metavar="RUN_ID", help="Archive the run with this run_id.")
    parser.add_argument(
        "--run-index",
        default=str(DEFAULT_RUN_INDEX),
        help=f"Path to run_index.json (default: {DEFAULT_RUN_INDEX})",
    )
    parser.add_argument(
        "--archive-root",
        default=str(DEFAULT_ARCHIVE_ROOT),
        help=f"Parent directory for archive output (default: {DEFAULT_ARCHIVE_ROOT})",
    )
    parser.add_argument(
        "--test-results",
        metavar="PATH",
        default=None,
        help="Optional path to a test_results.txt file to include in the archive.",
    )
    args = parser.parse_args()

    run_index_path = Path(args.run_index)
    archive_root = Path(args.archive_root)
    test_results_path = Path(args.test_results) if args.test_results else None

    try:
        run_entry = find_run_entry(
            run_index_path,
            run_id=args.run_id,
            latest=args.latest,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Archiving run {run_entry['run_id']} (study {run_entry['study_id']}, {run_entry['timestamp']}) ...")

    try:
        archive_dir = build_archive(
            run_entry,
            archive_root=archive_root,
            test_results_path=test_results_path,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Archive written: {archive_dir}")
    print(f"Verify integrity: cd {archive_dir} && sha256sum -c checksums.txt")


if __name__ == "__main__":
    main()
