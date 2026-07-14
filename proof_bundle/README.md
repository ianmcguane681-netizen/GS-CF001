# GS-CF001-C Live Proof Bundle (sanitised)

This bundle is evidence that the GS-CF001-C pipeline (Evidence OS methodology)
successfully retrieved **genuine, live, official CFPB complaint records** through
the fixed curl-based transport, ran the full deterministic pipeline against them,
and produced a methodology-compliant verdict.

- Run captured: 2026-07-14T22:42:54Z
- Run ID: `RUN-ABEC4DE8FEE1`
- Study ID: `GS-CF001-C`
- Code commit under test: `9bb288cfad99e16425f98000a906f8ca1a35eeac`
- Source access method: `official_cfpb_search_api`
- Records retrieved: 3 (limit requested: 3)
- Complaint IDs: `9999997`, `9999996`, `9999995`
- Final verdict: **CONTINUE RESEARCH** (evidence ceiling applied; `independent_source_family_count: 1`)

## Required system dependency

The official CFPB endpoints (`consumerfinance.gov` search API and
`files.consumerfinance.gov` bulk download) are fingerprinted and blocked by an
Akamai edge when accessed through Python's `urllib`/`requests` client stack, even
though the identical request succeeds via `curl` from the same IP. To restore
live access without weakening the methodology, `connectors/cfpb.py` shells out to
the **`curl`** binary as its HTTP transport, behind the same injectable
`fetch_json`/`opener` seams the connector already exposed for tests.

**`curl` must be present on `PATH`** in any environment that runs the live
pipeline. It already ships in this Replit environment and in the
`ubuntu-latest` GitHub Actions runner used by `.github/workflows/tests.yml`.
If `curl` is missing, `connectors.cfpb._require_curl()` raises a clear
`RuntimeError` rather than failing silently or falling back to a blocked
transport.

## Contents

| File | Contents |
| --- | --- |
| `run_manifest.json` | Run ID, code commit hash, methodology/rule versions, retrieval timestamps, input record identifiers, artifact checksums, final verdict. No personal data. |
| `access_diagnostics.json` | Request/response metadata (endpoint, method, headers, status, interpretation) for the live retrieval. No personal data. |
| `source_reliability_assessment.json` | Standing CFPB source-reliability record: publisher, authority level, known limitations, verification/independence constraints, prohibited inferences. No personal data. |
| `raw_records_redacted.json` | The 3 preserved raw CFPB records as retrieved, with any non-empty free-text narrative field (`complaint_what_happened`) replaced by a redaction marker. Complaint IDs, product/issue/sub-issue codes, company names, dates, and all other structured provenance fields are preserved unmodified. In this run the source narrative fields were already empty, so no text was present to redact. |
| `normalised_candidates_redacted.json` | The 3 normalised `EvidenceCandidate` records (post field-mapping), with the same narrative redaction applied to `raw_record.complaint_what_happened` and `parsed_fields.narrative`. |
| `verification_artifacts.json` | Deterministic verification output per candidate (mechanism classification, verification status, reasoning chain, source limitations). Contains no free-text consumer narrative by construction. |
| `proof_gate_results.json` | All 16 Proof Gate results (PG-01 … PG-16) for this run: status, threshold, observed value, confidence, missing evidence, and whether each gate constrains the maximum verdict. |
| `report.md` | The full human-readable Markdown verdict report generated for this run. |
| `report.json` | The full machine-readable verdict report for this run, with the same narrative redaction applied. |
| `test_results.txt` | Verbatim `pytest -q -v` output (22 passed) captured immediately before this run, plus the command and commit under test. |
| `checksums.txt` | SHA-256 checksums of every file in this bundle, for independent integrity verification. |

## What is deliberately excluded

- The full CFPB complaint dataset (millions of records) is not included; only
  the 3 records genuinely retrieved and processed by this run are preserved.
- Any uncontrolled consumer free-text narrative is redacted, not summarised or
  paraphrased, so nothing here represents an interpretation of narrative
  content.
- Intermediate development-only artifacts (earlier failed/blocked runs,
  scratch API responses used during root-cause investigation) are not part of
  this bundle.

## Methodology guarantee unaffected

The curl-transport and query-parameter fixes changed **only** how HTTP
requests are made and which query parameters are sent — they did not touch
normalisation, verification, proof-gate, or evidence-ceiling logic. As shown
in `proof_gate_results.json` and `report.md`, PG-15 (Source Independence) and
PG-16 (Evidence Ceiling Compliance) still correctly report
`independent_source_family_count: 1` and cap the verdict at **CONTINUE
RESEARCH**. CFPB complaint data alone can never produce a `BUILD CANDIDATE`
verdict under this methodology, regardless of record volume or repetition.

## Independent verification

To verify integrity: `sha256sum -c checksums.txt` from within this directory.
To verify reproducibility: re-run `python -m pytest -q` and
`python -m core.pipeline --limit 3` against the repository at commit
`9bb288cfad99e16425f98000a906f8ca1a35eeac` or later (requires `curl` on
`PATH` and outbound network access to `consumerfinance.gov`).
