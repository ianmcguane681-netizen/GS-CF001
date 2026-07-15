# GS-CF001

## Overview
Research proof system for Provena (Evidence Operating System). This is a Python
CLI/library, not a web app — there is no server or frontend. It runs a
deterministic evidence pipeline over CFPB consumer complaint data for the
`GS-CF001-C Credit Reporting Disputes` study, producing traceable file
artifacts (raw records, diagnostics, findings, mechanism classifications,
opportunity decision register, proof gate results, Markdown/JSON reports,
audit trail, run manifest) under `data/`.

See `README.md` for the full methodology, evidence pipeline stages, and
evidence-ceiling rules.

## Running it
```bash
# Run the test suite (90 tests)
python -m pytest -q

# Run the GS-CF001-C credit reporting proof against live CFPB data (100 records)
python -m core.pipeline --limit 100

# Compare the last 3 runs for stability and consistency
python3 -c "
from core.cross_run_analysis import load_and_compare_last_n_runs, write_cross_run_report
comp = load_and_compare_last_n_runs(3)
write_cross_run_report(comp, 'data/exports/comparison.md')
print('stability:', comp.overall_stability)
"

# Build a sanitised, git-committable archive from the most-recent run
python -m tools.build_study_archive --latest

# Build an archive from a specific run by run_id
python -m tools.build_study_archive --run-id RUN-XXXXXXXXXX

# Include captured test results in the archive (for milestone runs)
python -m tools.build_study_archive --latest --test-results /path/to/test_results.txt
```

The `Run Tests & Pipeline` workflow runs `pytest` and then the live pipeline
in sequence on demand (one-shot CLI run, no persistent server or web UI).

## Current goal
Prove the system can take a market, pull verified pain, create verified
solutions, and reject verified stupid/non-profitable solutions — entirely
in-house, deterministically, without AI in any decision. Single market
scope (GS-CF001-C) until this is proven end-to-end.

## Storage-hardening conventions

### Per-run timestamp
Every pipeline run generates one shared timestamp at the start of
`run_credit_reporting_proof()` (microsecond resolution UTC, format
`YYYYMMDDTHHMMSSffffffZ`). This stamp is threaded into every
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
Use `core.run_index.read_run_index()` to query it programmatically.

### Standalone per-run artifacts
Each run writes these files to `data/exports/` (in addition to the combined
`processed` bundle):
- `normalised_candidates_{stamp}.json` — the normalised EvidenceCandidate list
- `findings_{stamp}.json` — structured findings generated from verified evidence
- `opportunities_{stamp}.json` — opportunity assessments derived from findings
- `mechanism_classifications_{stamp}.json` — six-category deterministic classification
- `odr_{stamp}.json` — full machine-readable Opportunity Decision Register
- `odr_{stamp}.md` — human-readable ODR report

### Study-archive generator
`tools/build_study_archive.py` is a reusable CLI script. Given `--latest` or
`--run-id RUN-…`, it builds a git-committable, sanitised archive under
`study_archives/`. Verifies all source artifact checksums before writing.
Refuses to overwrite an existing archive. Run `sha256sum -c checksums.txt`
from within an archive directory to verify integrity.

### How a live run becomes a committed archive
1. Capture test results: `python -m pytest -q -v | tee /tmp/test_results.txt`
2. Run the pipeline: `python -m core.pipeline --limit 100`
3. (Optional) Compare runs: use `core.cross_run_analysis.load_and_compare_last_n_runs(3)`
4. Build the archive: `python -m tools.build_study_archive --latest --test-results /tmp/test_results.txt`
5. Verify: `cd study_archives/<archive_dir> && sha256sum -c checksums.txt`
6. Commit the new `study_archives/` subdirectory and `analysis/` documents

## Methodology milestones

### Milestone 1 — Storage hardening (committed 9044ef2)
Timestamped reports, append-only run index, standalone per-run artifacts,
reusable study-archive generator. Archive at
`study_archives/GS-CF001-C_RUN-8FFFBA72404A_20260715T184824501724Z/`.

