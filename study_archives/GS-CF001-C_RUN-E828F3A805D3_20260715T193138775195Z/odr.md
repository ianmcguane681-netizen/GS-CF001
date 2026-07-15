# Opportunity Decision Register — GS-CF001-C

**Run ID:** `RUN-E828F3A805D3`  
**Generated:** 2026-07-15T19:31:38+00:00  
**Evidence Ceiling:** **CONTINUE RESEARCH** (enforced — CFPB single source family)

---

## Methodology note

> All decisions in this ODR are produced by deterministic pipeline rules. No AI model was consulted for any classification or decision. The Evidence Ceiling (CONTINUE RESEARCH) is enforced by Proof Gates PG-15 and PG-16 and cannot be overridden. CFPB complaint data is a single source family. CFPB complaints are unverified consumer allegations and do not independently establish operational reality, software addressability, or commercial viability. Advancing beyond CONTINUE RESEARCH requires independent evidence from multiple research streams.

---

## Summary

| | Count |
|---|---|
| Total ODR entries | 2 |
| CONTINUE_RESEARCH | 1 |
| REJECTED | 1 |

## Decision table

| ODR ID | Mechanism | Classification | Evidence | Companies | Decision |
|---|---|---|---|---|---|
| `ODR-BD0605559C37` | furnisher_tradeline_data_error_persistence | Non-software problem | 76 | 6 | **REJECTED** |
| `ODR-B042707329BF` | bureau_dispute_reinvestigation_failure | Repeated complaint signal (operational reality unverified) | 3 | 3 | **CONTINUE_RESEARCH** |

---

### ODR-BD0605559C37 — furnisher_tradeline_data_error_persistence

| Field | Value |
|---|---|
| Classification | Non-software problem |
| Decision status | **REJECTED** |
| Finding ID | `FND-A401039F8FD9` |
| Opportunity ID | `OPP-32FB43B75268` |
| Evidence count | 76 |
| Company count | 6 |
| Companies | DISCOVER BANK, EQUIFAX, INC., Experian Information Solutions Inc., Lendmark Financial Services, Spring Oaks Capital, LLC, TRANSUNION INTERMEDIATE HOLDINGS, INC. |
| Component hypothesis | Consumer finance workflow component |
| Buyer clarity | weak |
| Commercial relevance | unproven |
| Component reusability | plausible |

**Evidence references:**

- `EVD-1B15F7E9E770`
- `EVD-265859017342`
- `EVD-21D52B16ADDC`
- `EVD-ACD32FFDFCDD`
- `EVD-52E5A0546D65`
- `EVD-95B7FCB98730`
- `EVD-405AD2EAA221`
- `EVD-8C129CA70096`
- `EVD-024F0E709E54`
- `EVD-4A1452A3D6F8`
- `EVD-CEB640150D56`
- `EVD-FF1FE1DC7B5F`
- `EVD-BB6F4DE78C75`
- `EVD-FC6F822AA94F`
- `EVD-F544DFAFE8B1`
- `EVD-C09D67E6AE54`
- `EVD-C57D1BD816BE`
- `EVD-883945B0D4C4`
- `EVD-82D16A5A6F2C`
- `EVD-540C63385B5D`
- `EVD-9E8E9A38509F`
- `EVD-391A5D59906F`
- `EVD-ABCE52121B75`
- `EVD-A7AE83853240`
- `EVD-2EFA96E07268`
- `EVD-4FAAF6A30166`
- `EVD-CC5AFA35021A`
- `EVD-8FCCAFCF8E6F`
- `EVD-7C4A08ADA752`
- `EVD-10BEF9293973`
- `EVD-AA5ED9C0BDDD`
- `EVD-C8052097D785`
- `EVD-D1F1E31B8ED6`
- `EVD-66DF65AA38A3`
- `EVD-A571D4D19863`
- `EVD-B0907A7BBCC4`
- `EVD-2B9AA678CCDF`
- `EVD-51C98B600601`
- `EVD-E45C7987792D`
- `EVD-4AB9020E4980`
- `EVD-3958FAEB61B7`
- `EVD-80C9EBA44DAD`
- `EVD-5BE5A6931781`
- `EVD-5971FE399A07`
- `EVD-59D71CA67C71`
- `EVD-EA0A555C87E3`
- `EVD-C7D539B44529`
- `EVD-CC82982F50F7`
- `EVD-3DC6059109B2`
- `EVD-8912A51205E2`
- `EVD-64232CAA085D`
- `EVD-3C32E24A2C50`
- `EVD-C1D3E6954C1E`
- `EVD-850E3D44A0E5`
- `EVD-1849321BA0BE`
- `EVD-A1EAD466941A`
- `EVD-3C063A95E72E`
- `EVD-1A79ADDDEEAB`
- `EVD-4F4E98125530`
- `EVD-B1F979EBD9E5`
- `EVD-8BEF1B5C8E22`
- `EVD-DC0DDD03B2F2`
- `EVD-A948F506461A`
- `EVD-75E747DADD97`
- `EVD-5B2372505AB0`
- `EVD-7908FF58C945`
- `EVD-F997CDE88DDA`
- `EVD-6CD97944EC80`
- `EVD-D1922097E007`
- `EVD-1D8A96AD603C`
- `EVD-60CCEE89837E`
- `EVD-EE3C86459131`
- `EVD-9A0FD26515B5`
- `EVD-3970FD92D783`
- `EVD-12110DE2E5DB`
- `EVD-DFBD0FC91450`

