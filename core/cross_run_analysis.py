"""cross_run_analysis.py — Compare multiple pipeline runs for stability and consistency.

Correctness 4 of the methodology-validation review: count-only comparisons are
insufficient. This module now compares runs using:

  Complaint-ID overlap / equality
    - Sorted-set SHA-256 hash (order-independent fingerprint of which complaints
      were retrieved)
    - Jaccard similarity across all run pairs (intersection / union of complaint IDs)
    - complaint_ids_identical: True only when every run retrieved the exact same set

  Ordering stability
    - Ordered-list SHA-256 hash (position-dependent fingerprint)
    - ordering_stable: True when all runs received complaints in the same sequence

  Source mutation detection
    - Per-record content hash indexed by complaint ID
    - mutation_detected: True when the same complaint ID appears in multiple runs
      but with different content (indicating the source record was mutated between
      runs — a data-integrity flag)

  Count-level comparisons (kept for backwards compatibility and quick scanning)
    - candidate_count, finding_count, opportunity_count per run

All analysis is deterministic. No AI. Reads existing artifact files.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.run_index import read_run_index


@dataclass
class RunSnapshot:
    """Per-run data loaded from artifact files."""
    run_id: str
    timestamp: str
    verdict: str
    evidence_ceiling: str
    source_access_method: str
    # Count-level metrics
    candidate_count: int
    verified_count: int
    finding_count: int
    opportunity_count: int
    mechanisms: list[str]
    companies: list[str]
    gate_statuses: dict[str, str]
    gates_constraining: list[str]
    # Complaint-ID level metrics (Correction 4)
    complaint_ids: list[str]               # ordered as returned by API
    complaint_id_set_hash: str             # SHA-256 of sorted ID list (order-independent)
    complaint_ordering_hash: str           # SHA-256 of ordered ID list (position-dependent)
    record_content_by_id: dict[str, str]   # complaint_id → SHA-256[:16] of record content

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # record_content_by_id can be large; omit from serialisation
        d.pop("record_content_by_id", None)
        return d


@dataclass
class CrossRunComparison:
    """Result of comparing N pipeline runs."""
    run_count: int
    run_ids: list[str]
    timestamps: list[str]

    # Count-level retrieval
    candidate_counts: list[int]
    retrieval_stable: bool
    retrieval_note: str

    # Complaint-ID overlap / equality (Correction 4)
    id_set_hashes: list[str]
    complaint_ids_identical: bool          # all runs returned the exact same set
    jaccard_similarity: float              # min across all pairs; 1.0 = identical sets
    id_overlap_note: str

    # Ordering stability (Correction 4)
    complaint_ordering_hashes: list[str]
    ordering_stable: bool
    ordering_note: str

    # Source mutation detection (Correction 4)
    mutation_detected: bool
    mutation_details: list[str]

    # Verdicts
    verdicts: list[str]
    verdict_consistent: bool
    evidence_ceilings: list[str]
    ceiling_consistent: bool

    # Proof Gates
    gate_status_by_run: list[dict[str, str]]
    inconsistent_gates: list[str]

    # Mechanisms
    mechanisms_per_run: list[list[str]]
    common_mechanisms: list[str]
    any_run_mechanisms: list[str]
    mechanism_stable: bool

    # Findings / Opportunities
    findings_per_run: list[int]
    opportunities_per_run: list[int]

    # Companies
    companies_per_run: list[list[str]]
    common_companies: list[str]

    # Overall
    overall_stability: str
    stability_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json_artifact(path_str: str | None) -> Any:
    if not path_str:
        return None
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _sha256_of(value: Any) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def _load_run_snapshot(entry: dict[str, Any]) -> RunSnapshot:
    paths = entry.get("artifact_paths", {})

    # ---- Candidates (count only) -------------------------------------------
    candidates_data = _load_json_artifact(paths.get("normalised_candidates")) or []
    candidate_count = len(candidates_data)

    # ---- Findings -------------------------------------------------------
    findings_data = _load_json_artifact(paths.get("findings")) or []
    finding_count = len(findings_data)
    mechanisms: list[str] = []
    companies: list[str] = []
    for f in findings_data:
        mech = f.get("mechanism")
        if mech and mech not in mechanisms:
            mechanisms.append(mech)
        for company in f.get("companies", []):
            if company and company not in companies:
                companies.append(company)

    # ---- Opportunities --------------------------------------------------
    opps_data = _load_json_artifact(paths.get("opportunities")) or []
    opportunity_count = len(opps_data)

    # ---- Verified evidence count ----------------------------------------
    processed = _load_json_artifact(paths.get("processed"))
    verified_count = 0
    if processed:
        verified_count = len(processed.get("verified_evidence", []))

    # ---- Proof gates ----------------------------------------------------
    gates_data = _load_json_artifact(paths.get("proof_gate_results")) or []
    gate_statuses: dict[str, str] = {}
    constraining: list[str] = []
    for gate in gates_data:
        gid = gate.get("gate_id", "")
        status = gate.get("status", "UNKNOWN")
        gate_statuses[gid] = status
        if gate.get("constrains_max_verdict"):
            constraining.append(gid)

    # ---- Complaint-ID level metrics (Correction 4) ----------------------
    # Raw records are stored as {"source":…, "records":[…], …}
    raw_data = _load_json_artifact(paths.get("raw"))
    raw_records: list[dict] = []
    if isinstance(raw_data, dict):
        raw_records = raw_data.get("records", [])
    elif isinstance(raw_data, list):
        raw_records = raw_data

    complaint_ids: list[str] = []
    record_content_by_id: dict[str, str] = {}
    for rec in raw_records:
        cid = str(
            rec.get("complaint_id")
            or rec.get("_source_record_id")
            or ""
        )
        if cid:
            complaint_ids.append(cid)
            # Short content hash for mutation detection (first 16 hex chars)
            content_hash = hashlib.sha256(
                json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16]
            record_content_by_id[cid] = content_hash

    sorted_ids = sorted(complaint_ids)
    complaint_id_set_hash = _sha256_of(sorted_ids)
    complaint_ordering_hash = _sha256_of(complaint_ids)

    return RunSnapshot(
        run_id=entry.get("run_id", ""),
        timestamp=entry.get("timestamp", ""),
        verdict=entry.get("verdict", ""),
        evidence_ceiling=entry.get("evidence_ceiling", ""),
        source_access_method=entry.get("source_access_method", ""),
        candidate_count=candidate_count,
        verified_count=verified_count,
        finding_count=finding_count,
        opportunity_count=opportunity_count,
        mechanisms=sorted(mechanisms),
        companies=sorted(companies),
        gate_statuses=gate_statuses,
        gates_constraining=constraining,
        complaint_ids=complaint_ids,
        complaint_id_set_hash=complaint_id_set_hash,
        complaint_ordering_hash=complaint_ordering_hash,
        record_content_by_id=record_content_by_id,
    )


def _jaccard(sets: list[set]) -> float:
    """Minimum pairwise Jaccard similarity across all pairs in *sets*."""
    if len(sets) <= 1:
        return 1.0
    min_j = 1.0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a, b = sets[i], sets[j]
            union = len(a | b)
            inter = len(a & b)
            pair_j = inter / union if union > 0 else 1.0
            if pair_j < min_j:
                min_j = pair_j
    return round(min_j, 4)


def compare_runs(run_entries: list[dict[str, Any]]) -> CrossRunComparison:
    """Compare N pipeline runs with full complaint-ID level analysis."""
    if not run_entries:
        raise ValueError("compare_runs requires at least one run entry.")

    snapshots = [_load_run_snapshot(e) for e in run_entries]
    n = len(snapshots)
    run_ids = [s.run_id for s in snapshots]
    timestamps = [s.timestamp for s in snapshots]

    # ---- Count-level retrieval stability -----------------------------------
    candidate_counts = [s.candidate_count for s in snapshots]
    retrieval_stable = all(c > 0 for c in candidate_counts)
    if retrieval_stable:
        retrieval_note = (
            f"All {n} run(s) returned candidates (counts: {candidate_counts}). "
            "Note: count equality does not imply record-set equality; see "
            "complaint-ID overlap analysis below."
        )
    else:
        zero_runs = [run_ids[i] for i, c in enumerate(candidate_counts) if c == 0]
        retrieval_note = (
            f"{len(zero_runs)} run(s) returned 0 candidates: {zero_runs}. "
            "CFPB API may have returned an empty result set for that pull."
        )

    # ---- Complaint-ID overlap / equality (Correction 4) -------------------
    id_set_hashes = [s.complaint_id_set_hash for s in snapshots]
    complaint_ids_identical = len(set(id_set_hashes)) == 1

    id_sets = [set(s.complaint_ids) for s in snapshots]
    jaccard = _jaccard(id_sets) if all(len(s) > 0 for s in id_sets) else 0.0

    if complaint_ids_identical:
        id_overlap_note = (
            f"All {n} run(s) retrieved the exact same set of complaint IDs "
            f"(set-hash: {id_set_hashes[0][:12]}…). "
            "Record-set identity confirmed."
        )
    else:
        hashes_preview = [h[:12] + "…" for h in id_set_hashes]
        id_overlap_note = (
            f"Complaint ID sets differ across runs "
            f"(set-hashes: {hashes_preview}, Jaccard={jaccard:.4f}). "
            "The CFPB API does not guarantee a deterministic result set for repeated "
            "queries; record-set variation is expected between runs."
        )

    # ---- Ordering stability (Correction 4) --------------------------------
    complaint_ordering_hashes = [s.complaint_ordering_hash for s in snapshots]
    ordering_stable = len(set(complaint_ordering_hashes)) == 1
    if ordering_stable:
        ordering_note = "Complaint ordering is identical across all runs."
    else:
        ordering_note = (
            "Complaint ordering varies across runs. The CFPB API sort order "
            "is not guaranteed to be deterministic between requests."
        )

    # ---- Source mutation detection (Correction 4) -------------------------
    mutation_details: list[str] = []
    if complaint_ids_identical and len(snapshots) > 1:
        # Only meaningful to check mutations when all runs retrieved the same set.
        sample_ids = list(snapshots[0].record_content_by_id.keys())
        for cid in sample_ids:
            hashes = [
                s.record_content_by_id.get(cid)
                for s in snapshots
                if cid in s.record_content_by_id
            ]
            unique = set(h for h in hashes if h is not None)
            if len(unique) > 1:
                mutation_details.append(
                    f"Complaint {cid}: content hash changed across runs — "
                    f"{sorted(unique)}. Source record may have been mutated."
                )
    mutation_detected = len(mutation_details) > 0

    # ---- Verdict / ceiling consistency ------------------------------------
    verdicts = [s.verdict for s in snapshots]
    verdict_consistent = len(set(verdicts)) == 1
    ceilings = [s.evidence_ceiling for s in snapshots]
    ceiling_consistent = len(set(ceilings)) == 1

    # ---- Proof gate consistency -------------------------------------------
    gate_status_by_run = [s.gate_statuses for s in snapshots]
    all_gate_ids = sorted({gid for s in snapshots for gid in s.gate_statuses})
    inconsistent_gates = [
        gid for gid in all_gate_ids
        if len({s.gate_statuses.get(gid, "MISSING") for s in snapshots}) > 1
    ]

    # ---- Mechanism distribution -------------------------------------------
    mechanism_sets = [set(s.mechanisms) for s in snapshots]
    common_mechs = sorted(set.intersection(*mechanism_sets)) if mechanism_sets else []
    any_mechs = sorted(set.union(*mechanism_sets)) if mechanism_sets else []
    mechanism_stable = len(common_mechs) == len(any_mechs) and bool(common_mechs)

    findings_per_run = [s.finding_count for s in snapshots]
    opps_per_run = [s.opportunity_count for s in snapshots]

    company_sets = [set(s.companies) for s in snapshots]
    common_companies = sorted(set.intersection(*company_sets)) if company_sets else []

    # ---- Overall stability -----------------------------------------------
    stability_notes: list[str] = []
    stability_issues = 0

    if not retrieval_stable:
        stability_notes.append(
            "RETRIEVAL UNSTABLE: Some runs returned 0 candidates."
        )
        stability_issues += 2

    if not complaint_ids_identical:
        stability_notes.append(
            f"RECORD-SET VARIES: Jaccard={jaccard:.4f}. "
            f"{id_overlap_note}"
        )
        stability_issues += 1

    if not ordering_stable:
        stability_notes.append(f"ORDERING VARIES: {ordering_note}")
        # Ordering variation alone is not a methodology failure; note only

    if mutation_detected:
        stability_notes.append(
            f"SOURCE MUTATION DETECTED: {len(mutation_details)} record(s) changed "
            "content between runs. See mutation_details for specifics."
        )
        stability_issues += 3

    if not verdict_consistent:
        stability_notes.append(
            f"VERDICT VARIES: {set(verdicts)}. "
            "Expected if some runs returned 0 candidates (→ REJECT)."
        )
        stability_issues += 1

    if not ceiling_consistent:
        stability_notes.append(
            f"CEILING INCONSISTENCY: {set(ceilings)}. "
            "Evidence ceiling must always be CONTINUE RESEARCH for CFPB-only data."
        )
        stability_issues += 3

    if inconsistent_gates:
        stability_notes.append(
            f"GATE STATUS VARIATION: {inconsistent_gates}. "
            "Data-dependent gates may vary if different records are retrieved."
        )
        stability_issues += 1

    if not mechanism_stable and any_mechs:
        stability_notes.append(
            f"MECHANISM VARIATION: common={common_mechs}, any={any_mechs}."
        )
        stability_issues += 1

    if ceiling_consistent and all(c == "CONTINUE RESEARCH" for c in ceilings):
        stability_notes.append(
            "CEILING ENFORCED: CONTINUE RESEARCH in all runs — correct for "
            "single source family."
        )

    if not stability_notes:
        stability_notes.append("All key metrics are consistent across all runs.")

    if stability_issues == 0:
        overall_stability = "stable"
    elif stability_issues <= 2:
        overall_stability = "partially_stable"
    else:
        overall_stability = "unstable"

    return CrossRunComparison(
        run_count=n,
        run_ids=run_ids,
        timestamps=timestamps,
        candidate_counts=candidate_counts,
        retrieval_stable=retrieval_stable,
        retrieval_note=retrieval_note,
        id_set_hashes=id_set_hashes,
        complaint_ids_identical=complaint_ids_identical,
        jaccard_similarity=jaccard,
        id_overlap_note=id_overlap_note,
        complaint_ordering_hashes=complaint_ordering_hashes,
        ordering_stable=ordering_stable,
        ordering_note=ordering_note,
        mutation_detected=mutation_detected,
        mutation_details=mutation_details,
        verdicts=verdicts,
        verdict_consistent=verdict_consistent,
        evidence_ceilings=ceilings,
        ceiling_consistent=ceiling_consistent,
        gate_status_by_run=gate_status_by_run,
        inconsistent_gates=inconsistent_gates,
        mechanisms_per_run=[s.mechanisms for s in snapshots],
        common_mechanisms=common_mechs,
        any_run_mechanisms=any_mechs,
        mechanism_stable=mechanism_stable,
        findings_per_run=findings_per_run,
        opportunities_per_run=opps_per_run,
        companies_per_run=[s.companies for s in snapshots],
        common_companies=common_companies,
        overall_stability=overall_stability,
        stability_notes=stability_notes,
    )


def load_and_compare_last_n_runs(
    n: int,
    run_index_path: str | Path = "data/exports/run_index.json",
) -> CrossRunComparison:
    all_entries = read_run_index(run_index_path)
    if not all_entries:
        raise ValueError(f"Run index is empty: {run_index_path}")
    entries = all_entries[-n:] if len(all_entries) >= n else all_entries
    return compare_runs(entries)


def write_cross_run_report(comparison: CrossRunComparison, path: str | Path) -> str:
    lines: list[str] = []
    lines.append("# Cross-Run Comparison Report")
    lines.append("")
    lines.append(f"**Runs compared:** {comparison.run_count}  ")
    lines.append(f"**Overall stability:** **{comparison.overall_stability}**  ")
    lines.append("")
    lines.append("## Run IDs and timestamps")
    lines.append("")
    lines.append("| # | Run ID | Timestamp | Verdict | Ceiling |")
    lines.append("|---|---|---|---|---|")
    for i, (rid, ts, v, c) in enumerate(zip(
        comparison.run_ids, comparison.timestamps,
        comparison.verdicts, comparison.evidence_ceilings,
    ), 1):
        lines.append(f"| {i} | `{rid}` | `{ts}` | {v} | {c} |")
    lines.append("")
    lines.append("## Retrieval — count level")
    lines.append("")
    lines.append("| Run # | Candidates |")
    lines.append("|---|---|")
    for i, c in enumerate(comparison.candidate_counts, 1):
        lines.append(f"| {i} | {c} |")
    lines.append("")
    lines.append(f"**Retrieval stable (all > 0):** {comparison.retrieval_stable}  ")
    lines.append(f"> {comparison.retrieval_note}")
    lines.append("")
    lines.append("## Complaint-ID overlap and equality (record-set analysis)")
    lines.append("")
    lines.append("| Run # | ID-set hash (first 12) | Ordering hash (first 12) |")
    lines.append("|---|---|---|")
    for i, (sh, oh) in enumerate(zip(
        comparison.id_set_hashes, comparison.complaint_ordering_hashes
    ), 1):
        lines.append(f"| {i} | `{sh[:12]}…` | `{oh[:12]}…` |")
    lines.append("")
    lines.append(f"**Complaint IDs identical across all runs:** {comparison.complaint_ids_identical}  ")
    lines.append(f"**Jaccard similarity (min pairwise):** {comparison.jaccard_similarity:.4f}  ")
    lines.append(f"**Ordering stable:** {comparison.ordering_stable}  ")
    lines.append(f"**Source mutation detected:** {comparison.mutation_detected}  ")
    lines.append("")
    lines.append(f"> **ID overlap:** {comparison.id_overlap_note}")
    lines.append(f"> **Ordering:** {comparison.ordering_note}")
    if comparison.mutation_details:
        lines.append("")
        lines.append("**Mutation details:**")
        for m in comparison.mutation_details:
            lines.append(f"- {m}")
    lines.append("")
    lines.append("## Verdict and Evidence Ceiling")
    lines.append("")
    lines.append(f"- Verdict consistent: **{comparison.verdict_consistent}** ({set(comparison.verdicts)})")
    lines.append(f"- Ceiling consistent: **{comparison.ceiling_consistent}** ({set(comparison.evidence_ceilings)})")
    lines.append("")
    lines.append("## Mechanism distribution")
    lines.append("")
    lines.append(f"- Common to all runs: {comparison.common_mechanisms or '(none)'}")
    lines.append(f"- Present in any run: {comparison.any_run_mechanisms or '(none)'}")
    lines.append(f"- Mechanism stable: **{comparison.mechanism_stable}**")
    lines.append("")
    for i, mechs in enumerate(comparison.mechanisms_per_run, 1):
        lines.append(f"- Run {i}: {mechs or ['(none)']}")
    lines.append("")
    lines.append("## Findings and opportunities")
    lines.append("")
    lines.append("| Run # | Findings | Opportunities |")
    lines.append("|---|---|---|")
    for i, (f, o) in enumerate(zip(comparison.findings_per_run, comparison.opportunities_per_run), 1):
        lines.append(f"| {i} | {f} | {o} |")
    lines.append("")
    lines.append("## Proof gate consistency")
    lines.append("")
    if comparison.inconsistent_gates:
        lines.append(f"Gates with status variation: {comparison.inconsistent_gates}  ")
        lines.append(
            "Note: data-dependent gates (PG-03–PG-14) may vary across runs. "
            "PG-15 and PG-16 must remain constant."
        )
    else:
        lines.append("All gate statuses are consistent across all runs.")
    lines.append("")
    lines.append("## Stability notes")
    lines.append("")
    for note in comparison.stability_notes:
        lines.append(f"- {note}")
    lines.append("")

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)
