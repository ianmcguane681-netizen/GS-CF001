# GS-CF001-C Sampling Design — 100-Record Live CFPB Pull

**Version:** SD-002 (Milestone 3 corrections applied)
**Study:** GS-CF001-C Credit Reporting Disputes  
**Prepared:** 2026-07-15  
**Status:** Approved for methodology-validation milestone

---

## 1. Purpose

This document defines the defensible, reproducible sampling design for the
GS-CF001-C methodology-validation milestone. The goal is not to characterise
the full CFPB complaint population — it is to determine whether the Evidence OS
pipeline can reliably identify, classify, and assess recurring operational pain
from a fixed, reproducible pull of genuine official CFPB data, and whether that
pain meets the evidence threshold for `CONTINUE RESEARCH` under a single source
family.

---

## 2. Sampling rationale — why 100 records

| Consideration | Rationale |
|---|---|
| Minimum for mechanism repetition | At least 3 verified instances of the same mechanism across 2+ companies is required for `finding_supported_cfpb_only`. 100 records provides sufficient margin for filtering, rejection, and mechanism spread while staying tractable for full artifact traceability. |
| Pipeline tractability | Each record produces a candidate, a verified-evidence object, potential findings, and ODR entries. 100 records keep all artifact files human-auditable and archive-committable. |
| Avoids over-claiming | 100 CFPB records is a deliberately modest pull. The analysis explicitly does not claim to characterise the full complaint population. The Evidence Ceiling (CONTINUE RESEARCH) enforces this. |
| Reproducibility baseline | 100 records is a stable size for comparing three independent pipeline runs: small enough that CFPB API retrieval is reliable, large enough to show mechanism consistency across runs. |
| Not a statistical sample | This design does not claim statistical representativeness. It claims only that the retrieved records are genuine official CFPB complaints filtered by product category, processed deterministically, and that any recurring mechanisms observed are real patterns within this pull. |

---

## 3. Source and filter specification

| Parameter | Value |
|---|---|
| Source | CFPB Consumer Complaint Database (official search API) |
| Source ID | `CFPB-CCD-001` |
| Product filter | `Credit reporting or other personal consumer reports` |
| Record limit | 100 (`--limit 100`) |
| Sort order | CFPB API default (most recently received first, as returned by the Elasticsearch `size` parameter without explicit sort override) |
| Transport | `curl` (required; Python urllib/requests is blocked by CFPB Akamai TLS fingerprinting) |
| Access method | `official_cfpb_search_api` |
| Endpoint | `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?size=100&product=Credit+reporting+or+other+personal+consumer+reports` |

---

## 4. Controlled run protocol

Three independent pipeline runs are executed under identical conditions:

| Parameter | Value |
|---|---|
| Command | `python -m core.pipeline --limit 100` |
| Data directory | `data/` (default) |
| Environment | Replit workspace, same code commit for all three runs |
| Timing | Sequential, not simultaneous |
| Test suite | All tests must pass before each run |
| Run recording | Each run appended to `data/exports/run_index.json` automatically |
| Artifacts | All 14 per-run artifact files written and checksummed |

**Why three runs:**
1. Confirm retrieval stability (same records or representative mechanism distribution)
2. Confirm artifact consistency (same mechanism classifications, verdict, Evidence Ceiling)
3. Identify any run-to-run variation in findings or gate statuses
4. Demonstrate the pipeline produces consistent, reproducible results — not one-off outputs

---

## 5. Expected variation between runs

CFPB API responses may return different records between calls (the endpoint does
not guarantee a deterministic order or a stable result set for a given `size`
parameter). Acceptable variation:

| Variable | Acceptable | Not acceptable |
|---|---|---|
| Record count | Exactly 100 each run (if API returns sufficient records) | 0 records (API blocked or down) |
| Specific complaint IDs | May differ between runs | — |
| Mechanism types detected | Same set or subset of known mechanisms | Entirely new mechanisms not in `verification/rules.py` |
| Evidence ceiling | `CONTINUE RESEARCH` every run (CFPB-only data) | Any deviation from ceiling |
| Verdict | `CONTINUE RESEARCH` or `REJECT` (if no candidates pass normalisation) | `BUILD CANDIDATE` |
| Gate PG-15, PG-16 | PG-15 FAIL, PG-16 PASS/ceiling applied, every run | PG-15 PASS (requires second source family not added) |

---

## 6. Normalisation and verification rules (reference)

Records are normalised by `core/normalization.py` using the product inclusion test:

```
"credit reporting" in product.lower() or "consumer reports" in product.lower()
```

Verification by `verification/classifier.py` applies:
- `OPERATIONAL_TERMS` — presence signals an operational complaint (tightened: "information" and
  "report" removed because they are too broad and appear in non-operational complaints)
- `SOFTWARE_ADDRESSABLE_TERMS` — presence signals a software-addressable mechanism
- `MECHANISM_RULES` — deterministic priority-ordered rules assign one of five mechanism labels

**Correction 5 — `software_addressable` is a classification input, not a verification gate:**  
A complaint is a `verified_candidate` if and only if `operational=True AND traceable=True`.
Software addressability does NOT gate verification status. This ensures non-software complaints
reach the findings engine and produce genuine REJECTED ODR outcomes from real complaint data.

---

## 7. Mechanism labels (trigger-process-failure format)

**Correction 6** renamed all mechanism labels to use consistent trigger-process-failure-consequence
format. The five mechanism labels are:

| Label | Description |
|---|---|
| `bureau_dispute_reinvestigation_failure` | Dispute triggers reinvestigation; bureau fails to correct result |
| `furnisher_tradeline_data_error_persistence` | Furnisher fails to remove or correct a disputed tradeline error |
| `dispute_supporting_evidence_rejection` | Evidence submitted with a dispute is rejected or ignored |
| `investigation_outcome_notification_failure` | Outcome notification not delivered or delayed after investigation |
| `unclassified_credit_reporting_complaint` | Default: does not match any higher-priority mechanism pattern |

