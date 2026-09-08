"""Executable P2g mutation matrix; every case crosses a real boundary."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import (
    DiagnosticTemplateError, TemplateSelectionService, load_diagnostic_templates, validate_diagnostic_templates,
)
from introai_tutor.verification_diagnostics import VerificationDiagnosticError, VerificationDiagnosticService
from tools.verification_quality_gate import lint_candidate_document
from template_acceptance_cases import PRODUCTION_TEMPLATE_ACCEPTANCE_CASES


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "data" / "diagnostic_templates.json"
CANDIDATES = ROOT / "data" / "candidate_templates" / "search_algorithms_p2f_candidates.json"


def _production():
    return json.loads(PRODUCTION.read_text(encoding="utf-8"))


def _candidate():
    p2f_ids = {
        "verify_path_cost_accumulation_v1", "verify_search_node_state_distinction_v1",
        "verify_dfs_infinite_branch_risk_v1", "verify_search_algorithm_properties_v1",
        "verify_greedy_suboptimality_v1", "verify_astar_f_value_v1",
        "verify_consistency_edge_check_v1",
    }
    templates = []
    acceptance = {}
    for item in json.loads(PRODUCTION.read_text(encoding="utf-8"))["templates"]:
        if item["id"] in p2f_ids:
            candidate = deepcopy(item)
            original_id = candidate["id"]
            candidate["id"] = "synthetic_" + original_id
            candidate["review_status"] = "candidate_draft"
            templates.append(candidate)
            acceptance[candidate["id"]] = deepcopy(PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[original_id])
    return {"schema_version": 1, "candidate_batch_id": "synthetic", "candidate_status": "pending_human_review", "templates": templates, "acceptance_cases": acceptance}


def _concepts():
    return {item["id"] for item in load_knowledge_points(ROOT / "data" / "knowledge_points.json")["knowledge_points"]}


def _write(tmp_path, document):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _candidate_lint_errors(tmp_path, document):
    return lint_candidate_document(root=ROOT, candidate_path=_write(tmp_path, document), production_path=PRODUCTION)["errors"]


def _candidate_template(document):
    return document["templates"][0]


@pytest.mark.parametrize("name,mutate", [
    ("missing_template_id", lambda d: d["templates"][0].pop("id")),
    ("empty_template_id", lambda d: d["templates"][0].__setitem__("id", "")),
    ("duplicate_template_id", lambda d: d["templates"].append(deepcopy(d["templates"][0]))),
    ("unknown_concept", lambda d: d["templates"][0].__setitem__("concept_ids", ["unknown"])),
    ("empty_concept_ids", lambda d: d["templates"][0].__setitem__("concept_ids", [])),
    ("wrong_concept_ids_type", lambda d: d["templates"][0].__setitem__("concept_ids", "bfs")),
    ("unknown_scorer", lambda d: d["templates"][0].__setitem__("deterministic_scorer", "unknown")),
    ("empty_scorer", lambda d: d["templates"][0].__setitem__("deterministic_scorer", "")),
    ("scorer_type_mismatch", lambda d: d["templates"][0].__setitem__("question_type", "multiple_choice")),
    ("missing_choices", lambda d: d["templates"][0].pop("choices")),
    ("empty_choices", lambda d: d["templates"][0].__setitem__("choices", [])),
    ("duplicate_choice_id", lambda d: d["templates"][0]["choices"].__setitem__(1, deepcopy(d["templates"][0]["choices"][0]))),
    ("empty_choice_id", lambda d: d["templates"][0]["choices"][0].__setitem__("id", "")),
    ("missing_choice_text", lambda d: d["templates"][0]["choices"][0].pop("text")),
    ("missing_expected", lambda d: d["templates"][0].pop("expected_answer")),
    ("wrong_expected_schema", lambda d: d["templates"][0].__setitem__("expected_answer", {"wrong": "x"})),
    ("expected_unknown_id", lambda d: d["templates"][0].__setitem__("expected_answer", {"choice_id": "unknown"})),
    ("illegal_review_status", lambda d: d["templates"][0].__setitem__("review_status", "illegal")),
    ("candidate_pretending_human", lambda d: d["templates"][0].__setitem__("review_status", "human_verified")),
    ("illegal_purpose", lambda d: d["templates"][0].__setitem__("purpose", "other")),
    ("malformed_misconception_rules", lambda d: d["templates"][0].__setitem__("misconception_rules", {})),
    ("missing_intents", lambda d: d["templates"][0].pop("eligible_intents")),
    ("empty_intents", lambda d: d["templates"][0].__setitem__("eligible_intents", [])),
    ("illegal_priority_type", lambda d: d["templates"][0].__setitem__("selection_priority", "1")),
], ids=[
    "missing_template_id", "empty_template_id", "duplicate_template_id", "unknown_concept",
    "empty_concept_ids", "wrong_concept_ids_type", "unknown_scorer",
    "empty_scorer", "scorer_type_mismatch", "missing_choices", "empty_choices", "duplicate_choice_id",
    "empty_choice_id", "missing_choice_text", "missing_expected", "wrong_expected_schema", "expected_unknown_id",
    "illegal_review_status", "candidate_pretending_human", "illegal_purpose", "malformed_misconception_rules", "missing_intents", "empty_intents", "illegal_priority_type",
])
def test_template_schema_mutations_hit_real_validator(name, mutate):
    document = _candidate()
    mutate(document)
    payload = {"schema_version": 1, "templates": document["templates"]}
    with pytest.raises(DiagnosticTemplateError):
        validate_diagnostic_templates(payload, valid_concept_ids=_concepts(), allowed_review_statuses={"candidate_draft"})


@pytest.mark.parametrize("name,mutate", [
    ("unauthorized_multi_concept", lambda d: d["templates"][0].__setitem__("concept_ids", ["search_problem_formulation", "breadth_first_search"])),
    ("multi_expected_duplicate", lambda d: d["templates"][0].__setitem__("deterministic_scorer", "multiple_choice_v1")),
    ("missing_source_refs", lambda d: d["acceptance_cases"][d["templates"][0]["id"]].__setitem__("source_refs", [])),
    ("unknown_source_chunk", lambda d: d["acceptance_cases"][d["templates"][0]["id"]]["source_refs"][0].__setitem__("chunk_id", "unknown")),
    ("filename_mismatch", lambda d: d["acceptance_cases"][d["templates"][0]["id"]]["source_refs"][0].__setitem__("source_file", "wrong.pdf")),
    ("page_below_one", lambda d: d["acceptance_cases"][d["templates"][0]["id"]]["source_refs"][0].__setitem__("page_start", 0)),
    ("page_outside_chunk", lambda d: d["acceptance_cases"][d["templates"][0]["id"]]["source_refs"][0].__setitem__("page_end", 9999)),
    ("reversed_page_range", lambda d: d["acceptance_cases"][d["templates"][0]["id"]]["source_refs"][0].update({"page_start": 99, "page_end": 1})),
    ("unknown_intent", lambda d: d["templates"][0].__setitem__("eligible_intents", ["unknown_intent"])),
    ("negative_priority", lambda d: d["templates"][0].__setitem__("selection_priority", -1)),
    ("missing_boundary", lambda d: d["acceptance_cases"][d["templates"][0]["id"]].__setitem__("capability_boundary", "")),
    ("illegal_evidence_strength", lambda d: d["acceptance_cases"][d["templates"][0]["id"]].__setitem__("evidence_strength", "illegal")),
    ("candidate_status", lambda d: d.__setitem__("candidate_status", "promoted")),
    ("acceptance_expected_mismatch", lambda d: d["acceptance_cases"][d["templates"][0]["id"]].__setitem__("correct_answer", "wrong")),
    ("answer_position_mismatch", lambda d: d["acceptance_cases"][d["templates"][0]["id"]].__setitem__("expected_answer_position", 1)),
    ("candidate_production_collision", lambda d: d["templates"][0].__setitem__("id", "verify_bfs_frontier_choice_v1")),
], ids=[
    "unauthorized_multi_concept", "multi_expected_duplicate", "missing_source_refs", "unknown_source_chunk", "filename_mismatch",
    "page_below_one", "page_outside_chunk", "reversed_page_range", "unknown_intent", "negative_priority",
    "missing_boundary", "illegal_evidence_strength", "candidate_status", "acceptance_expected_mismatch", "answer_position_mismatch", "candidate_production_collision",
])
def test_candidate_metadata_mutations_hit_real_candidate_lint(tmp_path, name, mutate):
    document = _candidate()
    if name == "multi_expected_duplicate":
        template = document["templates"][0]
        template["question_type"] = "multiple_choice"
        template["deterministic_scorer"] = "multiple_choice_v1"
        template["expected_answer"] = {"choice_ids": [template["choices"][0]["id"], template["choices"][0]["id"]]}
        template["misconception_rules"] = []
        document["acceptance_cases"][template["id"]]["deterministic_scorer"] = "multiple_choice_v1"
        document["acceptance_cases"][template["id"]]["question_type"] = "multiple_choice"
        document["acceptance_cases"][template["id"]]["correct_answer"] = template["expected_answer"]["choice_ids"]
    else:
        mutate(document)
    assert _candidate_lint_errors(tmp_path, document)


def test_production_candidate_status_and_service_isolation_paths():
    production = _production()
    production["templates"][0]["review_status"] = "candidate_draft"
    with pytest.raises(DiagnosticTemplateError):
        validate_diagnostic_templates(production, valid_concept_ids=_concepts())
    candidate = _candidate()["templates"][0]
    with pytest.raises(VerificationDiagnosticError):
        VerificationDiagnosticService(templates=[candidate])
    malformed = _production()["templates"][0]
    malformed["deterministic_scorer"] = "unknown"
    with pytest.raises(DiagnosticTemplateError):
        TemplateSelectionService(templates_data={"schema_version": 1, "templates": [malformed]}, valid_concept_ids=_concepts())


def test_candidate_document_is_rejected_by_production_loader():
    with pytest.raises(DiagnosticTemplateError):
        load_diagnostic_templates(CANDIDATES, valid_concept_ids=_concepts())


def _iddfs_refs(document):
    return document["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"]["source_refs"]


@pytest.mark.parametrize("name,mutate,expected", [
    ("all_context", lambda d: [ref.__setitem__("context_only", True) for ref in _iddfs_refs(d)], "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
    ("remove_evidence", lambda d: d["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"].__setitem__("source_refs", [_iddfs_refs(d)[0]]), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
    ("primary_as_context", lambda d: _iddfs_refs(d)[1].__setitem__("context_only", True), "SOURCE_PRIMARY_EVIDENCE_ANCHOR_MISSING"),
    ("evidence_unrelated", lambda d: _iddfs_refs(d)[1].update({"chunk_id": "lec2_bfs_layer_order", "page_start": 31, "page_end": 34}), "SOURCE_PRIMARY_EVIDENCE_ANCHOR_MISSING"),
    ("unknown_context", lambda d: _iddfs_refs(d)[0].__setitem__("chunk_id", "unknown"), "SOURCE_CHUNK_UNKNOWN"),
    ("unknown_evidence", lambda d: _iddfs_refs(d)[1].__setitem__("chunk_id", "unknown"), "SOURCE_CHUNK_UNKNOWN"),
    ("context_invalid_page", lambda d: _iddfs_refs(d)[0].__setitem__("page_end", 999), "SOURCE_PAGE_OUTSIDE_CHUNK"),
    ("evidence_invalid_page", lambda d: _iddfs_refs(d)[1].__setitem__("page_end", 999), "SOURCE_PAGE_OUTSIDE_CHUNK"),
    ("direct_without_evidence", lambda d: (d["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"].__setitem__("evidence_strength", "direct"), d["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"].__setitem__("source_refs", [_iddfs_refs(d)[0]])), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
    ("supported_without_evidence", lambda d: d["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"].__setitem__("source_refs", [_iddfs_refs(d)[0]]), "SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE"),
    ("context_wrong_type", lambda d: _iddfs_refs(d)[0].__setitem__("context_only", "true"), "SOURCE_CONTEXT_ONLY_TYPE_INVALID"),
    ("context_missing_note", lambda d: d["acceptance_cases"]["synthetic_verify_search_algorithm_properties_v1"].__setitem__("source_review_note", ""), "SOURCE_REVIEW_NOTE_MISSING"),
    ("duplicate_context", lambda d: _iddfs_refs(d).append(deepcopy(_iddfs_refs(d)[0])), "SOURCE_REF_DUPLICATE"),
    ("duplicate_evidence", lambda d: _iddfs_refs(d).append(deepcopy(_iddfs_refs(d)[1])), "SOURCE_REF_DUPLICATE"),
], ids=[
    "all_context", "remove_evidence", "primary_as_context", "evidence_unrelated",
    "unknown_context", "unknown_evidence", "context_invalid_page", "evidence_invalid_page",
    "direct_without_evidence", "supported_without_evidence", "context_wrong_type",
    "context_missing_note", "duplicate_context", "duplicate_evidence",
])
def test_source_role_mutations_fail_closed_in_candidate_lint(tmp_path, name, mutate, expected):
    document = _candidate()
    mutate(document)
    assert any(expected in error for error in _candidate_lint_errors(tmp_path, document))
