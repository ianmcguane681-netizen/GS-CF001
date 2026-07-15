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
# Run the test suite (125+ tests)
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
reusable study-archive generator.

### Milestone 2 — Methodology validation (committed 562a085)
100-record sampling design, three live CFPB runs, cross-run analysis, mechanism
classifier, ODR, study archive. Archive at
`study_archives/GS-CF001-C_RUN-8FFFBA72404A_20260715T184824501724Z/`.

### Milestone 3 — Methodology corrections (2026-07-15)
Six corrections from code review applied: (C1) ceiling note and category labels
explicitly caveat CFPB complaints as unverified allegations; (C2) "only remaining
blocker" framing removed everywhere; (C3) `missing_for_upgrade` expanded to 7
commercial requirements; (C4) cross-run analysis extended with complaint-ID
set/ordering/mutation checks; (C5) `software_addressable` moved out of the
`verified_candidate` gate enabling genuine REJECTED ODR outcomes; (C6) mechanism
labels renamed to trigger-process-failure format.

**Sampling design:** `sampling_design/GS-CF001-C_sampling_design.md`
**Cross-run analysis:** `analysis/GS-CF001-C_cross_run_comparison_milestone3.md`
**Archive:** `study_archives/GS-CF001-C_RUN-E828F3A805D3_20260715T193138775195Z/`

**Milestone 3 cross-run findings (3 × 100-record runs):**
- Complaint IDs identical and in identical order across all three runs (Jaccard=1.0)
- Verdict: CONTINUE RESEARCH (all 3); Ceiling: CONTINUE RESEARCH (all 3)
- Mechanisms stable: `bureau_dispute_reinvestigation_failure`, `furnisher_tradeline_data_error_persistence`
- Findings: 2; Opportunities: 2; Proof gates: consistent
- Source mutation detected in ~100 records — false positive caused by volatile CFPB
  metadata (company_response, timely, _retrieved_at) being included in the content
  hash. Fixed in Milestone 4.
- `tests/` — 114 tests, all passing

### Milestone 4 — Three-agent coordinated review (2026-07-15, commit a1d4da0)
Three workstreams executed simultaneously:

**Mutation analysis fix (critical — F-01 from methodology audit):**
`core/cross_run_analysis.py` rewritten with three named field buckets:
- `CLASSIFICATION_INPUT_FIELDS` (`complaint_what_happened`, `product`, `sub_product`,
  `issue`, `sub_issue`) — fields the classifier reads; mutation here is `classification_mutation_detected` (CRITICAL)
- `STABLE_BUSINESS_FIELDS` (`company`, `state`, `zip_code`, `date_received`, etc.) —
  not used in classification; unexpected mutation flagged as `business_mutation_detected` (WARNING)
- Volatile metadata (`company_response`, `timely`, `_retrieved_at`, etc.) — CFPB updates
  these continuously; differences are `metadata_differs` (INFO, never penalises stability)

Result: `overall_stability: stable` — was `unstable` before the fix. 100
metadata-only differences per run are correctly classified as informational.

**Borderline vote detection (F-04 from methodology audit):**
`MechanismClassification.borderline_note` field (str, default `""`). Populated
when any majority vote driving classification falls within 10pp of 50%. Helps
reviewers identify classifications sensitive to small evidence changes.

**Methodology audit report:** `analysis/review_methodology_audit.md`
Findings: F-01 CRITICAL (mutation fix — resolved), F-04 MEDIUM (borderline note —
resolved), F-02/F-03/F-05/F-06 documented with primary agent responses.

**Commercial review report:** `analysis/review_commercial.md`
Commercial gap register (9 rows): unit economics, TAM, competitive displacement,
buyer persona, e-OSCAR integration all CRITICAL or HIGH. Incumbents identified:
e-OSCAR, Pega, Salesforce FSC.

**Cross-run analysis:** `analysis/GS-CF001-C_cross_run_comparison_milestone4.md`
**Archive:** `study_archives/GS-CF001-C_RUN-6A31FC091937_20260715T195010440210Z/`

**Milestone 4 cross-run findings (3 × 100-record runs):**
- Complaint IDs identical, ordering stable, Jaccard=1.0 (all 3 runs)
- Verdict: CONTINUE RESEARCH (all 3); Ceiling: CONTINUE RESEARCH (all 3)
- Mechanisms stable: `bureau_dispute_reinvestigation_failure`, `furnisher_tradeline_data_error_persistence`
- Findings: 2; Opportunities: 2; Proof gates: consistent
- `classification_mutation_detected: False` — no classification inputs changed ✓
- `metadata_differs: True` (100 records) — expected, informational only ✓
- `tests/` — 125 tests, all passing

## Mechanism classification (six categories)

All findings are classified by `findings/mechanism_classifier.py` using
deterministic rules only (no AI). Categories in order of commercial priority:

| Category | Criteria | Decision |
|---|---|---|
| `repeated_complaint_signal` | evidence≥3, companies≥2, operational, software-addressable, all repeated | CONTINUE_RESEARCH |
| `partial_complaint_signal` | evidence≥3, companies≥2, operational, software-addressable, not all repeated | CONTINUE_RESEARCH |
| `commercially_weak` | operational + software-addressable, but insufficient scale | CONTINUE_RESEARCH |
| `non_software_problem` | operational but not software-addressable (Correction 5: reachable now) | REJECTED |
| `non_operational_problem` | not operational | REJECTED |
| `noise` | <2 verified evidence items | REJECTED |

All CFPB-only evidence is capped at CONTINUE RESEARCH by PG-15/PG-16 regardless
of category. BUILD CANDIDATE requires a second independent source family.

**Milestone 3 corrections (2026-07-15):**
- C1: Category labels and ceiling note explicitly caveat CFPB complaints as unverified allegations
- C2: "only remaining blocker" language removed from all reasoning, labels, and upgrade lists
- C3: `missing_for_upgrade` expanded to 7 requirements (buyer, cost, competitive, non-software, market, commercial signal, independent corroboration)
- C4: Cross-run analysis extended with complaint-ID set/ordering/mutation checks
- C5: `software_addressable` moved out of `verified_candidate` gate; `non_software_problem` findings now reach ODR and produce genuine REJECTED entries
- C6: Mechanism labels renamed to trigger-process-failure format: `bureau_dispute_reinvestigation_failure`, `furnisher_tradeline_data_error_persistence`, `dispute_supporting_evidence_rejection`, `investigation_outcome_notification_failure`, `unclassified_credit_reporting_complaint`

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

**Three-bucket mutation analysis (Milestone 4):**
Raw records are split into three named field buckets before hashing:
- `CLASSIFICATION_INPUT_FIELDS` — any change sets `classification_mutation_detected`
- `STABLE_BUSINESS_FIELDS` — any change sets `business_mutation_detected`
- Volatile metadata — differences are `metadata_differs` (informational, never penalises stability)

`mutation_detected` (summary) = `classification_mutation_detected OR business_mutation_detected`.
Volatile metadata differences never count as mutations.

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
- `tests/` — pytest suite (125 tests, all passing)
- `data/` — generated run artifacts (gitignored)
- `study_archives/` — committed, sanitised milestone archives
- `proof_bundle/` — legacy first milestone archive

## User preferences
None recorded yet.
