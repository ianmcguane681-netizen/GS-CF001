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

## The docket join, and the case that made it mandatory

An IDB row states that an FCRA violation was found. It does not state which duty
was breached: `section` is `1681` on every record and `subsection` is empty
throughout. So the mechanism is not in the data.

`connectors/docket_join.py` rebuilds the PACER docket number from the IDB's coded
`office` and `docket_number` fields (`office=2, docket=2100267` → `2:21-cv-00267`)
and confirms the case against RECAP. Verified live at 4 of 4.

The join is not enrichment. It is a precondition, because of this record:

```text
United States v. Vivint Smart Home     2:21-cv-00267
consent judgment, against the respondent
suit nature: 890 Other Statutory Actions
```

A real FCRA violation, judicially resolved against the respondent, satisfying both
posture and direction — and a government enforcement action about improperly
*using* consumer reports, with nothing to do with reinvestigation failures. It was
the study's only occurrence-establishing record. Admitting it would have proved the
study's mechanism with a case about something else, and it would have read as a
success.

An adjudicated record must now be confirmed against a single consumer-credit docket
before it can establish or contradict anything. A join that fails, or is ambiguous,
or never runs, leaves the record establishing nothing: unknown subject matter is not
permission.

**Effect on the live run:** occurrence-establishing records fell from 1 to 0, and
PG-09 moved from WEAK to FAIL. That is the correct answer.

## Standing state of the study

| Axis | Status |
| --- | --- |
| Independent source families | 2 — CFPB complaints, federal court records |
| Adjudicated records retrievable | 67 establishing, 3 contradicting |
| Occurrence established in the live run | 0 — the one candidate was off-mechanism |
| PG-09 | FAIL — no adjudication establishes this study's mechanism |
| PG-13 | WEAK — one contradicting case, mechanism unclassified |
| Maximum permitted verdict | CONTINUE RESEARCH |

## Update, 2026-07-27: mechanism-level corroboration is now reachable

The structural claim below was wrong in one respect. Case-level *metadata* carries
no mechanism, which remains true. But the complaint *document* does, and RECAP
holds it for some dockets.

A complaint is the plaintiff's own account of what happened — the same evidentiary
class as a CFPB consumer narrative — so the study's existing classifier applies
unchanged. Live: the complaint in *Proctor v Experian* (41,983 characters)
classifies to `bureau_dispute_reinvestigation_failure`; *Washington v Equifax*
(9,967 characters) to the same.

Document 1 is the complaint only in an **original proceeding**. A removed case
opens with a notice of removal, a transferred one with transfer papers. The IDB
codes this in its `origin` field, so it is read rather than assumed.

Retrieval is now **stratified by direction**. Defence-side decisions outnumber
plaintiff-side ones roughly 366 to 67, so an unstratified sample of any practical
size is almost all defence wins and the study never sees an adjudicated finding of
occurrence. Retrieving only plaintiff wins would be the opposite error — a source
that can only confirm is not a test — so both strata are requested in equal
measure and the stratification is recorded.

**Live state after these changes:** occurrence-establishing records went 0 → 1, and
adjudicated records now carry real mechanisms (`bureau_dispute_reinvestigation_
failure`, `dispute_supporting_evidence_rejection`). PG-09 moved FAIL → WEAK. It is
not PASS because the one record establishing occurrence has no retrievable
complaint text, so it corroborates nothing.

What remains is coverage, not design: PG-09 needs a plaintiff win, on a
consumer-credit case, with complaint text in RECAP, on a mechanism another family
also alleges. That conjunction is sparse but no longer impossible.

**Original assessment, retained:** it was unachieved, and the reason was thought
structural rather than a gap in the plumbing. Neither source names the
mechanism: the IDB stops at `section=1681`, and docket metadata carries a statutory
cause and a nature-of-suit category but no consumer narrative. Case-level records
identify *that* an FCRA claim was decided, never *which duty* was breached.

Closing it needs document-level text — the complaint or opinion in a joined docket —
which RECAP holds unevenly because coverage depends on user contributions. That is a
real research step with an uncertain yield, not a wiring job, and it should be
scoped as one.


## Coverage sweep, 2026-07-27: the binding constraint measured

`tools/adjudication_coverage.py` walked the entire occurrence-establishing pool —
all 67 FCRA cases whose coded outcome went against the respondent on the merits —
and recorded where each one stops on the way to corroborating this study's
mechanism.

| Stopped at | Count |
| --- | ---: |
| No complaint text in RECAP | 43 |
| Off-study suit nature | 11 |
| Not an original proceeding | 10 |
| Join failed | 2 |
| **Reached a mechanism** | **1** |

```text
pool enumerated        67
joined to a docket     65
consumer credit        54
complaint text          1
reached a mechanism     1
```

**RECAP document coverage is the binding constraint, and it is severe.** Subject
matter is rarely the problem: 54 of the 65 joined records are consumer credit
cases. The failure is that RECAP holds the complaint for one of them. Coverage is
contributed by users, so this is a property of the archive rather than of the
courts, and it is not something more retrieval effort fixes.

The one record that completes the conjunction:

```text
Sandmeier v. Collection Consultants of California    caed 2:20-cv-00657
merits judgment for the plaintiff, consumer credit, original proceeding
complaint text retrieved -> bureau_dispute_reinvestigation_failure
```

That is the first adjudicated finding this study has ever held that is capable of
corroborating its mechanism. It exists, and it is one record.

**What this means for PG-09.** Corroboration is achievable but not yet robust. One
adjudication is a fact about one dispute, and a gate that passes on a single record
would be asserting a market-wide mechanism from a single California case. The
sensible reading is that the tier now works and the sample is thin — a judgement for
the board rather than for me.

### A defect this sweep found in itself

The first two runs reported a completed summary while pagination had failed on the
first page, having enumerated nothing. The tool wrote a summary over previously
assessed records, so a run with no denominator at all read as a finished
measurement. It now refuses to summarise when the pool was not enumerated, exits
non-zero, and says why.

The cause was self-inflicted: the pool was re-walked at full page size on every
attempt, so the expensive request ran first and repeatedly and was throttled before
any record could be assessed. The pool is enumerated once and cached.
