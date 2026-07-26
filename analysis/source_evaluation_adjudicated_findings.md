# Source evaluation — adjudicated findings

**Date:** 2026-07-26
**Question:** can this study obtain adjudicated findings — a judgment, consent
order, or examination finding — establishing that an alleged FCRA reinvestigation
failure actually occurred?
**Answer:** yes. One source adopted, four rejected.

## Why this was asked

The review board's open SEV-2 (`FND3-SR-001`) found:

> Complaints are consumer allegations to a regulator and filings are claims put to
> a court. Two independent forums now allege the same mechanism, which establishes
> independence, but neither establishes that the alleged failures occurred.

with the accepted remediation: *require a judgment, consent order or examination
finding before asserting the failure occurred.*

Sources were probed before any connector was designed. Every status code and count
below was observed on 2026-07-26 and is reproducible from
`source_evaluation_adjudicated_findings.json`.

## Adopted: FJC Integrated Database

The Federal Judicial Center's Integrated Database, republished through
CourtListener at `/api/rest/v4/fjc-integrated-database/`. It is the judiciary's own
statistical record of every federal civil case, and it codes what opinion prose does
not:

```text
disposition   how the case ended   (consent, verdict, settled, default, ...)
judgment      who it went for      (1 plaintiff, 2 defendant, 3 both, 4 unknown)
```

Posture and direction are therefore read off official codes rather than inferred
from text. Admission is statutory and deterministic, matching the RECAP connector's
standard: the FJC records the statute as separate title and section fields, so FCRA
cases are title 15, section 1681. No keyword matching on captions or party names.

**17,204 FCRA cases** are present. Classified by the adopted rules:

| Outcome | Count | Treatment |
| --- | --- | --- |
| Consent judgment for plaintiff | 23 | establishes occurrence |
| Judgment on pre-trial motion for plaintiff | 39 | establishes occurrence |
| Jury verdict for plaintiff | 4 | establishes occurrence |
| Directed verdict for plaintiff | 1 | establishes occurrence |
| **Total establishing occurrence** | **67** | |
| Trial merits for defendant | 3 | counter-evidence |
| Judgment on pre-trial motion for defendant | 363 | **excluded — ambiguous** |
| Settled | 7,683 | **excluded — not an admission** |
| Default judgment | 32 | **excluded — forfeiture, not a finding** |

Three exclusions carry the reasoning, and each discards real volume:

- **Settlement is the most common ending in this dataset** — roughly 7,700 of
  17,200. A settlement is not an admission. Admitting these would have handed the
  study thousands of false proofs in a single retrieval.
- **Default judgments** record that the defendant never appeared. Nobody weighed
  whether the failure happened.
- **Judgment on a pre-trial motion is directional.** For the plaintiff it is a
  merits win, because a plaintiff cannot prevail on a motion to dismiss — winning
  before trial means summary judgment. For the defendant the same code covers both
  a Rule 12(b)(6) dismissal, where the claim failed as a matter of law without any
  fact being found, and Rule 56 summary judgment, where the facts were resolved.
  The database does not distinguish them, so a defence win here is undetermined —
  discarding the largest defence-side group rather than overstating it.

The IDB is **not** a new source family. These are the same federal courts RECAP
already covers, so it raises evidentiary standing without touching the independent
family count. Counting it as a third forum would double-count one dispute.

## Rejected

### CourtListener opinions — REJECTED, OUTCOME NOT CODED

| Probe | Result |
| --- | --- |
| `search/?type=o` unauthenticated | HTTP 200 — 402 published FCRA opinions |
| `clusters/`, `opinions/{id}/` unauthenticated | HTTP 401 |
| `clusters/{id}/` **authenticated** | HTTP 200 — `disposition` empty on **8 of 8** |

The records are real and on point: published federal opinions naming Experian,
Equifax and TransUnion. A token was obtained and the endpoints opened, but the
fields carrying the outcome are unpopulated for modern federal opinions —
`disposition`, `posture`, `procedural_history` and `syllabus` all came back empty.
Opinion snippets do not contain the statutory citation either, so even admission
could not be verified locally.

Inferring disposition from opinion prose was considered and rejected. This
repository refuses keyword guessing where structured metadata exists, and posture is
where guessing does the most damage — an opinion denying a motion to dismiss
*assumes the allegations are true*, so misreading one would convert an allegation
into a finding with a judge's name attached.

### Federal Register API — REJECTED, WRONG INSTRUMENT

HTTP 200, unauthenticated, 1,248 documents matching "Fair Credit Reporting Act". It
is nonetheless a **rulemaking gazette, not an adjudication register**: the results
are rules, proposed rules, regulatory agendas and Paperwork Reduction Act notices.
The consent orders it carries are FTC *proposed* orders published for comment —
"Analysis of Proposed Consent Order To Aid Public Comment" — which are not final
adjudications. Admitting those would have reproduced the board's finding in a new
source rather than answering it.

### FTC Legal Library — REJECTED, PUBLISHER REFUSES AUTOMATED ACCESS

`legal-library/browse/cases-proceedings` returns HTTP 403, and the candidate API
path returns a block page: *"The request resembles an abusive automated request."*
The publisher is explicitly refusing automated retrieval.

### CFPB enforcement actions — REJECTED, NO MACHINE-READABLE FEED

HTTP 200 but `text/html` only; `?format=json` returns HTML and two candidate JSON
paths return 404. Independently of the format problem, CFPB enforcement shares a
publisher with the CFPB complaint family already in the study, so its independence
would need to be argued rather than assumed.

## What the first live three-source run found

Running `--sources cfpb,court,fjc` retrieved 8 adjudicated cases: one consent
judgment establishing occurrence, one trial judgment for the respondent, six
undetermined. PG-09 and PG-13 both reported PASS.

**That pass was wrong, and the run exposed it.** IDB rows carry no consumer
narrative, so every one classified to the default `unclassified_credit_reporting_
complaint` mechanism — and so did the complaints in the same run. The corroboration
check matched them to each other on *both being unclassified*. Two records agreeing
that neither has been classified is not corroboration.

The unclassified fallback is now excluded from mechanism matching in both
directions, mirroring how PG-06 already refuses to match an unknown company against
itself. On the re-run PG-09 and PG-13 correctly report WEAK: an adjudication
establishing occurrence exists, but it does not yet corroborate a classified
mechanism.

## Standing state of the study

| Axis | Status |
| --- | --- |
| Independent source families | 2 — CFPB complaints, federal court records |
| Adjudicated records retrievable | 67 establishing, 3 contradicting |
| Occurrence established in the live run | 1 (consent judgment) |
| PG-09 / PG-13 | WEAK — adjudication present, mechanism unclassified |
| Maximum permitted verdict | CONTINUE RESEARCH |

**Next step to make PG-09 pass on merit:** classify the mechanism for adjudicated
records. IDB rows carry outcome codes but no narrative, so the mechanism has to come
from the underlying docket — joining an IDB record to its RECAP docket by docket
number would supply the text the classifier needs.
