# Source evaluation — adjudicated findings

**Date:** 2026-07-26
**Question:** can this study obtain adjudicated findings — a judgment, consent
order, or examination finding — establishing that an alleged FCRA reinvestigation
failure actually occurred?
**Answer:** located, not yet obtainable. One candidate is viable and blocked on a
free API credential. Three are rejected.

## Why this was asked

The review board's open SEV-2 (`FND3-SR-001`) found:

> Complaints are consumer allegations to a regulator and filings are claims put to
> a court. Two independent forums now allege the same mechanism, which establishes
> independence, but neither establishes that the alleged failures occurred.

with the accepted remediation: *require a judgment, consent order or examination
finding before asserting the failure occurred.*

Sources were probed before any connector was designed. Every status code below was
observed on 2026-07-26 and is reproducible from
`source_evaluation_adjudicated_findings.json`.

## Candidates

### 1. CourtListener opinions — VIABLE, BLOCKED ON CREDENTIAL

| Probe | Result |
| --- | --- |
| `search/?type=o` (unauthenticated) | HTTP 200 — 402 published opinions for `"Fair Credit Reporting Act" reinvestigation` |
| `clusters/` | HTTP 401 |
| `opinions/{id}/` | HTTP 401 |

The records are real and directly on point: published federal appellate and
district opinions naming Experian, Equifax and TransUnion as respondents.

Two things block admission, and both are the same problem — the fields that carry
legal meaning are behind authentication:

1. **Statutory admission cannot be verified locally.** The RECAP connector admits a
   docket by checking structured metadata (`cause` = `15:1681 Fair Credit Reporting
   Act`, verified live at 12/12 rows). The opinion search returns `suitNature` as an
   empty string, and opinion snippets do not contain the statutory citation.
   Admission would rest entirely on the search index's own full-text match, with no
   check this repository could perform or reproduce.
2. **Disposition cannot be classified.** `posture`, `procedural_history` and
   `syllabus` are empty strings on every row of the free endpoint. CourtListener's
   structured `disposition` field lives on the cluster record, which is 401.

Inferring disposition from opinion prose was considered and rejected. This
repository already refuses keyword guessing where structured metadata exists, and
posture is exactly where guessing does the most damage — an opinion denying a
motion to dismiss *assumes the allegations are true*, so misreading one would
convert an allegation into a finding with a judge's name attached.

**Unblocked by:** a CourtListener API token (free, issued for research use). This is
a human registration step.

### 2. Federal Register API — REJECTED, WRONG INSTRUMENT

HTTP 200, unauthenticated, well documented, 1,248 documents matching "Fair Credit
Reporting Act". It is nonetheless the wrong source: the Federal Register is a
**rulemaking gazette, not an adjudication register.** The FCRA results are rules,
proposed rules, regulatory agendas and Paperwork Reduction Act notices. The consent
orders it does carry are FTC *proposed* orders published for comment — titled
"Analysis of Proposed Consent Order To Aid Public Comment" — which are not final
adjudications. Admitting those would have reproduced the board's finding in a new
source rather than answering it.

### 3. FTC Legal Library — REJECTED, PUBLISHER REFUSES AUTOMATED ACCESS

`legal-library/browse/cases-proceedings` returns HTTP 403. The candidate API path
returns a block page: *"The request resembles an abusive automated request."* The
publisher is explicitly refusing automated retrieval, so this source is not
available to this study by any route it would be legitimate to take.

### 4. CFPB enforcement actions — REJECTED, NO MACHINE-READABLE FEED

The enforcement actions index is HTTP 200 but `text/html` only; `?format=json`
returns HTML, and two candidate JSON paths return 404. Independently of the format
problem, CFPB enforcement shares a publisher with the CFPB complaint family already
in the study, so its independence would need to be argued rather than assumed.

## What was built instead

The remediation the board accepted is a **requirement**, and a requirement is a
control, not a dataset. That control was missing entirely and has been built:

- `core/adjudication.py` — evidentiary standing (`ALLEGED` / `ADJUDICATED`) as an
  axis orthogonal to source family, with a deterministic posture and direction
  classifier that defaults to establishing nothing.
- `PG-09` and `PG-13` were pinned to `FAIL`. A pinned constant enforces nothing —
  it cannot distinguish a study that lacks adjudicated evidence from one that has
  it, and flipping the constant would have passed the gate silently. Both now
  compute from evidentiary standing.
- `Finding.occurrence_established` and `StudyVerdict.occurrence_established_count`
  report the two axes separately, so "independently alleged" can never be read off
  the page as "established".

On the live two-family run, PG-09 now fails with a specific reason —
`corroborated=0; adjudicated=0; establishing occurrence=0` — rather than by
definition.

## Standing state of the study

| Axis | Status |
| --- | --- |
| Independent source families | 2 — CFPB complaints, federal court records |
| Adjudicated findings of occurrence | 0 |
| Maximum permitted verdict | CONTINUE RESEARCH |
