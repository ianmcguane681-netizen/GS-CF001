# Adversarial Methodology Audit — GS-CF001-C Evidence OS Pipeline

**Reviewer:** Read-only explore subagent (methodology-auditor)  
**Date:** 2026-07-15  
**Scope:** Evidence claims, Proof Gates, traceability, classification thresholds,
rejection logic, mutation analysis, remaining overstatement  
**Status:** Findings preserved verbatim. Primary agent response noted per finding.

---

## Executive Summary

- **CRITICAL — Mutation detection flawed**: `core/cross_run_analysis.py` hashes
  entire raw records including volatile administrative metadata (retrieval
  timestamps, company response dates), causing 100/100 false-positive mutation
  flags on stable data. **→ Fixed in this milestone.**
- **HIGH — Trivially-failing gates**: PG-09 through PG-13 are hardcoded `False`
  and cannot pass without pipeline code modification. Honest but obscures gate
  intent. **→ Documented below; not changed (intentional design gate).**
- **MEDIUM — Traceability fog**: Proof gate evaluator passes full evidence ID
  list to every gate regardless of relevance. Letter of traceability satisfied,
  spirit not. **→ Documented; future milestone work.**
- **MEDIUM — Majority-vote classification**: `_majority()` rule allows 49%
  misclassification of a finding's nature without warning. **→ Documented.**
- **LOW — SOFTWARE_ADDRESSABLE_TERMS breadth**: 8 keywords may miss
  software-addressable failure modes not using those specific terms.
  **→ Documented; in-scope for future expansion.**

---

## Finding Detail

### F-01 — CRITICAL: Mutation detection hashes volatile metadata

**File:** `core/cross_run_analysis.py` line 205  
**Severity:** CRITICAL  
**Description:** `record_content_by_id` hashes the entire `rec` dict via
`json.dumps(rec, sort_keys=True)`. CFPB raw records include volatile fields
(`_retrieved_at`, `date_sent_to_company`, `company_response`, `timely`,
`company_public_response`) that the CFPB updates live. This caused 100/100
records to be flagged as mutated in the Milestone 3 cross-run report, rendering
the mutation analysis meaningless.  
**Fix:** Split content hashing into three named buckets:
- `classification_content_by_id` — fields the classifier actually reads
  (`complaint_what_happened`, `product`, `sub_product`, `issue`, `sub_issue`)
- `business_content_by_id` — stable CFPB source fields not used in classification
  (`company`, `state`, `zip_code`, `tags`, `submitted_via`, `has_narrative`,
  `date_received`)
- Volatile metadata (`_retrieved_at`, `company_response`, `timely`,
  `date_sent_to_company`, `company_public_response`, `_retrieval_url`, etc.)
  noted as expected-to-differ and not counted as a stability issue.

**Primary agent response:** Fixed. `CrossRunComparison` now carries
`classification_mutation_detected`, `classification_mutation_details`,
`business_mutation_detected`, `business_mutation_details`, `metadata_differs`.
Overall stability scoring penalises only `classification_mutation_detected`.

---

### F-02 — HIGH: PG-09 through PG-13 are trivially hardcoded False

**File:** `proof_gates/evaluator.py`  
**Severity:** HIGH  
**Description:** Gates PG-09 (Buyer Clarity), PG-10 (Measurable Cost), PG-11
(Competitive Landscape), PG-12 (Non-Software Alternatives), PG-13 (Commercial
Signal) are hardcoded to `FAIL`/`WEAK` status with `constrains_max_verdict=False`.
They cannot pass regardless of data volume.  
**Primary agent response:** This is intentional design — these gates guard
commercial evidence that CFPB-only data cannot supply. They are not data-driven
because no evidence pipeline stage currently produces the inputs they would
need. They are honest signal: until buyer research, unit economics, and
competitive assessment are added as pipeline stages, these gates should remain
FAIL. Changing them would be overstatement. **Not changed.**

---

### F-03 — MEDIUM: Traceability fog — gates receive full evidence ID list

