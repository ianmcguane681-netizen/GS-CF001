from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

VerdictOutcome = Literal[
    "BUILD CANDIDATE",
    "CONTINUE RESEARCH",
    "PROCESS / POLICY PROBLEM",
    "SATURATED MARKET",
    "REJECT",
    "INSUFFICIENT EVIDENCE",
]


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    source_type: str
    base_url: str
    jurisdiction: str
    role: str
    source_family: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Study:
    study_id: str
    title: str
    research_question: str
    implemented: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceCandidate:
    candidate_id: str
    source: Source
    study: Study
    source_record_id: str
    source_url: str
    retrieved_at: str
    raw_record: dict[str, Any]
    parsed_fields: dict[str, Any]
    study_mapping_reason: str
    traceability: list[str]
    evidence_state: str = "EVIDENCE_CANDIDATE"
    state_transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        data["study"] = self.study.to_dict()
        return data


@dataclass(frozen=True)
class VerifiedEvidence:
    evidence_id: str
    candidate_id: str
    study_id: str
    source_record_id: str
    company_name: str
    verification_status: str
    operational: bool
    traceable: bool
    software_addressable: bool
    repeated_signal: bool
    independently_corrobored: bool
    mechanism: str
    reasoning_chain: list[str]
    supporting_candidate_ids: list[str]
    missing_evidence: list[str]
    evidence_state: str = "VERIFIED_WITHIN_SOURCE"
    source_family: str = ""
    product: str = ""
    issue: str = ""
    date_received: str = ""
    source_limitations: list[str] = field(default_factory=list)
    alternative_explanations: list[str] = field(default_factory=list)
    state_transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Finding:
    finding_id: str
    study_id: str
    mechanism: str
    status: str
    evidence_ids: list[str]
    companies: list[str]
    evidence_count: int
    company_count: int
    summary: str
    missing_evidence: list[str]
    reasoning_chain: list[str]
    date_range: str = ""
    product_issue_mappings: list[str] = field(default_factory=list)
    mechanism_definition: dict[str, str] = field(default_factory=dict)
    verification_status: str = "CFPB-limited"
    alternative_explanations: list[str] = field(default_factory=list)
    source_limitations: list[str] = field(default_factory=list)
    maximum_permitted_verdict: str = "CONTINUE RESEARCH"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpportunityHypothesis:
    opportunity_id: str
    finding_id: str
    status: str
    component_hypothesis: str
    buyer_clarity: str
    commercial_relevance: str
    existing_solution_maturity: str
    component_reusability: str
    market_saturation: str
    implementation_leverage: str
    user_clarity: str = "unknown"
    workflow_owner: str = "unknown"
    regulatory_exposure: str = "unknown"
    operational_cost: str = "unknown"
    integration_burden: str = "unknown"
    cross_company_applicability: str = "unknown"
    non_software_alternatives: str = "unknown"
    evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    reasoning_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProofGateResult:
    gate_id: str
    gate_name: str
    status: str
    threshold: str
    observed_value: str
    evidence_ids: list[str]
    supporting_evidence: list[str]
    counter_evidence: list[str]
    confidence: float
    missing_evidence: list[str]
    recommended_next_action: str
    constrains_max_verdict: bool
    reasoning_chain: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StudyVerdict:
    verdict_id: str
    study_id: str
    outcome: VerdictOutcome
    unconstrained_outcome: VerdictOutcome
    evidence_ceiling: VerdictOutcome
    final_permitted_outcome: VerdictOutcome
    evidence_ceiling_reason: str
    evidence_required_to_remove_ceiling: list[str]
    independent_source_family_count: int
    proof_gates: list[ProofGateResult]
    evidence_ids: list[str]
    finding_ids: list[str]
    opportunity_ids: list[str]
    missing_evidence: list[str]
    reasoning_chain: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["proof_gates"] = [gate.to_dict() for gate in self.proof_gates]
        return data


@dataclass(frozen=True)
class PipelineResult:
    source_records: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[EvidenceCandidate] = field(default_factory=list)
    verified_evidence: list[VerifiedEvidence] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    opportunities: list[OpportunityHypothesis] = field(default_factory=list)
    gates: list[ProofGateResult] = field(default_factory=list)
    verdict: StudyVerdict | None = None
    source_reliability: list["SourceReliabilityAssessment"] = field(default_factory=list)
    access_diagnostics: list["AccessDiagnostic"] = field(default_factory=list)
    analysis_artifacts: list["AnalysisArtifact"] = field(default_factory=list)
    state_transitions: list["EvidenceStateTransition"] = field(default_factory=list)
    run_manifest: "RunManifest | None" = None
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_records": self.source_records,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "verified_evidence": [evidence.to_dict() for evidence in self.verified_evidence],
            "findings": [finding.to_dict() for finding in self.findings],
            "opportunities": [opportunity.to_dict() for opportunity in self.opportunities],
            "gates": [gate.to_dict() for gate in self.gates],
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "source_reliability": [item.to_dict() for item in self.source_reliability],
            "access_diagnostics": [item.to_dict() for item in self.access_diagnostics],
            "analysis_artifacts": [item.to_dict() for item in self.analysis_artifacts],
            "state_transitions": [item.to_dict() for item in self.state_transitions],
            "run_manifest": self.run_manifest.to_dict() if self.run_manifest else None,
            "artifacts": self.artifacts,
        }


@dataclass(frozen=True)
class SourceReliabilityAssessment:
    source_id: str
    source_name: str
    publisher: str
    publisher_type: str
    authority_level: str
    jurisdiction: str
    source_family: str
    retrieval_method: str
    retrieval_timestamp: str
    update_frequency: str
    coverage_period: str
    record_granularity: str
    known_limitations: list[str]
    verification_constraints: list[str]
    independence_constraints: list[str]
    representativeness_warning: str
    data_completeness_warning: str
    permitted_uses: list[str]
    prohibited_inferences: list[str]
    reliability_version: str
    last_reviewed_date: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccessDiagnostic:
    diagnostic_id: str
    endpoint: str
    attempted_at: str
    environment: str
    request_method: str
    request_headers: dict[str, str]
    response_status: str
    response_headers: dict[str, str]
    response_body_summary: str
    retry_result: str
    final_interpretation: str
    access_method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceStateTransition:
    transition_id: str
    evidence_id: str
    previous_state: str
    new_state: str
    rule_or_process: str
    timestamp: str
    inputs: list[str]
    output: str
    confidence: float
    limitations: list[str]
    actor_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisArtifact:
    artifact_id: str
    method_used: str
    instruction_version: str
    timestamp: str
    input_evidence_ids: list[str]
    output: dict[str, Any]
    confidence: float
    known_limitations: list[str]
    validation_status: str
    affected_finding_or_verdict: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    study_id: str
    code_commit_hash: str
    configuration_version: str
    methodology_version: str
    rule_versions: dict[str, str]
    ai_model_configuration: str
    source_access_method: str
    retrieval_timestamps: list[str]
    input_record_identifiers: list[str]
    artifact_checksums: dict[str, str]
    output_artifact_list: list[str]
    final_verdict: str
    evidence_ceiling: str
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
