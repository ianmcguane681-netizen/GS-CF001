# Cross-Run Comparison Report

**Runs compared:** 3  
**Overall stability:** **stable**  

## Run IDs and timestamps

| # | Run ID | Timestamp | Verdict | Ceiling |
|---|---|---|---|---|
| 1 | `RUN-88AC9B5642A1` | `20260715T194949384451Z` | CONTINUE RESEARCH | CONTINUE RESEARCH |
| 2 | `RUN-AF098965780A` | `20260715T194955268616Z` | CONTINUE RESEARCH | CONTINUE RESEARCH |
| 3 | `RUN-6A31FC091937` | `20260715T195010440210Z` | CONTINUE RESEARCH | CONTINUE RESEARCH |

## Retrieval — count level

| Run # | Candidates |
|---|---|
| 1 | 100 |
| 2 | 100 |
| 3 | 100 |

**Retrieval stable (all > 0):** True  
> All 3 run(s) returned candidates (counts: [100, 100, 100]). Note: count equality does not imply record-set equality; see complaint-ID overlap analysis below.

## Complaint-ID overlap and equality

| Run # | ID-set hash (first 12) | Ordering hash (first 12) |
|---|---|---|
| 1 | `d53f15ecf378…` | `aa3f388dc863…` |
| 2 | `d53f15ecf378…` | `aa3f388dc863…` |
| 3 | `d53f15ecf378…` | `aa3f388dc863…` |

**Complaint IDs identical across all runs:** True  
**Jaccard similarity (min pairwise):** 1.0000  
**Ordering stable:** True  

> **ID overlap:** All 3 run(s) retrieved the exact same set of complaint IDs (set-hash: d53f15ecf378…). Record-set identity confirmed.
> **Ordering:** Complaint ordering is identical across all runs.

## Source mutation analysis (three-category breakdown)

Mutation is split into three named categories. Only classification-input mutations affect pipeline outputs. Volatile metadata differences are expected for live CFPB pulls and are never counted as a stability issue.

### 1. Classification-input mutation — ✅ NONE

Fields: `complaint_what_happened`, `product`, `sub_product`, `issue`, `sub_issue`  
Impact: **can alter mechanism assignment, operational flag, ODR outcome**  
Detected: **False**  

### 2. Stable-business-field mutation — ✅ NONE

Fields: `company`, `state`, `zip_code`, `tags`, `submitted_via`, `has_narrative`, `date_received`, `complaint_id`  
Impact: **unexpected; does not affect classification outputs**  
Detected: **False**  

### 3. Volatile-metadata differences — ℹ️ YES (expected)

Fields: `company_response`, `timely`, `date_sent_to_company`, `company_public_response`, `_retrieved_at`, `_retrieval_url`, `_access_method`, `_source_name`  
Impact: **none — these fields are not read by the classifier; differences are expected for live CFPB pulls**  
Records with metadata differences: **100**  
> 100 record(s) have volatile-metadata differences (company_response, timely, date_sent_to_company, _retrieved_at, etc.). This is EXPECTED for live CFPB pulls — the CFPB database updates these administrative fields continuously. Volatile metadata is NOT included in mutation_detected or stability scoring.

## Verdict and Evidence Ceiling

- Verdict consistent: **True** ({'CONTINUE RESEARCH'})
- Ceiling consistent: **True** ({'CONTINUE RESEARCH'})

## Mechanism distribution

- Common to all runs: ['bureau_dispute_reinvestigation_failure', 'furnisher_tradeline_data_error_persistence']
- Present in any run: ['bureau_dispute_reinvestigation_failure', 'furnisher_tradeline_data_error_persistence']
- Mechanism stable: **True**

- Run 1: ['bureau_dispute_reinvestigation_failure', 'furnisher_tradeline_data_error_persistence']
- Run 2: ['bureau_dispute_reinvestigation_failure', 'furnisher_tradeline_data_error_persistence']
- Run 3: ['bureau_dispute_reinvestigation_failure', 'furnisher_tradeline_data_error_persistence']

## Findings and opportunities

| Run # | Findings | Opportunities |
|---|---|---|
| 1 | 2 | 2 |
| 2 | 2 | 2 |
| 3 | 2 | 2 |

## Proof gate consistency

All gate statuses are consistent across all runs.

## Stability notes

- METADATA DIFFERENCES (INFO — not a stability issue): 100 record(s) have volatile-metadata changes (company_response, timely, date_sent_to_company, _retrieved_at). Expected for live CFPB pulls. Does not affect pipeline outputs.
- CEILING ENFORCED: CONTINUE RESEARCH in all runs — correct for single source family.
