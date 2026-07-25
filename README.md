# GS-CF001

Golden Study - Consumer Finance 001.

This repository is a research proof system for Provena, an Evidence Operating System powered by AI.

It is not a product, dashboard, demo, or analytics app. The Evidence OS is the system of record. AI may assist analysis later, but evidence and deterministic Proof Gates remain the decision authority.

## Research Question

> Is there enough verified, repeated operational pain in U.S. consumer financial account servicing and complaint resolution to justify building one or more reusable workflow components?

## Initial Scope

Only `GS-CF001-C Credit Reporting Disputes` is implemented.

The remaining studies are definitions only:

- `GS-CF001-A` Mortgage Servicing
- `GS-CF001-B` Bank Account Servicing
- `GS-CF001-D` Debt Collection Communication
- `GS-CF001-E` Consumer Loan Servicing
- `GS-CF001-F` Payment & Transaction Disputes

## Methodology

CFPB complaint records are discovery material only. A complaint never automatically becomes a finding or opportunity.

Pipeline:

```text
Discovery
-> Source Record
-> Normalisation
-> Evidence Candidate
-> Verification within source
-> CFPB-limited Finding
-> Opportunity Assessment
-> Proof Gates
-> Verdict
```

Every stage must preserve traceability. If a stage cannot justify itself with evidence, the study reports why and stops short of a positive conclusion.

## Evidence Authority

Governing rule:

```text
AI may propose.
Evidence must prove.
Proof Gates must decide.
```

AI outputs, if introduced later, must be stored as analysis artifacts. They are never source evidence and cannot override deterministic gates.

## Evidence Ceiling

CFPB data alone can produce CFPB-supported, CFPB-limited findings.

CFPB data alone can never produce `BUILD CANDIDATE`.

Deterministic ceiling:

```text
IF independent source family count < 2
THEN maximum verdict = CONTINUE RESEARCH
```

Multiple CFPB complaint records remain one source family.

## Current Sources

Two independent source families are integrated:

- CFPB Consumer Complaint Database — `CFPB complaints`
- CourtListener federal court records (RECAP) — `Federal court records`

The CFPB connector separates the CFPB source from access methods:

- Official CFPB Search API adapter
- Official CFPB bulk download adapter
- Local official CFPB snapshot adapter

No scraping and no third-party mirrors are used.

### Federal court records

Federal dockets are a genuinely separate source family: different parties, a
different forum, and legal consequences attached. Admission is deterministic on
the statutory cause recorded by the court itself — a docket is mapped to this
study only where the claim arises under the Fair Credit Reporting Act
(15 U.S.C. 1681), never by keyword matching a case caption.

The evidential limits are deliberately narrow:

```text
A filed complaint is an allegation, not a finding of fact.
A settlement or dismissal is not an admission of liability.
```

Dockets therefore corroborate that an alleged mechanism recurs outside the CFPB,
and satisfy the independence requirement. They do not establish that any alleged
failure occurred. Docket metadata carries no consumer narrative, and a case
caption is never mined as though it were a first-hand account.

With both families present the deterministic evidence ceiling lifts:

```text
independent source family count >= 2
=> maximum verdict is no longer capped at CONTINUE RESEARCH
```

The verdict itself remains gated on the remaining proof gates, which continue to
require solution-maturity, commercial and counter-evidence research that is not
yet integrated.

## Reports and Artifacts

Each run writes file artifacts only:

- Raw source records or access failure diagnostics
- Source reliability assessment
- Normalised evidence candidates
- Verification artifacts
- Findings
- Opportunity assessments
- Proof Gate results
- Audit trail / evidence state transitions
- Markdown report
- JSON report
- Run manifest with checksums

Reports must be traceable to structured artifacts and methodology rules.

## Run Tests

```powershell
python -m pytest -q
```

## Run Credit Reporting Proof

```powershell
python -m core.pipeline --limit 3
```

The run writes raw, processed, and report artifacts under `data/`.

If CFPB access is blocked by the execution environment, the run writes an access diagnostic and stops short of normalisation instead of creating placeholder evidence.
