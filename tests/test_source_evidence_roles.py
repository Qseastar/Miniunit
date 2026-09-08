"""Adversarial source-role contract tests for candidate quality tooling."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.verification_quality_gate import validate_source_roles
from tools.course_material_manifest import load_course_material_manifest, material_index


ROOT = Path(__file__).resolve().parents[1]
CHUNKS = {
    item["id"]: item
    for item in json.loads((ROOT / "data" / "course_chunks.json").read_text(encoding="utf-8"))["chunks"]
}
MATERIALS = material_index(load_course_material_manifest(ROOT / "data" / "course_material_manifest.json"))


def _ref(
    chunk_id: str, start: int, end: int, *, context_only: object = False,
    primary_evidence: object = False,
) -> dict:
    source = {
        "chunk_id": chunk_id,
        "source_file": CHUNKS[chunk_id]["source_file"],
        "page_start": start,
        "page_end": end,
    }
    if context_only is not False:
        source["context_only"] = context_only
    if primary_evidence is not False:
        source["primary_evidence"] = primary_evidence
    return source


def _entry(refs: object, *, concept: str = "completeness_optimality_complexity") -> dict:
    return {
        "bank_type": "candidate",
        "primary_concept": concept,
        "source_expectations": refs,
        "source_review_note": "p.53 只提供 IDDFS 的章节上下文；p.58 提供性质证据。",
    }


def test_valid_primary_evidence_without_context_passes():
    assert validate_source_roles(_entry([_ref("lec2_iddfs_properties", 58, 58)]), CHUNKS) == []


def test_manifest_backed_source_validation_rejects_unknown_material_role_and_page():
    valid = _entry([_ref("lec2_iddfs_properties", 58, 58)])
    assert validate_source_roles(valid, CHUNKS, MATERIALS) == []
    unknown = _entry([{**_ref("lec2_iddfs_properties", 58, 58), "source_file": "missing.pdf"}])
    assert "SOURCE_MATERIAL_UNKNOWN" in validate_source_roles(unknown, CHUNKS, MATERIALS)
    wrong_role_chunks = deepcopy(CHUNKS)
    wrong_role_chunks["lec2_iddfs_properties"] = {
        **wrong_role_chunks["lec2_iddfs_properties"], "source_role": "prerequisite_support",
    }
    assert "SOURCE_MATERIAL_ROLE_MISMATCH" in validate_source_roles(valid, wrong_role_chunks, MATERIALS)
    restricted_materials = deepcopy(MATERIALS)
    key = ("course_core", "ai_lec2_uninformed_search.pdf")
    restricted_materials[key]["allowed_page_range"] = {"page_start": 1, "page_end": 57}
    assert "SOURCE_PAGE_OUTSIDE_MATERIAL" in validate_source_roles(valid, CHUNKS, restricted_materials)


def test_valid_iddfs_context_plus_primary_evidence_passes():
    assert validate_source_roles(_entry([
        _ref("lec2_iddfs_strategy", 53, 53, context_only=True),
        _ref("lec2_iddfs_properties", 58, 58, primary_evidence=True),
    ]), CHUNKS) == []


def test_multiple_context_sources_plus_primary_evidence_passes():
    assert validate_source_roles(_entry([
        _ref("lec2_iddfs_strategy", 53, 53, context_only=True),
        _ref("lec2_iddfs_strategy", 54, 54, context_only=True),
        _ref("lec2_iddfs_properties", 58, 58, primary_evidence=True),
    ]), CHUNKS) == []


def test_unrelated_context_is_allowed_only_beside_primary_evidence():
    assert validate_source_roles(_entry([
        _ref("lec2_bfs_properties", 35, 35, context_only=True),
        _ref("lec2_iddfs_properties", 58, 58),
    ]), CHUNKS) == []


def test_missing_context_flag_defaults_to_primary_evidence_and_checks_topics():
    assert "SOURCE_PRIMARY_TOPIC_MISMATCH: lec2_iddfs_strategy" in validate_source_roles(
        _entry([_ref("lec2_iddfs_strategy", 53, 53)]), CHUNKS
    )


@pytest.mark.parametrize(
    "name,entry,expected",
    [
        ("context_only_alone", _entry([_ref("lec2_iddfs_strategy", 53, 53, context_only=True)]), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
        ("all_sources_context_only", _entry([_ref("lec2_iddfs_strategy", 53, 53, context_only=True), _ref("lec2_bfs_properties", 35, 35, context_only=True)]), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
        ("unrelated_context_only", _entry([_ref("lec2_bfs_properties", 35, 35, context_only=True)]), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
        ("matching_context_only", _entry([_ref("lec2_iddfs_properties", 58, 58, context_only=True)]), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
        ("unrelated_evidence_plus_context", _entry([_ref("lec2_bfs_layer_order", 31, 34), _ref("lec2_iddfs_strategy", 53, 53, context_only=True)]), "SOURCE_NO_PRIMARY_EVIDENCE"),
        ("unrelated_evidence", _entry([_ref("lec2_bfs_layer_order", 31, 34)]), "SOURCE_NO_PRIMARY_EVIDENCE"),
        ("unknown_context", _entry([{**_ref("lec2_iddfs_strategy", 53, 53, context_only=True), "chunk_id": "unknown"}]), "SOURCE_CHUNK_UNKNOWN: unknown"),
        ("filename_mismatch", _entry([{**_ref("lec2_iddfs_strategy", 53, 53, context_only=True), "source_file": "wrong.pdf"}, _ref("lec2_iddfs_properties", 58, 58)]), "SOURCE_FILENAME_MISMATCH: lec2_iddfs_strategy"),
        ("page_below_one", _entry([{**_ref("lec2_iddfs_strategy", 53, 53, context_only=True), "page_start": 0}, _ref("lec2_iddfs_properties", 58, 58)]), "SOURCE_PAGE_RANGE_INVALID: source[0]"),
        ("page_outside_chunk", _entry([{**_ref("lec2_iddfs_strategy", 53, 53, context_only=True), "page_end": 999}, _ref("lec2_iddfs_properties", 58, 58)]), "SOURCE_PAGE_OUTSIDE_CHUNK: lec2_iddfs_strategy"),
        ("reversed_pages", _entry([{**_ref("lec2_iddfs_strategy", 53, 53, context_only=True), "page_start": 54, "page_end": 53}, _ref("lec2_iddfs_properties", 58, 58)]), "SOURCE_PAGE_RANGE_INVALID: source[0]"),
        ("string_true", _entry([{**_ref("lec2_iddfs_strategy", 53, 53), "context_only": "true"}]), "SOURCE_CONTEXT_ONLY_TYPE_INVALID: source[0]"),
        ("integer_one", _entry([{**_ref("lec2_iddfs_strategy", 53, 53), "context_only": 1}]), "SOURCE_CONTEXT_ONLY_TYPE_INVALID: source[0]"),
        ("null", _entry([{**_ref("lec2_iddfs_strategy", 53, 53), "context_only": None}]), "SOURCE_CONTEXT_ONLY_TYPE_INVALID: source[0]"),
        ("empty_refs", _entry([]), "SOURCE_REFS_MISSING"),
        ("missing_refs", _entry(None), "SOURCE_REFS_MISSING"),
        ("duplicate_context", _entry([_ref("lec2_iddfs_strategy", 53, 53, context_only=True), _ref("lec2_iddfs_strategy", 53, 53, context_only=True), _ref("lec2_iddfs_properties", 58, 58)]), "SOURCE_REF_DUPLICATE: lec2_iddfs_strategy"),
        ("duplicate_evidence", _entry([_ref("lec2_iddfs_properties", 58, 58), _ref("lec2_iddfs_properties", 58, 58)]), "SOURCE_REF_DUPLICATE: lec2_iddfs_properties"),
    ],
)
def test_invalid_source_role_matrix_hits_shared_validator(name, entry, expected):
    assert expected in validate_source_roles(deepcopy(entry), CHUNKS)


def test_actual_iddfs_regressions_require_p58_primary_evidence():
    from template_acceptance_cases import PRODUCTION_TEMPLATE_ACCEPTANCE_CASES
    acceptance = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES["verify_search_algorithm_properties_v1"]
    entry = _entry(deepcopy(acceptance["source_refs"]))
    assert validate_source_roles(entry, CHUNKS) == []

    only_p53 = _entry([deepcopy(acceptance["source_refs"][0])])
    assert "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE" in validate_source_roles(only_p53, CHUNKS)

    p58_as_context = _entry([
        deepcopy(acceptance["source_refs"][0]),
        {**deepcopy(acceptance["source_refs"][1]), "context_only": True},
    ])
    issues = validate_source_roles(p58_as_context, CHUNKS)
    assert "SOURCE_PRIMARY_EVIDENCE_CONTEXT_ONLY: source[1]" in issues
    assert "SOURCE_PRIMARY_EVIDENCE_ANCHOR_MISSING" in issues


def test_context_only_is_supported_in_promoted_production_metadata_and_candidate_notes_are_required():
    production_entry = _entry([_ref("lec2_iddfs_properties", 58, 58, context_only=True)])
    production_entry["bank_type"] = "production"
    assert "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE" in validate_source_roles(production_entry, CHUNKS)

    missing_note = _entry([_ref("lec2_iddfs_properties", 58, 58)])
    missing_note["source_review_note"] = " "
    assert "SOURCE_REVIEW_NOTE_MISSING" in validate_source_roles(missing_note, CHUNKS)


def test_unknown_primary_concept_and_context_chain_order_fail_or_remain_manual_review_only():
    unknown_primary = _entry([_ref("lec2_iddfs_properties", 58, 58)], concept="unknown_concept")
    unknown_issues = validate_source_roles(unknown_primary, CHUNKS)
    assert "SOURCE_PRIMARY_TOPIC_MISMATCH: lec2_iddfs_properties" in unknown_issues
    assert "SOURCE_NO_PRIMARY_EVIDENCE" in unknown_issues

    # Source-role validation enforces authority and page validity, not an invented
    # temporal-page heuristic. A later context page is structurally valid but its
    # pedagogical chain remains a manual source-review obligation.
    later_context = _entry([
        _ref("lec2_iddfs_properties", 58, 58, primary_evidence=True),
        _ref("lec2_ucs_properties", 63, 63, context_only=True),
    ])
    assert validate_source_roles(later_context, CHUNKS) == []
