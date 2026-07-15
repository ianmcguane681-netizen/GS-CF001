---
name: Three-bucket mutation analysis
description: How cross_run_analysis.py splits raw CFPB record fields into three named buckets to avoid false-positive mutation alerts from volatile metadata.
---

## The rule

Raw CFPB records are split into three named field buckets before hashing for cross-run mutation detection:

1. **`CLASSIFICATION_INPUT_FIELDS`** — `complaint_what_happened`, `product`, `sub_product`, `issue`, `sub_issue`  
   These are the only fields the classifier reads. A hash change here is `classification_mutation_detected = True` (CRITICAL).

2. **`STABLE_BUSINESS_FIELDS`** — `company`, `state`, `zip_code`, `tags`, `submitted_via`, `has_narrative`, `date_received`, `complaint_id`  
   Not used in classification but expected to be stable. A hash change here is `business_mutation_detected = True` (WARNING).

3. **Volatile metadata** — everything else: `company_response`, `timely`, `date_sent_to_company`, `company_public_response`, `_retrieved_at`, `_retrieval_url`, `_access_method`, `_source_name`, `_cfpb_hit_id`, `_source_record_id`  
   CFPB updates these continuously between API pulls. Differences are `metadata_differs = True` (INFO). They **never** penalise `overall_stability`.

`mutation_detected` (summary field) = `classification_mutation_detected OR business_mutation_detected`. Metadata differences are excluded from this summary.

**Why:** The original implementation hashed the entire raw record. Every live CFPB pull returned different `company_response` and `_retrieved_at` values for the same complaint, causing 100/100 records to appear "mutated" on every run — making the mutation analysis useless. Splitting into buckets eliminates this false positive class entirely.

**How to apply:** When adding new fields to the raw CFPB record schema, classify each field into one of the three buckets before extending `CLASSIFICATION_INPUT_FIELDS` or `STABLE_BUSINESS_FIELDS`. Any field that CFPB may update after initial complaint submission (status fields, timestamps, response fields) belongs in the volatile bucket — never in the classification or business buckets.