The old labels (`credit_report_dispute_investigation`, `incorrect_credit_report_information`,
`credit_report_documentation_handling`, `credit_report_resolution_communication`,
`credit_reporting_dispute_handling`) are retired.

---

## 8. Mechanism classification criteria

Each identified finding is classified into one of six categories by
`findings/mechanism_classifier.py` using deterministic rules only:

| Category | Rules | ODR Decision |
|---|---|---|
| `noise` | evidence_count < 2 or no verified_candidate items | REJECTED |
| `non_operational_problem` | Has evidence; operational=False for majority of verified items | REJECTED |
| `non_software_problem` | Operational evidence present; software_addressable=False for majority | REJECTED |
| `commercially_weak` | Operational + software-addressable; company_count < 2 or evidence_count < 3, or status ≠ finding_supported_cfpb_only | CONTINUE_RESEARCH |
| `repeated_complaint_signal` | evidence≥3, companies≥2, operational, software-addressable, status=finding_supported_cfpb_only, all repeated | CONTINUE_RESEARCH |
| `partial_complaint_signal` | evidence≥3, companies≥2, operational, software-addressable, status=finding_supported_cfpb_only, not all repeated | CONTINUE_RESEARCH |

**Correction 1** — renamed categories:
- `candidate_needs_corroboration` → `repeated_complaint_signal` (old name implied only one remaining blocker)
- `verified_pain` → `partial_complaint_signal` (old name incorrectly implied verified operational fact)

**Correction 2** — "only remaining blocker" language removed from all category labels, reasoning chains,
and `missing_for_upgrade` lists. CFPB complaints are unverified consumer allegations; repeating
a complaint pattern is necessary but not sufficient evidence of operational failure.

**Correction 3** — `missing_for_upgrade` now covers all seven advance requirements:
1. Independent corroboration from a non-CFPB source family
2. Buyer persona clarity (who pays, who authorises)
3. Measurable cost or financial impact
4. Competitive landscape and existing solution maturity
5. Non-software alternative analysis
6. Market size evidence
7. Commercial signal (willingness-to-pay or procurement evidence)

---

## 9. Rejection harness (Correction 5 validation)

`connectors/rejection_harness.py` provides `RejectionHarnessConnector` — a controlled test
connector with 6 synthetic CFPB-taxonomy complaints (3 Pattern A: furnisher refused removal,
3 Pattern B: identity theft result without removal). All are `operational=True, traceable=True,
software_addressable=False`, so they:
- Pass the `verified_candidate` gate (operational AND traceable)
- Classify as `non_software_problem`
- Produce genuine **REJECTED** ODR entries

This confirms the pipeline correctly identifies and rejects non-software operational problems
and is not restricted to producing only CONTINUE_RESEARCH outcomes.

`tests/test_rejection_harness.py` validates the full harness pipeline end-to-end.

---

## 10. Evidence Ceiling enforcement

CFPB data is a single source family. Proof Gates PG-15 (Source Independence)
and PG-16 (Evidence Ceiling Compliance) enforce a hard ceiling of
`CONTINUE RESEARCH` regardless of how many records are retrieved, how many
mechanisms are identified, or how many companies are observed.

This ceiling is a methodology rule, not an access limitation. It applies even
if 10,000 records are retrieved. The ceiling can only be removed by adding a
second independent source family (regulatory, enforcement, judicial, audit, or
company-examination evidence). That is not part of this milestone.

REJECTED ODR entries do not represent a breach of the ceiling — they represent
findings the pipeline has actively eliminated as non-viable.

---

## 11. Opportunity Decision Register (ODR)

The ODR is produced by `core/opportunity_decision_register.py` for every run.
Each entry records: mechanism, classification, evidence references, companies,
evidence count, commercial assessment, decision status, Evidence Ceiling note,
and full deterministic reasoning chain. No AI is used in any ODR decision.
Decisions are derived entirely from finding status, mechanism classification
rules, and proof gate outputs.

**Correction 1** — `EVIDENCE_CEILING_NOTE` updated to include explicit caveat that
CFPB complaints are unverified consumer allegations, not confirmed operational facts.

**Correction 2** — ODR rationale language does not use "only remaining blocker" framing.
The ceiling applies to all CFPB-only findings; it is not presented as a single obstacle.

---

## 12. What this design does not claim

- It does not claim statistical representativeness of the full CFPB complaint
  population.
- It does not claim that identified mechanisms are proven operational failures
  (CFPB complaints are unverified consumer allegations).
- It does not claim commercial viability of any identified opportunity.
- It does not claim BUILD CANDIDATE status is appropriate. CFPB-only evidence
  can only ever support CONTINUE RESEARCH.
- It does not claim these mechanisms are unique to credit reporting or are not
  already solved by existing software products — that research is a later step.

---

## 13. Verification instructions

To reproduce this sampling run:
1. Confirm `curl` is on PATH (`which curl`)
2. Run `python -m pytest -q` — all tests must pass (≥114)
3. Run `python -m core.pipeline --limit 100` (three times)
4. Compare run index entries: `cat data/exports/run_index.json`
5. Run cross-run comparison:
   ```python
   from core.cross_run_analysis import load_and_compare_last_n_runs, write_cross_run_report
   comp = load_and_compare_last_n_runs(3)
   write_cross_run_report(comp, 'analysis/comparison.md')
   ```
6. Build archive: `python -m tools.build_study_archive --latest`
7. Verify: `cd study_archives/<archive_dir> && sha256sum -c checksums.txt`
