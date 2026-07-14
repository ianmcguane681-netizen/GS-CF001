from core.models import EvidenceCandidate, Finding, OpportunityHypothesis, ProofGateResult, Source, Study, StudyVerdict, VerifiedEvidence


def test_domain_model_is_source_agnostic():
    source = Source("SRC-1", "Any Source", "public_database", "https://example.test", "US", "discovery")
    study = Study("STUDY-1", "Any Study", "Question?", implemented=True)

    candidate = EvidenceCandidate(
        "CAN-1",
        source,
        study,
        "external-1",
        "https://example.test/1",
        "2026-07-14T00:00:00Z",
        {"raw": "record"},
        {"field": "value"},
        "Mapped by test rule.",
        ["retrieved raw record", "normalised parsed fields"],
    )

    verified = VerifiedEvidence(
        "EVD-1",
        candidate.candidate_id,
        study.study_id,
        candidate.source_record_id,
        "Example Company",
        "verified",
        True,
        True,
        True,
        False,
        False,
        "dispute_investigation",
        ["verified traceability"],
        [candidate.candidate_id],
        ["independent corroboration"],
    )

    finding = Finding(
        "FND-1",
        study.study_id,
        verified.mechanism,
        "needs_more_evidence",
        [verified.evidence_id],
        ["Example Company"],
        1,
        1,
        "Single operational signal.",
        ["more companies"],
        ["grouped verified evidence"],
    )

    opportunity = OpportunityHypothesis(
        "OPP-1",
        finding.finding_id,
        "unproven",
        "Dispute workflow",
        "unclear",
        "unproven",
        "unknown",
        "possible",
        "unknown",
        "unknown",
        finding.evidence_ids,
        ["buyer evidence"],
        ["assessed after finding"],
    )

    gate = ProofGateResult("Evidence quality", "WEAK", ["EVD-1"], 0.35, ["corroboration"], "Continue research.", ["checked evidence"])
    verdict = StudyVerdict("VER-1", study.study_id, "CONTINUE RESEARCH", [gate], ["EVD-1"], ["FND-1"], ["OPP-1"], ["corroboration"], ["gates not satisfied"])

    assert candidate.source.source_id == "SRC-1"
    assert opportunity.finding_id == finding.finding_id
    assert verdict.outcome == "CONTINUE RESEARCH"
    assert verdict.proof_gates[0].missing_evidence == ["corroboration"]
