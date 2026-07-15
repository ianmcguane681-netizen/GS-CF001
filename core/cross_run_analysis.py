"""cross_run_analysis.py — Compare multiple pipeline runs for stability and consistency.

Loads run artifacts from the run index and compares:
  - Retrieval stability (record counts)
  - Verdict and Evidence Ceiling consistency
  - Proof Gate status consistency across runs
  - Mechanism distribution per run
  - Finding and opportunity counts
  - Company distribution

All comparisons are deterministic. No AI. Reads from existing artifact files
written by core/pipeline.py. Safe to call on any set of runs in run_index.json.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    candidate_count: int
    verified_count: int
    finding_count: int
    opportunity_count: int
    mechanisms: list[str]
    companies: list[str]
    gate_statuses: dict[str, str]          # gate_id -> status
    gates_constraining: list[str]          # gate_ids where constrains_max_verdict=True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrossRunComparison:
    """Result of comparing N pipeline runs."""
    run_count: int
    run_ids: list[str]
    timestamps: list[str]

    # Retrieval
    candidate_counts: list[int]
    retrieval_stable: bool                # all runs returned > 0 candidates
    retrieval_note: str

    # Verdicts
    verdicts: list[str]
    verdict_consistent: bool
    evidence_ceilings: list[str]
    ceiling_consistent: bool

    # Proof Gates
    gate_status_by_run: list[dict[str, str]]   # one dict per run
    inconsistent_gates: list[str]              # gate_ids that changed across runs

    # Mechanisms
    mechanisms_per_run: list[list[str]]
    common_mechanisms: list[str]              # present in all runs
    any_run_mechanisms: list[str]             # present in at least one run
    mechanism_stable: bool

    # Findings / Opportunities
    findings_per_run: list[int]
    opportunities_per_run: list[int]

    # Companies
    companies_per_run: list[list[str]]
    common_companies: list[str]

    # Overall
    overall_stability: str                    # stable | partially_stable | unstable
    stability_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json_artifact(path_str: str | None) -> Any:
    """Load a JSON artifact file. Returns None on missing/corrupt."""
    if not path_str:
        return None
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_run_snapshot(entry: dict[str, Any]) -> RunSnapshot:
    """Build a RunSnapshot from one run_index entry and its artifact files."""
    paths = entry.get("artifact_paths", {})

    # Candidates
    candidates_data = _load_json_artifact(paths.get("normalised_candidates")) or []
    candidate_count = len(candidates_data)

    # Verified evidence — load from processed bundle since there's no standalone file
    verified_count = 0
    finding_count = 0
    opportunity_count = 0
    mechanisms: list[str] = []
    companies: list[str] = []

    # Load findings file
    findings_data = _load_json_artifact(paths.get("findings")) or []
    finding_count = len(findings_data)
    for f in findings_data:
        mech = f.get("mechanism")
        if mech and mech not in mechanisms:
            mechanisms.append(mech)
        for company in f.get("companies", []):
            if company and company not in companies:
                companies.append(company)

    # Load opportunities file
    opps_data = _load_json_artifact(paths.get("opportunities")) or []
    opportunity_count = len(opps_data)

    # Load verified evidence from processed bundle for verified_count
    processed = _load_json_artifact(paths.get("processed"))
    if processed:
        verified_count = len(processed.get("verified_evidence", []))

    # Load proof gates
    gates_data = _load_json_artifact(paths.get("proof_gate_results")) or []
    gate_statuses: dict[str, str] = {}
    constraining: list[str] = []
    for gate in gates_data:
        gid = gate.get("gate_id", "")
        status = gate.get("status", "UNKNOWN")
        gate_statuses[gid] = status
        if gate.get("constrains_max_verdict"):
            constraining.append(gid)

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
    )


def compare_runs(
    run_entries: list[dict[str, Any]],
) -> CrossRunComparison:
    """Compare N pipeline runs.

    Parameters
    ----------
    run_entries:
        List of run-index entries (as returned by read_run_index). Pass the
        specific entries to compare — typically the last N runs.

    Returns
    -------
    CrossRunComparison with full analysis.
    """
    if not run_entries:
        raise ValueError("compare_runs requires at least one run entry.")

    snapshots = [_load_run_snapshot(e) for e in run_entries]
    n = len(snapshots)

    run_ids = [s.run_id for s in snapshots]
    timestamps = [s.timestamp for s in snapshots]

    # ---- Retrieval stability -----------------------------------------------
    candidate_counts = [s.candidate_count for s in snapshots]
    retrieval_stable = all(c > 0 for c in candidate_counts)
    if retrieval_stable:
        retrieval_note = f"All {n} run(s) returned candidates (counts: {candidate_counts})."
    else:
        zero_runs = [run_ids[i] for i, c in enumerate(candidate_counts) if c == 0]
        retrieval_note = (
            f"{len(zero_runs)} run(s) returned 0 candidates: {zero_runs}. "
            "CFPB API may have returned an empty result set for that pull."
        )

    # ---- Verdict / ceiling consistency ------------------------------------
    verdicts = [s.verdict for s in snapshots]
    verdict_consistent = len(set(verdicts)) == 1
    ceilings = [s.evidence_ceiling for s in snapshots]
    ceiling_consistent = len(set(ceilings)) == 1

    # ---- Proof gate consistency -------------------------------------------
    gate_status_by_run = [s.gate_statuses for s in snapshots]
    all_gate_ids = sorted({gid for s in snapshots for gid in s.gate_statuses})
    inconsistent_gates = []
    for gid in all_gate_ids:
        statuses = [s.gate_statuses.get(gid, "MISSING") for s in snapshots]
        if len(set(statuses)) > 1:
            inconsistent_gates.append(gid)

    # ---- Mechanism distribution -------------------------------------------
    mechanism_sets = [set(s.mechanisms) for s in snapshots]
    if mechanism_sets:
        common_mechs = sorted(set.intersection(*mechanism_sets))
        any_mechs = sorted(set.union(*mechanism_sets))
    else:
        common_mechs = []
        any_mechs = []
    mechanism_stable = len(common_mechs) == len(any_mechs) and bool(common_mechs)

    # ---- Findings / opportunities -----------------------------------------
    findings_per_run = [s.finding_count for s in snapshots]
    opps_per_run = [s.opportunity_count for s in snapshots]

    # ---- Companies ---------------------------------------------------------
    company_sets = [set(s.companies) for s in snapshots]
    if company_sets:
        common_companies = sorted(set.intersection(*company_sets))
    else:
        common_companies = []

    # ---- Overall stability assessment ------------------------------------
    stability_notes: list[str] = []
    stability_issues = 0

    if not retrieval_stable:
        stability_notes.append(
            "RETRIEVAL UNSTABLE: Some runs returned 0 candidates. "
            "CFPB API may return empty results intermittently."
        )
        stability_issues += 2

    if not verdict_consistent:
        stability_notes.append(
            f"VERDICT VARIES: {set(verdicts)}. "
            "This is expected if some runs retrieved 0 candidates (→ REJECT) "
            "and others retrieved candidates (→ CONTINUE RESEARCH)."
        )
        stability_issues += 1

    if not ceiling_consistent:
        stability_notes.append(
            f"CEILING INCONSISTENCY: {set(ceilings)}. "
            "Evidence ceiling should always be CONTINUE RESEARCH for CFPB-only data."
        )
        stability_issues += 3  # This would be a methodology violation

    if inconsistent_gates:
        stability_notes.append(
            f"GATE STATUS VARIATION: {inconsistent_gates}. "
            "Some gates change status between runs depending on whether records "
            "were retrieved. This is expected for data-dependent gates (PG-03 to PG-14)."
        )
        stability_issues += 1

    if not mechanism_stable and any_mechs:
        stability_notes.append(
            f"MECHANISM VARIATION: common={common_mechs}, any={any_mechs}. "
            "Some mechanisms appear only in specific runs — depends on records retrieved."
        )
        stability_issues += 1

    if ceiling_consistent and all(c == "CONTINUE RESEARCH" for c in ceilings):
        stability_notes.append(
            "CEILING ENFORCED: Evidence ceiling is CONTINUE RESEARCH in all runs — correct for single source family."
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
    """Convenience function: load the last *n* runs and compare them."""
    all_entries = read_run_index(run_index_path)
    if not all_entries:
        raise ValueError(f"Run index is empty: {run_index_path}")
    entries = all_entries[-n:] if len(all_entries) >= n else all_entries
    return compare_runs(entries)


def write_cross_run_report(comparison: CrossRunComparison, path: str | Path) -> str:
    """Write a Markdown cross-run comparison report. Returns path as str."""
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
    lines.append("## Retrieval stability")
    lines.append("")
    lines.append(f"| Run # | Candidates retrieved |")
    lines.append(f"|---|---|")
    for i, c in enumerate(comparison.candidate_counts, 1):
        lines.append(f"| {i} | {c} |")
    lines.append("")
    lines.append(f"**Retrieval stable:** {comparison.retrieval_stable}  ")
    lines.append(f"**Note:** {comparison.retrieval_note}")
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
        lines.append(
            f"Gates with status variation across runs: {comparison.inconsistent_gates}  "
        )
        lines.append(
            "Note: data-dependent gates (PG-03 through PG-14) may vary if different "
            "records are retrieved per run. PG-15 and PG-16 must remain constant."
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
