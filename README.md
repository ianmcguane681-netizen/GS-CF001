# GS-CF001

Golden Study - Consumer Finance 001.

This repository is a research proof system. It is not a product, dashboard, demo, or analytics app.

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
-> Normalisation
-> Evidence Candidate
-> Verification
-> Finding
-> Opportunity Assessment
-> Proof Gates
-> Verdict
```

Every stage must preserve traceability. If a stage cannot justify itself with evidence, the study reports why and stops short of a positive conclusion.

## Current Source

Initial live source:

- CFPB Consumer Complaint Database

No other source is integrated yet.

## Run Tests

```powershell
python -m pytest -q
```

## Run Credit Reporting Proof

```powershell
python -m core.pipeline --limit 1
```

The run writes raw, processed, and report artifacts under `data/`.

