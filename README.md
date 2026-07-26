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

## Evidentiary Standing

Independence and proof are separate questions, and the study tracks them on
separate axes:

```text
source family        does this share an origin with evidence already held?
evidentiary standing is this an allegation, or has a forum decided it?
```

Adding forums moves the first axis. Only a decision moves the second. Ten
independent complaint databases would still be ten allegations.

`core/adjudication.py` holds the rule. A record reaches `ADJUDICATED` standing
only when a forum resolved the merits, and it establishes occurrence only when
that resolution went against the respondent. Everything the classifier cannot
resolve from explicit structured values is `UNDETERMINED`, which never establishes
occurrence — because posture is routinely misread:

```text
denying a motion to dismiss   -> the court ASSUMED the allegations were true
denying summary judgment      -> the facts are genuinely DISPUTED
"affirmed" on appeal          -> relative to a judgment below; no direction alone
a settlement                  -> not an admission
```

`PG-09` (Independent Corroboration) requires an adjudicated finding of occurrence
on a mechanism *another* source family independently alleges. `PG-13`
(Counter-Evidence) requires a disposition that went the other way — complaints and
filings are submitted by claimants, so neither can ever produce counter-evidence,
and a source that can only confirm the hypothesis is not a test of it.

Both gates were previously pinned to `FAIL`.

### The adjudicated source

`connectors/fjc_idb.py` reads the Federal Judicial Center's Integrated Database —
the judiciary's own statistical record of every federal civil case. It codes what
opinion prose does not:

```text
disposition   how the case ended   (consent, verdict, settled, default, ...)
judgment      who it went for      (1 plaintiff, 2 defendant, 3 both, 4 unknown)
```

Admission is statutory and deterministic, matching the RECAP connector: the FJC
records the statute as title and section, so FCRA is title 15, section 1681.

Of 17,204 FCRA cases, 67 establish occurrence and 3 contradict it. The exclusions
matter more than the inclusions:

```text
7,683 settled          a settlement is not an admission
   32 default          a forfeiture, not a weighed finding
  363 pre-trial win    for the defendant, one code covers both Rule 12(b)(6)
                       and Rule 56 — not separable, so it proves nothing
```

The IDB is deliberately **not** a new source family. These are the same courts
RECAP already covers, so it raises standing without touching the independent family
count — counting it as a third forum would double-count one dispute.

Requires `COURTLISTENER_API_TOKEN`. Without it the connector emits an access
diagnostic rather than an empty result, so an unconfigured environment never looks
like an absence of adjudications.

```bash
python -m core.pipeline --sources cfpb,court,fjc --limit 8
```

See `analysis/source_evaluation_adjudicated_findings.md` for the four sources that
were probed and rejected, and for the false PASS the first live three-source run
produced before the unclassified-mechanism guard was added.

## Market and Competition Lane

`market/` answers a different question from the study: who already operates in
this market, at what scale, and where is their primary disclosure. It exists to
feed competitive and economic assessment (SV Engine `C8_MARKET_COMPETITION`,
`G7_COMPETITIVE_VIABILITY`), not to prove that consumer harm occurred.

It is sealed off from the evidence study by construction:

```text
MarketEvidence is not VerifiedEvidence.
It carries no source_family, so it can never reach the proof gates
or the independent source family count.
```

Every record is classed `E5_COMPETITIVE_MARKET` and carries
`counts_toward_source_independence: false` explicitly, so the constraint is
legible in the artifact and not only in the code that produced it.

Current source: SEC EDGAR submissions and XBRL company facts. Registrants are
verified against the SIC code they file under rather than an assumption about who
they are — a CIK that turns out not to be a credit reporting agency is reported as
such. Annual figures are filtered by period length, because a 10-K also carries
quarterly breakdowns, and restatements of the same period collapse to the most
recently filed value.

EDGAR full-text search was evaluated and rejected: a phrase search for
"Fair Credit Reporting Act" across 10-K filings returns thousands of unrelated
registrants, so it cannot support a deterministic admission rule.

Experian is absent by necessity — it is LSE-listed and does not file with the SEC,
so no EDGAR evidence exists for it.

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
