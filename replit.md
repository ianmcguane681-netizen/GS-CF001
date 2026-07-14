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
# Run the test suite
python -m pytest -q

# Run the GS-CF001-C credit reporting proof against live CFPB data
python -m core.pipeline --limit 3
```

The `Run Tests & Pipeline` workflow runs both of the above in sequence
on demand (it's a one-shot CLI run, not a persistent server — there's no
web UI to preview since this project is a research pipeline, not an app).

Dependencies (`pytest`, `requests`) are installed via Replit's Python package
manager; `requirements.txt` lists `pytest`.

## Environment notes
- Outbound requests to the official CFPB Search API
  (`consumerfinance.gov/.../search/api/v1/`) and the official CFPB bulk
  download (`files.consumerfinance.gov/ccdb/complaints.csv.zip`) are currently
  blocked with HTTP 403 (Akamai "Access Denied") from this environment. This
  is expected, documented behavior for the repo: when live CFPB access is
  blocked, the pipeline writes an access diagnostic and stops short of
  normalisation instead of fabricating placeholder evidence (see
  `data/exports/access_diagnostics_*.json` and the resulting `CONTINUE
  RESEARCH`/`REJECT` verdict). No code changes are needed to "fix" this —
  it reflects the intended fail-closed design. All three official access
  methods (Search API, bulk download, local official snapshot) have been
  exercised manually and each correctly produced its own diagnostic when
  unavailable.
- The third adapter, `CFPBLocalOfficialSnapshotAdapter`, can process a local
  official CFPB CSV snapshot file if one is ever supplied, bypassing the
  network access issue, but the CLI (`core.pipeline`) doesn't expose a flag
  to select it yet — tracked as a follow-up task.

## Project structure
- `connectors/` — source connectors (CFPB) and access adapters (API, bulk
  download, local snapshot)
- `core/` — pipeline orchestration, domain models, normalisation, storage,
  AI-governance guardrails
- `verification/`, `findings/`, `opportunity/`, `proof_gates/` — pipeline
  stages per the methodology in README.md
- `reports/` — Markdown/JSON report generation
- `studies/` — study definitions (only GS-CF001-C is implemented)
- `tests/` — pytest suite (13 tests, all passing)
- `data/` — generated run artifacts (gitignored per-file, directories kept)

## User preferences
None recorded yet.
