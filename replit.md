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
  complaint records (e.g. complaint IDs `9999995`–`9999997`) end-to-end with
  zero errors. The Evidence OS ceiling still correctly caps the verdict at
  `CONTINUE RESEARCH` since CFPB is a single source family — that ceiling is
  a methodology rule, not an access problem, and must never be bypassed.
- The third adapter, `CFPBLocalOfficialSnapshotAdapter`, can process a local
  official CFPB CSV snapshot file if one is ever supplied, but the CLI
  (`core.pipeline`) doesn't expose a flag to select it yet — tracked as a
  follow-up task. Not currently needed since live access now works.
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

## Proof bundle
`proof_bundle/` contains a sanitised, independently-reviewable snapshot of one
live GS-CF001-C run against genuine official CFPB data: run manifest, access
diagnostic, source reliability assessment, the 3 preserved raw records and
normalised candidates (free-text narrative redacted, complaint IDs and
provenance preserved), verification artifacts, all 16 Proof Gate results,
the Markdown/JSON reports, exact test results, and SHA-256 checksums. See
`proof_bundle/README.md` for details and verification instructions.

## Project structure
- `connectors/` — source connectors (CFPB) and access adapters (API, bulk
  download, local snapshot)
- `core/` — pipeline orchestration, domain models, normalisation, storage,
  AI-governance guardrails
- `verification/`, `findings/`, `opportunity/`, `proof_gates/` — pipeline
  stages per the methodology in README.md
- `reports/` — Markdown/JSON report generation
- `studies/` — study definitions (only GS-CF001-C is implemented)
- `tests/` — pytest suite (22 tests, all passing), including focused
  curl-transport tests in `tests/test_cfpb_transport.py`
- `data/` — generated run artifacts (gitignored per-file, directories kept)
- `proof_bundle/` — sanitised, committed proof bundle (see above)
- `.github/workflows/tests.yml` — CI test workflow

## User preferences
None recorded yet.