**Decision rationale:**

- Finding FND-A401039F8FD9: majority operational=True (76/76 items).
- However, fewer than half of evidence items have software_addressable=True.
- The failure mode is more plausibly addressed by policy change, regulatory compliance, staffing adjustment, legal action, or vendor-contract modification rather than a software workflow component.
- Classified as non_software_problem.
- Commercial hypothesis: 'Consumer finance workflow component' — buyer_clarity=weak, commercial_relevance=unproven, reusability=plausible.
- Decision: REJECTED. The mechanism does not meet the threshold for commercial investigation under the current evidence base.

**Required to advance decision status:**

- majority of evidence items must contain SOFTWARE_ADDRESSABLE_TERMS matches
- mechanism must indicate a workflow gap addressable by software (not a legal or regulatory compliance gap)

**Evidence ceiling note:**

> Evidence ceiling: CONTINUE RESEARCH. CFPB complaint data is a single source family. Proof Gates PG-15 and PG-16 cap the maximum verdict at CONTINUE RESEARCH regardless of record volume. CFPB complaints are unverified consumer allegations and do not independently confirm operational failure, software addressability, or commercial viability. Multiple independent research streams are required before any of those conclusions can be drawn.

---

### ODR-B042707329BF — bureau_dispute_reinvestigation_failure

| Field | Value |
|---|---|
| Classification | Repeated complaint signal (operational reality unverified) |
| Decision status | **CONTINUE_RESEARCH** |
| Finding ID | `FND-B08448E45182` |
| Opportunity ID | `OPP-35B0080268E3` |
| Evidence count | 3 |
| Company count | 3 |
| Companies | EQUIFAX, INC., Experian Information Solutions Inc., TRANSUNION INTERMEDIATE HOLDINGS, INC. |
| Component hypothesis | Consumer finance workflow component |
| Buyer clarity | weak |
| Commercial relevance | unproven |
| Component reusability | plausible |

**Evidence references:**

- `EVD-0359C390CC60`
- `EVD-E8859085410F`
- `EVD-7DA79EC3CA44`

**Decision rationale:**

- Finding FND-B08448E45182: evidence_count=3 ≥ 3, company_count=3 ≥ 2, status=finding_supported_cfpb_only.
- All verified evidence items have repeated_signal=True — the same mechanism appears across multiple complaints.
- Operational and software-addressable criteria met within CFPB data.
- IMPORTANT: CFPB complaints are unverified consumer allegations. This classification does NOT confirm operational reality, software addressability of the root cause, or commercial viability.
- Evidence ceiling enforced: CONTINUE RESEARCH (PG-15 source_families=1, PG-16 ceiling applied).
- Classified as repeated_complaint_signal.
- Commercial hypothesis: 'Consumer finance workflow component' — buyer_clarity=weak, commercial_relevance=unproven, reusability=plausible.
- Decision: CONTINUE_RESEARCH. Evidence ceiling enforced. CFPB complaint data establishes a complaint signal only — not a verified operational failure or commercial opportunity. Multiple independent research streams must be completed before this can advance.

**Required to advance decision status:**

- Independent corroboration of operational reality from a non-CFPB source (regulatory findings, enforcement actions, judicial records, audit reports, or company-examination evidence) confirming the mechanism exists as described.
- Named buyer persona with confirmed purchasing authority, demonstrated budget cycle, and organisational context (role, company size, purchase trigger).
- Measurable operational or financial cost attributable to the mechanism (documented dollar amount, labour hours lost, SLA breach rate, or equivalent quantifiable harm — not inferred from complaint volume).
- Competitive landscape assessment: named existing solutions, their current maturity level, and a sourced explanation of why they fail or are unavailable to the identified buyer.
- Non-software alternatives assessment: explicit evaluation of why process change, staffing, regulatory compliance, or vendor-contract modification cannot solve this more cost-effectively than software.
- Addressable market size estimate with sourced revenue-potential basis (not a top-down TAM — a bottoms-up count of named buyers with stated willingness to pay or comparable purchase evidence).
- Commercial signal: at least one instance of stated or implied willingness to pay, a deal-cycle or procurement reference, or a comparable competitive sale.

**Evidence ceiling note:**

> Evidence ceiling: CONTINUE RESEARCH. CFPB complaint data is a single source family. Proof Gates PG-15 and PG-16 cap the maximum verdict at CONTINUE RESEARCH regardless of record volume. CFPB complaints are unverified consumer allegations and do not independently confirm operational failure, software addressability, or commercial viability. Multiple independent research streams are required before any of those conclusions can be drawn.
