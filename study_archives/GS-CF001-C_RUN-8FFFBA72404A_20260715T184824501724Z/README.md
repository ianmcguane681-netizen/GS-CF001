# GS-CF001-C Study Archive — RUN-8FFFBA72404A

Sanitised, independently-reviewable archive of one live GS-CF001-C pipeline run.

## Run metadata

| Field | Value |
|---|---|
| Run ID | `RUN-8FFFBA72404A` |
| Study ID | `GS-CF001-C` |
| Run timestamp | `2026-07-15T18:48:24Z` |
| Verdict | **CONTINUE RESEARCH** |
| Evidence Ceiling | **CONTINUE RESEARCH** |
| Source access method | `official_cfpb_search_api` |

## Contents

| File | Contents |
|---|---|
| `run_manifest.json` | Run ID, code commit hash, methodology versions, retrieval timestamps, input record IDs, artifact checksums, final verdict. No personal data. |
| `access_diagnostics.json` | Request/response metadata (endpoint, method, headers, status, interpretation). No personal data. |
| `source_reliability_assessment.json` | CFPB source-reliability record: publisher, authority level, limitations, verification constraints. No personal data. |
| `raw_records_redacted.json` | Raw CFPB records as retrieved. Free-text narrative (complaint_what_happened) replaced by redaction marker; all structured provenance fields preserved. |
| `normalised_candidates_redacted.json` | Normalised EvidenceCandidate records. Same narrative redaction applied to raw_record.complaint_what_happened and parsed_fields.narrative. |
| `verification_artifacts.json` | Deterministic verification output per candidate. No consumer narrative by construction. |
| `proof_gate_results.json` | All Proof Gate results: status, threshold, observed value, confidence, missing evidence, ceiling constraint flag. |
| `audit_trail.json` | State transitions for each candidate through the pipeline stages. |
| `findings.json` | Structured findings generated from verified evidence. |
| `opportunities.json` | Opportunity assessments derived from findings. |
| `report.json` | Machine-readable verdict report. Narrative fields redacted. |
| `report.md` | Full human-readable Markdown verdict report. |
| `archive_metadata.json` | Archive provenance: generated timestamp, run record, file checksums, redaction policy. |
| `test_results.txt` | pytest output captured immediately before this run (if included). |

## Redaction policy

Free-text consumer narrative fields (`complaint_what_happened`, `narrative`) are replaced with a literal redaction marker in all artifact types that may contain them (raw records, normalised candidates, report JSON). The marker is:

    [REDACTED: free-text consumer narrative — not preserved in archive]

Structured provenance fields — complaint ID, product, issue, sub-issue, company, dates, state, zip, submission channel, company response — are preserved unmodified. Nothing in this archive represents an interpretation of any consumer's free-text narrative.

## What is deliberately excluded

- The full CFPB complaint dataset is not included; only the records retrieved and processed in this specific run are present.
- Raw workspace artifacts (data/) remain gitignored; this archive is the only committed representation of this run's output.

## Evidence Ceiling guarantee

The Evidence Ceiling is enforced by the methodology (Proof Gates PG-15 Source Independence and PG-16 Evidence Ceiling Compliance), not by access limitations. CFPB complaint data alone — regardless of record volume — can never produce a BUILD CANDIDATE verdict under this methodology. The ceiling must never be bypassed.

## How a run becomes an archive

1. Run `python -m core.pipeline --limit N` to execute the pipeline and record the run in `data/exports/run_index.json`.
2. Run `python -m tools.build_study_archive --latest` (or `--run-id RUN-...`) to build a sanitised archive from that run.
3. The tool verifies all artifact checksums against the run manifest, redacts narrative fields, writes this README and `checksums.txt`, and creates `study_archives/{study_id}_{run_id}_{timestamp}/`.
4. Commit the new `study_archives/` subdirectory to git. The live `data/` directory stays gitignored and is never committed.

## Independent verification

To verify archive integrity: run `sha256sum -c checksums.txt` from within this directory.
To verify reproducibility: re-run `python -m pytest -q` then `python -m core.pipeline --limit 3` in the repository (requires `curl` on PATH and outbound access to consumerfinance.gov).
