# GS-CF001-C Traceable Verdict Report

Generated: 2026-07-27T00:25:38Z

Unconstrained Assessment: CONTINUE RESEARCH
Evidence Ceiling: BUILD CANDIDATE
Evidence Ceiling Reason: At least two independent source families are present.
Final Verdict: CONTINUE RESEARCH
Required Next Evidence: none

## Source Reliability
- `CFPB-CCD-001` CFPB Consumer Complaint Database; family `CFPB complaints`; method `official_cfpb_search_api`.
  - Representativeness warning: CFPB complaint records are not a statistically representative market sample.
  - Data completeness warning: Some CFPB fields may be missing, withheld, amended, or unavailable in public data.
  - Verification constraints: CFPB complaint repetition can support a repeated complaint signal.; CFPB alone cannot independently corroborate the underlying allegation.; CFPB alone cannot establish a BUILD CANDIDATE verdict.; Independent source evidence is required for stronger commercial conclusions.
  - Prohibited inferences: Do not infer that alleged failures definitely occurred.; Do not infer market prevalence from complaint volume alone.; Do not infer that software is the best intervention.; Do not produce BUILD CANDIDATE from CFPB data alone.
- `COURTLISTENER-FCRA-001` CourtListener Federal Court Records (RECAP); family `Federal court records`; method `courtlistener_search_api`.
  - Representativeness warning: Federal dockets are not a statistically representative sample of the market.
  - Data completeness warning: RECAP is a partial mirror of PACER; absence of a case proves nothing.
  - Verification constraints: Repeated statutory causes can support a repeated alleged mechanism.; Court records alone do not establish that an alleged failure occurred.; A judgment or documented finding is required before asserting proven failure.
  - Prohibited inferences: Do not infer that alleged failures definitely occurred.; Do not treat a settlement as proof of wrongdoing.; Do not infer market prevalence from case volume alone.
- `FJC-IDB-FCRA-001` FJC Integrated Database (federal civil case outcomes); family `Federal court records`; method `fjc_integrated_database_api`.
  - Representativeness warning: Cases reaching a merits judgment are a small and unrepresentative fraction: most FCRA cases settle.
  - Data completeness warning: Recent cases carry null outcome codes until a subsequent dataset load.
  - Verification constraints: A merits judgment for the plaintiff establishes that a violation was found.; Absence of a coded judgment never means a case was decided either way.; A single case establishes occurrence in that case, never market prevalence.
  - Prohibited inferences: Do not treat a settlement or voluntary dismissal as proof of wrongdoing.; Do not treat a default judgment as a finding on the merits.; Do not infer market prevalence from adjudicated case counts.; Do not count this source toward independent source families.

## Access Diagnostics
- `ADIAG-77C380169706` method `official_cfpb_search_api` endpoint `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?size=8&product=Credit+reporting+or+other+personal+consumer+reports` status `200`; interpretation: Official CFPB search API returned parseable JSON.
- `ADIAG-2E4C44CE7B1E` method `courtlistener_search_api` endpoint `https://www.courtlistener.com/api/rest/v4/search/?q=%22Fair+Credit+Reporting+Act%22+reinvestigation&type=r&order_by=dateFiled+desc` status `200`; interpretation: CourtListener search API returned parseable JSON.
- `ADIAG-34D610B237FA` method `fjc_integrated_database_api` endpoint `https://www.courtlistener.com/api/rest/v4/fjc-integrated-database/?title=15&section__startswith=1681&disposition__in=5%2C6%2C7%2C8%2C9&judgment__in=1%2C2&page_size=8` status `200`; interpretation: FJC Integrated Database returned parseable JSON.