**File:** `proof_gates/evaluator.py` (PG-01, PG-04 and others)  
**Severity:** MEDIUM  
**Description:** Several gates pass the full `evidence_ids` list from all
verified evidence, even when the gate assesses only a subset of that evidence
(e.g., PG-04 assesses mechanism consistency, not all individual evidence items).
This satisfies the letter of traceability (every decision has evidence IDs) but
not the spirit (which evidence items specifically drove this gate?).  
**Primary agent response:** Acknowledged. Scoped to a future milestone. The
current traceability model is per-finding and per-mechanism rather than
per-gate-per-evidence-item. Fixing it requires evaluating which evidence IDs are
gate-relevant at evaluation time, which is a non-trivial refactor of the gate
evaluator interface. **Not changed in this milestone; documented here.**

---

### F-04 — MEDIUM: Majority-vote classification allows 49% signal discard

**File:** `findings/mechanism_classifier.py`  
**Severity:** MEDIUM  
**Description:** `_majority(items, key)` returns True if `sum(key(i) for i in
items) / len(items) >= 0.5`. A finding with 49% software-addressable items is
classified as `non_software_problem`. No warning is emitted about borderline
votes.  
**Recommended fix:** Emit a `borderline_note` in the classification when the
majority vote is within 10 percentage points of 0.5 (i.e., 40%–60% range), so
reviewers know the classification is sensitive to small changes in evidence.  
**Primary agent response:** Acknowledged. Adding `borderline_note` to
`MechanismClassification` is low-risk and useful for auditability. **Fixed in
this milestone.**

---

### F-05 — LOW: SOFTWARE_ADDRESSABLE_TERMS may miss valid signals

**File:** `verification/rules.py` lines 48–57  
**Severity:** LOW  
**Description:** Eight terms (`dispute`, `investigation`, `document`, `proof`,
`communication`, `response`, `timeline`, `resolution`) may miss software-
addressable failure modes that use different vocabulary (e.g., "upload",
"portal", "workflow", "automated", "case management"). Complaints that describe
a process breakdown without using these exact words will be misclassified as
`non_software_problem`.  
**Primary agent response:** Acknowledged. Expanding the term list requires
careful testing to avoid false positives (marking non-software complaints as
software-addressable). Deferred to a future milestone with its own evidence
analysis. **Not changed; documented here.**

---

### F-06 — LOW: repeated_signal susceptible to sample size

**File:** `verification/classifier.py`  
**Severity:** LOW  
**Description:** `repeated_signal=True` is set when a mechanism appears ≥2 times
in the run. With a 100-record pull, a globally common mechanism might appear
only once in the sample — yielding `repeated_signal=False` not because the
pattern is rare but because the sample is small.  
**Primary agent response:** Acknowledged. The sampling design document notes
this: 100 records is not a statistical sample. The repeated-signal threshold
is intentionally conservative. **Not changed.**

---

## Accepted Conclusions

The auditor reviewed the following and found them sound:

- **Evidence Ceiling (PG-15/PG-16):** Robustly implemented and deterministic.
  A second source family is correctly required before any stronger verdict.
- **Trigger-process-failure mechanism taxonomy:** Consistently applied across
  classifier, ODR, tests, and archive outputs.
- **No AI in decisions:** All ODR, finding, and gate decisions are deterministic.
  No probabilistic model influences any output.
- **CFPB complaint caveat language:** Wording in reasoning chains, ceiling notes,
  and category labels correctly describes CFPB data as "unverified consumer
  allegations" throughout. No overstatement found in Python string literals.
- **Correction 5 (software_addressable gate removal):** Correctly implemented.
  `non_software_problem` findings now reach the ODR.

---

## Primary Agent Actions Taken This Milestone

| Finding | Action |
|---|---|
| F-01 CRITICAL mutation detection | Fixed — three-bucket field separation |
| F-02 HIGH trivially-failing gates | Documented — intentional design, not changed |
| F-03 MEDIUM traceability fog | Documented — future milestone |
| F-04 MEDIUM majority-vote borderline | Fixed — borderline_note added |
| F-05 LOW term list breadth | Documented — future milestone |
| F-06 LOW repeated_signal sample size | Documented — sampling design caveat |
