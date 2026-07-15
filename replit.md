# GS-CF001

## Overview
Research proof system for Provena (Evidence Operating System). This is a Python
CLI/library, not a web app — there is no server or frontend. It runs a
deterministic evidence pipeline over CFPB consumer complaint data for the
`GS-CF001-C Credit Reporting Disputes` study, producing traceable file
artifacts (raw records, diagnostics, findings, opportunity assessments, Proof
Gate results, Markdown/JSON reports, audit trail, run manifest) under `data/`.

See `README.md` for the full methodology, evidence pipeline stages, and
evidence-ceiling rules.

## Running it
```bash
# Run the test suite (54 tests)
python -m pytest -q

# Run the GS-CF001-C credit reporting proof against live CFPB data
python -m core.pipeline --limit 3

# Build a sanitised, git-committable archive from the most-recent run
python -m tools.build_study_archive --latest

# Build an archive from a specific run by run_id
python -m tools.build_study_archive --run-id RUN-XXXXXXXXXX

# Include captured test results in the archive (for milestone runs)
python -m tools.build_study_archive --latest --test-results /path/to/test_results.txt
```

The `Run Tests & Pipeline` workflow runs `pytest` and then the live pipeline
in sequence on demand (one-shot CLI run, no persistent server or web UI).

## Storage-hardening conventions

### Per-run timestamp
Every pipeline run generates one shared timestamp at the start of
`run_credit_reporting_proof()` (microsecond resolution UTC, format
`YYYYMMDDTHHMMSSffffffZ`). This stamp is passed explicitly into every
`write_json_artifact()` call so all of a single run's files carry the same
stamp and can be grouped by it. No run's files collide with another run's.
The helper is `core.storage.run_timestamp()`.

### Run index
`data/exports/run_index.json` is an append-only JSON list (one entry per
pipeline run) that records: `run_id`, `timestamp`, `study_id`, `verdict`,
`evidence_ceiling`, `source_access_method`, `artifact_paths`, and
`artifact_checksums` (computed from the final on-disk state of every artifact
after all writes complete). The file is gitignored (lives under `data/`) and
is workspace-persistent — it accumulates across every run in the environment.
Use `core.run_index.read_run_index()` to query it programmatically. The index
degrades gracefully on a corrupt or missing file (returns an empty list rather
than crashing).

### Standalone per-run artifacts
In addition to the combined `processed` bundle, each run now writes three
standalone files to `data/exports/`:
- `normalised_candidates_{stamp}.json` — the normalised EvidenceCandidate list
- `findings_{stamp}.json` — structured findings generated from verified evidence
- `opportunities_{stamp}.json` — opportunity assessments derived from findings

These expose each stage independently for inspection, diff, or archiving
without unpacking the whole processed bundle. Backward compatibility with the
combined bundle is preserved.

### Study-archive generator
`tools/build_study_archive.py` is a reusable script that turns any completed
pipeline run (identified by run_id or "latest") into a git-committable,
sanitised, integrity-checked archive under `study_archives/`. Run it after
every milestone pipeline run.

**What the archive contains:**
- `raw_records_redacted.json` — raw CFPB records with narrative fields redacted
- `normalised_candidates_redacted.json` — normalised candidates with narrative redacted
- `verification_artifacts.json`, `proof_gate_results.json`, `audit_trail.json`
- `findings.json`, `opportunities.json`
- `report.json` (narrative-redacted), `report.md` (full Markdown verdict report)
- `run_manifest.json`, `access_diagnostics.json`, `source_reliability_assessment.json`
- `archive_metadata.json` — machine-readable provenance, file checksums, redaction policy
- `README.md` — human-readable provenance, contents, verification instructions
- `checksums.txt` — SHA-256 of every file; run `sha256sum -c checksums.txt` to verify

**Redaction policy:** the fields `complaint_what_happened` and `narrative` are
replaced with a literal marker wherever they appear in any artifact that may
carry them. Structured provenance fields (complaint ID, product, issue, company,
dates, etc.) are preserved unmodified.

**Integrity:** checksums are verified against the run-index values (which are
computed from final on-disk state) before any file is written. A mismatch
aborts immediately and removes the partial archive. Existing archives are never
silently overwritten — a `FileExistsError` is raised if the target directory
exists.

**Git tracking:** `study_archives/` is not gitignored. Commit each new archive
subdirectory as part of the milestone that produced it. The live `data/`
directory stays gitignored.