## Evidence
- `EVD-0B9218158E5F` from candidate `CAN-6E938D214D32`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-8404BBB05A6C` from candidate `CAN-CEEE7F9664BC`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-894E85746148` from candidate `CAN-73F4C2E957C4`: verified_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-4FEAB650BE17` from candidate `CAN-44CDB6B487C6`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-B3AADFA13B4F` from candidate `CAN-52A5E81F615F`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-511C0E1ED74A` from candidate `CAN-F9EFAC631736`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-819109845E20` from candidate `CAN-12087AB422C0`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-35A67BECCAA2` from candidate `CAN-C7997D40E75C`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-3EF8503D7273` from candidate `CAN-C4B712D11D4B`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-F6068E1F7066` from candidate `CAN-F510B71FBF52`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-AE7C3684E244` from candidate `CAN-6D5DC81B368F`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-38B5E7D991C5` from candidate `CAN-ED5C46BA8AA9`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-605833ABF3D7` from candidate `CAN-8249A2C47904`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-EF15C1E99C3A` from candidate `CAN-E4C8015622EC`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-01348CCBD196` from candidate `CAN-5F85EB0AD31B`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-8613CFA03C92` from candidate `CAN-8E5B4D4839C8`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-1081F20BDE13` from candidate `CAN-DA634A1BF095`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-76DCC3EFB5E3` from candidate `CAN-B768CC26711C`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-7BB361FF4CD6` from candidate `CAN-DA780A7329F3`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-8465BDF1E349` from candidate `CAN-BD68DFFCF625`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-2251217C0121` from candidate `CAN-66B976528A2C`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-3D23A47CFD1A` from candidate `CAN-1C0DD0545A1E`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-C6AF231EAA80` from candidate `CAN-021641350D02`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.
- `EVD-97E4AEE416A2` from candidate `CAN-B6B3E69CDA1D`: rejected_candidate; mechanism `unclassified_credit_reporting_complaint`.

## Findings
- `FND-06F9DD9346D2`: needs_more_evidence; supported by `EVD-894E85746148`; missing: an identified operational mechanism, minimum 3 verified evidence items, evidence across at least 2 companies, independent non-CFPB corroboration.

## Opportunity Assessment
- `OPP-65EF9497DB46`: unproven; component `Unclassified mechanism - no supported component yet`; supported by `EVD-894E85746148`; missing: an identified operational mechanism, minimum 3 verified evidence items, evidence across at least 2 companies, independent non-CFPB corroboration, supported finding, buyer pattern across multiple companies, existing solution maturity research, buyer willingness evidence, commercial urgency evidence.

