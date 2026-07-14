from __future__ import annotations

import subprocess
from pathlib import Path

from core.ids import stable_id
from core.models import RunManifest
from core.storage import file_checksum

CONFIGURATION_VERSION = "GS-CF001-CONFIG-001"
METHODOLOGY_VERSION = "PROVENA-EOS-METHOD-001"
RULE_VERSIONS = {
    "normalisation": "NORM-CFPB-001",
    "verification": "VER-CFPB-001",
    "findings": "FIND-CFPB-001",
    "opportunity_assessment": "OPP-ASSESS-001",
    "proof_gates": "PG-001",
    "evidence_ceiling": "CEILING-001",
    "ai_governance": "AI-GOV-001",
}


def current_commit_hash() -> str:
    commands = [
        ["git", "rev-parse", "HEAD"],
        [str(Path.home() / "AppData/Local/GitHubDesktop/app-3.6.1/resources/app/git/cmd/git.exe"), "rev-parse", "HEAD"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            continue
    return "unknown"


def build_run_manifest(
    study_id: str,
    source_access_method: str,
    retrieval_timestamps: list[str],
    input_record_identifiers: list[str],
    output_artifact_list: list[str],
    final_verdict: str,
    evidence_ceiling: str,
    errors: list[str],
    warnings: list[str],
) -> RunManifest:
    artifact_checksums = {path: file_checksum(path) for path in output_artifact_list}
    payload = {
        "study_id": study_id,
        "records": input_record_identifiers,
        "artifacts": artifact_checksums,
        "verdict": final_verdict,
    }
    return RunManifest(
        run_id=stable_id("RUN", payload),
        study_id=study_id,
        code_commit_hash=current_commit_hash(),
        configuration_version=CONFIGURATION_VERSION,
        methodology_version=METHODOLOGY_VERSION,
        rule_versions=RULE_VERSIONS,
        ai_model_configuration="AI disabled; deterministic rules only.",
        source_access_method=source_access_method,
        retrieval_timestamps=retrieval_timestamps,
        input_record_identifiers=input_record_identifiers,
        artifact_checksums=artifact_checksums,
        output_artifact_list=output_artifact_list,
        final_verdict=final_verdict,
        evidence_ceiling=evidence_ceiling,
        errors=errors,
        warnings=warnings,
    )