### How a live run becomes a committed archive
1. Capture test results: `python -m pytest -q -v | tee /tmp/test_results.txt`
2. Run the pipeline: `python -m core.pipeline --limit 3`
3. Build the archive: `python -m tools.build_study_archive --latest --test-results /tmp/test_results.txt`
4. Inspect the archive under `study_archives/`; verify with `sha256sum -c checksums.txt`
5. Commit the new `study_archives/` subdirectory together with any other milestone changes

## Environment notes
- **CFPB transport fix (2026-07-14):** Python's `urllib`/`requests` TLS+HTTP
  client stack is fingerprinted and blocked (HTTP 403, or an indefinite hang)
  by CFPB's Akamai edge from this environment — verified by confirming the
  identical URL, headers, and outbound IP succeed instantly via `curl` but
  fail via Python's stdlib HTTP clients. `connectors/cfpb.py` now shells out
  to `curl` as the transport for the official Search API and bulk-download
  adapters, behind the same `fetch_json`/`opener` injection seams the
  adapters already exposed (`CFPBTransportHTTPError` mirrors
  `urllib.error.HTTPError`'s interface so existing diagnostic/error handling
  above the transport layer is unchanged). No new dependency: `curl` is a
  system binary.
- **Query bug fix (2026-07-14):** `CFPBAPIAccessAdapter.build_url` also sent
  `format=json&no_aggs=true`, which — on the *current* live API — switches
  the endpoint into a full-database export/attachment mode that ignores
  `size`/`product` filtering (confirmed: multi-GB response instead of a
  filtered result). Removing those two params restores the intended
  Elasticsearch-style `{"hits":{"hits":[...]}}` response, filtered by
  `product` and limited by `size`, which the rest of the connector already
  expects.
- With both fixes, `python -m core.pipeline` retrieves genuine live CFPB
  complaint records end-to-end with zero errors. The Evidence OS ceiling still
  correctly caps the verdict at `CONTINUE RESEARCH` since CFPB is a single
  source family — that ceiling is a methodology rule, not an access problem,
  and must never be bypassed.
- **Required system dependency: `curl`.** Any environment that runs the live
  pipeline (`python -m core.pipeline`) must have the `curl` binary on `PATH`
  for official CFPB retrieval to work. It is present by default in this
  Replit environment and in the `ubuntu-latest` GitHub Actions runner. If
  missing, `connectors.cfpb._require_curl()` raises a clear `RuntimeError`
  instead of silently falling back to a blocked transport. Tests do not
  require `curl` — they stub `subprocess.run`/`shutil.which`.

## CI
`.github/workflows/tests.yml` runs the full `pytest` suite on every push and
pull request via GitHub Actions (`ubuntu-latest`, Python 3.12).

## Study archives
`study_archives/` contains sanitised, independently-reviewable snapshots of
selected live GS-CF001-C runs. Each subdirectory is named
`{study_id}_{run_id}_{timestamp}/` and contains everything documented in the
Storage-hardening conventions section above. See the README.md inside each
archive for full provenance and verification instructions.

The legacy `proof_bundle/` directory is a manually-assembled snapshot from the
first milestone run (2026-07-14, commit `9bb288c`). New milestone archives are
generated by `tools/build_study_archive.py` and stored under `study_archives/`.

## Project structure
- `connectors/` — source connectors (CFPB) and access adapters (API, bulk
  download, local snapshot)
- `core/` — pipeline orchestration, domain models, normalisation, storage,
  AI-governance guardrails, run manifest, run index
- `tools/` — CLI utilities: `build_study_archive.py` (study archive generator)
- `verification/`, `findings/`, `opportunity/`, `proof_gates/` — pipeline
  stages per the methodology in README.md
- `reports/` — Markdown/JSON report generation
- `studies/` — study definitions (only GS-CF001-C is implemented)
- `tests/` — pytest suite (54 tests, all passing), including focused tests for
  curl-transport, run-index edge cases, and the study-archive generator
- `data/` — generated run artifacts (gitignored per-file, directories kept)
- `study_archives/` — committed, sanitised milestone archives (git-tracked)
- `proof_bundle/` — legacy manually-assembled proof bundle (first milestone)
- `.github/workflows/tests.yml` — CI test workflow

## User preferences
None recorded yet.
