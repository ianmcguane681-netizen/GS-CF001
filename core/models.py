from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

VerdictOutcome = Literal[
    "BUILD CANDIDATE",
    "CONTINUE RESEARCH",
    "PROCESS / POLICY PROBLEM",
    "SATURATED MARKET",
    "REJECT",
]


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    source_type: str
    base_url: str
    jurisdiction: str
    role: str
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
    evidence_ids: list[str]
    missing_evidence: list[str]
    reasoning_chain: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProofGateResult:
    gate_name: str
    status: str
    evidence_ids: list[str]
    confidence: float
    missing_evidence: list[str]
    recommended_next_action: str
    reasoning_chain: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StudyVerdict:
    verdict_id: str
    study_id: str
    outcome: VerdictOutcome
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
            "artifacts": self.artifacts,
        }
