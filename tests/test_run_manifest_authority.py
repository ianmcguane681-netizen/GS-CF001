"""A run must name the authority that will judge it.

FND3-MA-001, raised by the Methodology Auditor and left open through two further
reviews: the manifest recorded the methodology the run was *produced* under but
nothing about the regime that would *judge* it, so an artefact could not be traced
to a review authority from the manifest alone.

The fix names the regime and deliberately stops short of naming a version. A run
cannot know which version will assess it, and asserting one would record something
unknowable at the time of writing.
"""
from __future__ import annotations

from core.manifest import REVIEWING_AUTHORITY, build_run_manifest


def manifest(tmp_path):
    artefact = tmp_path / "artifact.json"
    artefact.write_text("{}", encoding="utf-8")
    return build_run_manifest(
        study_id="GS-CF001-C",
        source_access_method="test",
        retrieval_timestamps=["2026-07-26T00:00:00Z"],
        input_record_identifiers=["REC-1"],
        output_artifact_list=[str(artefact)],
        final_verdict="CONTINUE RESEARCH",
        evidence_ceiling="CONTINUE RESEARCH",
        errors=[],
        warnings=[],
    )


def test_the_manifest_names_the_governing_review_regime(tmp_path):
    authority = manifest(tmp_path).to_dict()["reviewing_authority"]

    assert authority["review_methodology_profile_id"] == "RBM-001"
    assert authority["architecture_authority"] == "RBE-001"


def test_the_manifest_does_not_assert_an_assessment_version(tmp_path):
    """The version that assessed an artefact is a review-time fact.

    Recording one here would be a guess that silently goes stale the moment the
    profile is amended, and the study would have no way to know.
    """
    authority = manifest(tmp_path).to_dict()["reviewing_authority"]

    assert "review_methodology_version" not in authority
    assert not any(
        key for key, value in authority.items() if key != "note" and value.strip().startswith("2.")
    )
    assert "reviewing board" in authority["assessment_version_recorded_by"]


def test_the_declared_regime_is_not_binding(tmp_path):
    """RBM-001 is a release candidate; nothing here may imply otherwise."""
    assert manifest(tmp_path).to_dict()["reviewing_authority"]["binding"] == "false"


def test_the_authority_block_is_copied_not_shared(tmp_path):
    """Mutating one run's manifest must not rewrite the module constant."""
    first = manifest(tmp_path)
    first.reviewing_authority["review_methodology_profile_id"] = "TAMPERED"

    assert REVIEWING_AUTHORITY["review_methodology_profile_id"] == "RBM-001"
    assert manifest(tmp_path).reviewing_authority["review_methodology_profile_id"] == "RBM-001"