## Proof Gates
- PG-01 Source Authenticity: PASS; threshold `Source reliability assessment present`; observed `True`; confidence 1.0; evidence no evidence; missing: none; constrains max verdict: False; next action: Create or review source reliability assessment.
- PG-02 Raw Record Preservation: PASS; threshold `Raw retrieval artifact or diagnostic exists`; observed `True`; confidence 1.0; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: none; constrains max verdict: False; next action: Do not normalise until raw retrieval or access failure is preserved.
- PG-03 Normalisation Integrity: PASS; threshold `Normalised candidate records exist`; observed `True`; confidence 0.9; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: none; constrains max verdict: False; next action: Resolve source access or normalisation before verification.
- PG-04 Study Classification Integrity: PASS; threshold `All evidence maps to GS-CF001-C`; observed `True`; confidence 0.9; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: none; constrains max verdict: False; next action: Classify retrieved records into the implemented study only.
- PG-05 Repetition: FAIL; threshold `Minimum repeated mechanism finding`; observed `False`; confidence 0.0; evidence `EVD-894E85746148`; missing: repeated mechanism across CFPB records; constrains max verdict: False; next action: Collect more CFPB records until repeated mechanisms are present.
- PG-06 Cross-Company Evidence: FAIL; threshold `At least 2 company references`; observed `1`; confidence 0.0; evidence `EVD-894E85746148`; missing: evidence across at least 2 companies; constrains max verdict: False; next action: Collect records spanning multiple companies.
- PG-07 Operational Specificity: FAIL; threshold `Finding includes operational mechanism definition`; observed `False`; confidence 0.0; evidence `EVD-894E85746148`; missing: operational mechanism definition; constrains max verdict: False; next action: Extract trigger, step, failure mode, consequence, and expected process.
- PG-08 Software-Addressability: WEAK; threshold `Opportunity assessment exists`; observed `False`; confidence 0.2; evidence `EVD-894E85746148`; missing: software-addressability evidence; constrains max verdict: False; next action: Assess workflow detail and non-software alternatives.
- PG-09 Independent Corroboration: FAIL; threshold `At least 1 adjudicated finding of occurrence, on a mechanism independently alleged by another source family`; observed `corroborated=0; adjudicated=8; establishing occurrence=0`; confidence 0.0; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: a judgment, consent order, or examination finding resolving the mechanism against a respondent; constrains max verdict: True; next action: Retrieve adjudicated dispositions before BUILD CANDIDATE.
- PG-10 Buyer Clarity: FAIL; threshold `Confirmed buyer evidence`; observed `unverified`; confidence 0.0; evidence `EVD-894E85746148`; missing: confirmed buyer, budget owner, procurement context; constrains max verdict: False; next action: Research buyer role after independent corroboration.
- PG-11 Existing Solution Assessment: WEAK; threshold `At least 1 incumbent assessed for maturity, not merely identified`; observed `identified=5; assessed=0; publishing a price=0`; confidence 0.3; evidence `PRC-CREDIT-REPAIR-CLOUD`, `PRC-DISPUTEFOX`, `PRC-SCORECEO`, `PRC-CLIENT-DISPUTE-MANAGER`, `PRC-DISPUTESUITE`; missing: comparative assessment of at least one incumbent: strengths, weaknesses or differentiation; constrains max verdict: False; next action: Assess an identified incumbent rather than only listing it.
- PG-12 Commercial Relevance: FAIL; threshold `At least 1 budget-holding buyer stating willingness`; observed `buyer records=0; budget-holding and willing=0`; confidence 0.0; evidence no evidence; missing: a buyer who controls a budget stating what they would pay for; constrains max verdict: False; next action: Record a buyer conversation; no dataset answers this.
- PG-13 Counter-Evidence: WEAK; threshold `At least 1 adjudicated disposition resolving the mechanism in a respondent's favour`; observed `contradicting=0 of 8 adjudicated`; confidence 0.3; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: adjudicated dispositions decided in a respondent's favour; constrains max verdict: False; next action: Retrieve dispositions in both directions, not only those that confirm.
- PG-14 Reproducibility: PASS; threshold `Run preserves artifacts and diagnostics`; observed `True`; confidence 0.8; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: none; constrains max verdict: False; next action: Preserve run manifest, diagnostics, and raw official records.
- PG-15 Source Independence: PASS; threshold `Independent source family count >= 2`; observed `2`; confidence 1.0; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: none; constrains max verdict: True; next action: Add independent corroborating source family.
- PG-16 Evidence Ceiling Compliance: PASS; threshold `If source families < 2, maximum verdict is CONTINUE RESEARCH`; observed `source families=2`; confidence 1.0; evidence `EVD-0B9218158E5F`, `EVD-8404BBB05A6C`, `EVD-894E85746148`, `EVD-4FEAB650BE17`, `EVD-B3AADFA13B4F`, `EVD-511C0E1ED74A`, `EVD-819109845E20`, `EVD-35A67BECCAA2`, `EVD-3EF8503D7273`, `EVD-F6068E1F7066`, `EVD-AE7C3684E244`, `EVD-38B5E7D991C5`, `EVD-605833ABF3D7`, `EVD-EF15C1E99C3A`, `EVD-01348CCBD196`, `EVD-8613CFA03C92`, `EVD-1081F20BDE13`, `EVD-76DCC3EFB5E3`, `EVD-7BB361FF4CD6`, `EVD-8465BDF1E349`, `EVD-2251217C0121`, `EVD-3D23A47CFD1A`, `EVD-C6AF231EAA80`, `EVD-97E4AEE416A2`; missing: none; constrains max verdict: False; next action: Apply deterministic ceiling before final verdict.

## Verdict Reasoning
- Verdict generated from deterministic proof gate statuses.
- No positive build decision is allowed unless every proof gate passes.
- Proof gates not passing: PG-05, PG-06, PG-07, PG-08, PG-09, PG-10, PG-11, PG-12, PG-13.
- Gates constraining the maximum verdict: PG-09, PG-15.
- Evidence ceiling applied after unconstrained assessment.

## Run Manifest
- Run ID: `RUN-6312B475553F`
- Code commit: `5bce4834267f9d31b0bced1f2f5e42ac2ca7d206`
- Methodology version: `PROVENA-EOS-METHOD-001`
- Source access method: `official_cfpb_search_api`
- AI model configuration: AI disabled; deterministic rules only.