### Milestone 2 — Methodology validation (in progress)
Six objectives: (1) 100-record sampling design documented; (2) three controlled
100-record live CFPB runs executed; (3) cross-run comparison confirms stable
pipeline (identical mechanism distribution, verdicts, Evidence Ceiling across
all 3 runs); (4) recurring operational mechanisms identified across distinct
financial institutions using deterministic rules; (5) each mechanism classified
into one of six deterministic categories; (6) Opportunity Decision Register
produced per run with evidence references, reasoning, commercial assessment,
decision status, and Evidence Ceiling enforcement.

**Sampling design:** `sampling_design/GS-CF001-C_sampling_design.md`
**Cross-run analysis:** `analysis/GS-CF001-C_cross_run_comparison_milestone2.md`
**Archive:** `study_archives/GS-CF001-C_{run_id}_{timestamp}/`

## Mechanism classification (six categories)

All findings are classified by `findings/mechanism_classifier.py` using
deterministic rules only (no AI). Categories in order of commercial priority:

| Category | Criteria | Decision |
|---|---|---|
| `candidate_needs_corroboration` | evidence≥3, companies≥2, operational, software-addressable, all repeated | CONTINUE_RESEARCH |
| `verified_pain` | evidence≥3, companies≥2, operational, software-addressable, not all repeated | CONTINUE_RESEARCH |
| `commercially_weak` | operational + software-addressable, but insufficient scale | CONTINUE_RESEARCH |
| `non_software_problem` | operational but not software-addressable | REJECTED |
| `non_operational_problem` | not operational | REJECTED |
| `noise` | <2 verified evidence items | REJECTED |

All CFPB-only evidence is capped at CONTINUE RESEARCH by PG-15/PG-16 regardless
of category. BUILD CANDIDATE requires a second independent source family.

## Opportunity Decision Register (ODR)

`core/opportunity_decision_register.py` produces one `ODREntry` per finding/
opportunity pair per run. Each entry records: mechanism, classification,
evidence references, companies, evidence count, component hypothesis, buyer
clarity, commercial relevance, decision status, decision rationale, missing
evidence for upgrade, and Evidence Ceiling note. No AI is used. All decisions
are deterministic and reproducible.

## Cross-run analysis

`core/cross_run_analysis.py` compares N pipeline runs for: retrieval stability,
verdict and ceiling consistency, proof gate consistency, mechanism distribution,
finding/opportunity counts, and company distribution. Produces a
`CrossRunComparison` object with `overall_stability` = stable | partially_stable
| unstable, and full stability notes.

## Environment notes
- **CFPB transport fix (2026-07-14):** Python's `urllib`/`requests` TLS+HTTP
  client stack is fingerprinted and blocked by CFPB's Akamai edge. `connectors/cfpb.py`
  shells out to `curl` as transport. `curl` must be on PATH.
- **Required system dependency: `curl`.** Present in this Replit environment and
  in the `ubuntu-latest` GitHub Actions runner. `_require_curl()` raises a clear
  `RuntimeError` if missing.

## CI
`.github/workflows/tests.yml` runs the full `pytest` suite on every push and
pull request via GitHub Actions (`ubuntu-latest`, Python 3.12).

## Study archives
`study_archives/` contains sanitised, independently-reviewable snapshots of
selected live GS-CF001-C runs. Each subdirectory is named
`{study_id}_{run_id}_{timestamp}/`. The legacy `proof_bundle/` directory is
the first manually-assembled milestone snapshot. New archives are generated
by `tools/build_study_archive.py`.

## Analysis documents
`analysis/` contains committed cross-run comparison reports and other
analytical documents produced from pipeline runs. These are git-tracked
(not gitignored).

## Project structure
- `connectors/` — source connectors (CFPB) and access adapters
- `core/` — pipeline orchestration, models, normalisation, storage, run index,
  manifest, opportunity decision register, cross-run analysis
- `findings/` — findings engine, mechanism classifier
- `tools/` — CLI utilities: `build_study_archive.py`
- `verification/`, `opportunity/`, `proof_gates/` — pipeline stages
- `reports/` — Markdown/JSON report generation
- `studies/` — study definitions (only GS-CF001-C)
- `sampling_design/` — sampling design documents
- `analysis/` — committed cross-run comparison and analysis documents
- `tests/` — pytest suite (90 tests, all passing)
- `data/` — generated run artifacts (gitignored)
- `study_archives/` — committed, sanitised milestone archives
- `proof_bundle/` — legacy first milestone archive

## User preferences
None recorded yet.
