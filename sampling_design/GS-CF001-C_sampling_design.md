# GS-CF001-C Sampling Design — 100-Record Live CFPB Pull

**Version:** SD-001  
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
- `OPERATIONAL_TERMS` — presence signals an operational complaint
- `SOFTWARE_ADDRESSABLE_TERMS` — presence signals a software-addressable mechanism
- `MECHANISM_RULES` — deterministic priority-ordered rules assign one of five
  mechanism labels (or the default `credit_reporting_dispute_handling`)

---

## 7. Mechanism classification criteria

Each identified finding is classified into one of six categories by
`findings/mechanism_classifier.py` using deterministic rules only:

| Category | Rules |
|---|---|
| `noise` | evidence_count < 2 or no verified_candidate items |
| `non_operational_problem` | Has evidence; operational=False for majority of verified items |
| `non_software_problem` | Operational evidence present; software_addressable=False for majority |
| `commercially_weak` | Operational + software-addressable; company_count < 2 or evidence_count < 3 |
| `verified_pain` | evidence_count ≥ 3, company_count ≥ 2, operational, software-addressable, status=finding_supported_cfpb_only |
| `candidate_needs_corroboration` | All verified_pain criteria + all evidence items have repeated_signal=True |

---

## 8. Evidence Ceiling enforcement

CFPB data is a single source family. Proof Gates PG-15 (Source Independence)
and PG-16 (Evidence Ceiling Compliance) enforce a hard ceiling of
`CONTINUE RESEARCH` regardless of how many records are retrieved, how many
mechanisms are identified, or how many companies are observed.

This ceiling is a methodology rule, not an access limitation. It applies even
if 10,000 records are retrieved. The ceiling can only be removed by adding a
second independent source family (regulatory, enforcement, judicial, audit, or
company-examination evidence). That is not part of this milestone.

---

## 9. Opportunity Decision Register (ODR)

The ODR is produced by `core/opportunity_decision_register.py` for every run.
Each entry records: mechanism, classification, evidence references, companies,
evidence count, commercial assessment, decision status, Evidence Ceiling note,
and full deterministic reasoning chain. No AI is used in any ODR decision.
Decisions are derived entirely from finding status, mechanism classification
rules, and proof gate outputs.

---

## 10. What this design does not claim

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

## 11. Verification instructions

To reproduce this sampling run:
1. Confirm `curl` is on PATH (`which curl`)
2. Run `python -m pytest -q` — all tests must pass
3. Run `python -m core.pipeline --limit 100` (three times)
4. Compare run index entries: `cat data/exports/run_index.json`
5. Build archive: `python -m tools.build_study_archive --latest`
6. Verify: `cd study_archives/<archive_dir> && sha256sum -c checksums.txt`
