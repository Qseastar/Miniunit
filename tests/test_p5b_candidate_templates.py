"""Offline promotion and regression contracts for the P5b production batch."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from introai_tutor.diagnostic_state_integration import DiagnosticStateIntegrationService
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import (
    DiagnosticTemplateError,
    TemplateSelectionService,
    load_diagnostic_templates,
)
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError,
    VerificationDiagnosticService,
    score_verification_answer,
)
from tools.verification_benchmark import load_candidate_document

from template_acceptance_cases import PRODUCTION_TEMPLATE_ACCEPTANCE_CASES


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "data/diagnostic_templates.json"
STAGING = ROOT / "data/candidate_templates/search_algorithms_p5b_candidates.json"
P5B_IDS = {
    "verify_local_search_final_state_focus_v1",
    "verify_hill_climbing_stop_at_local_best_v1",
    "verify_simulated_annealing_worse_successor_v1",
    "verify_evolutionary_search_parent_cycle_v1",
    "verify_minimax_max_min_value_choice_v1",
    "verify_alpha_beta_prune_when_bounds_cross_v1",
    "verify_mcts_four_stage_order_v1",
    "verify_ucb_upper_bound_selection_v1",
}


def _concept_ids() -> set[str]:
    return {
        item["id"]
        for item in load_knowledge_points(ROOT / "data/knowledge_points.json")["knowledge_points"]
    }


def _production() -> dict[str, dict]:
    document = load_diagnostic_templates(PRODUCTION, valid_concept_ids=_concept_ids())
    return {item["id"]: item for item in document["templates"]}


def _source_refs() -> dict[str, dict]:
    chunks = {
        item["id"]: item
        for item in json.loads((ROOT / "data/course_chunks.json").read_text(encoding="utf-8"))["chunks"]
    }
    return chunks


def test_p5b_staging_is_promoted_and_empty():
    assert json.loads(STAGING.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "candidate_batch_id": "search_algorithms_p5b_a",
        "candidate_status": "promoted_to_production",
        "templates": [],
        "acceptance_cases": {},
    }
    assert load_candidate_document(STAGING, root=ROOT)["templates"] == []
    with pytest.raises(DiagnosticTemplateError):
        load_diagnostic_templates(STAGING, valid_concept_ids=_concept_ids())


def test_p5b_templates_are_human_verified_unique_and_selector_visible():
    templates = _production()
    assert len(templates) == 28
    assert P5B_IDS <= set(templates)
    assert len(set(templates)) == 28
    assert all(templates[item]["review_status"] == "human_verified" for item in P5B_IDS)
    selector = TemplateSelectionService(
        templates_data={"schema_version": 1, "templates": list(templates.values())},
        valid_concept_ids=_concept_ids(),
    )
    selected = {
        item["id"]
        for template_id in P5B_IDS
        for intent in templates[template_id]["eligible_intents"]
        for item in selector.select(
            concept_ids=templates[template_id]["concept_ids"], intent=intent
        )
    }
    assert P5B_IDS <= selected


@pytest.mark.parametrize("template_id", sorted(P5B_IDS))
def test_p5b_production_source_and_boundary_contract(template_id):
    template = _production()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]
    assert template["concept_ids"] == [case["primary_concept_id"]]
    assert template["question_type"] == "single_choice"
    assert template["deterministic_scorer"] == "single_choice_v1"
    assert case["evidence_strength"] in {"direct", "direct_plus_closed_instance"}
    assert case["source_refs"]
    chunks = _source_refs()
    for ref in case["source_refs"]:
        chunk = chunks[ref["chunk_id"]]
        assert ref["source_file"] == chunk["source_file"]
        assert ref["page_start"] >= chunk["page_start"]
        assert ref["page_end"] <= chunk["page_end"]
        assert case["primary_concept_id"] in chunk["topic_ids"]
    assert case["capability_boundary"].strip()


@pytest.mark.parametrize("template_id", sorted(P5B_IDS))
def test_p5b_every_choice_and_malformed_answer_fail_closed(template_id):
    template = _production()[template_id]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template_id]
    expected = template["expected_answer"]["choice_id"]
    for choice in template["choices"]:
        result = score_verification_answer(template=template, answer=choice["id"])
        assert result["passed"] is (choice["id"] == expected)
        assert result["score"] == (1.0 if choice["id"] == expected else 0.0)
    with pytest.raises(VerificationDiagnosticError):
        score_verification_answer(
            template=template, answer=deepcopy(case["malformed_answer"])
        )


def test_p5b_local_search_final_revision_is_locked():
    template = _production()["verify_local_search_final_state_focus_v1"]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template["id"]]
    assert template["expected_answer"] == {"choice_id": "candidate_solution_quality"}
    assert template["choices"][1]["id"] == "candidate_solution_quality"
    assert "总体介绍" in template["prompt"]
    assert "Hill Climbing" in case["capability_boundary"]
    assert "path/frontier/exhaustive" in case["capability_boundary"]


def test_p5b_static_answer_positions_are_preserved():
    templates = _production()
    expected_positions = {
        "verify_local_search_final_state_focus_v1": 2,
        "verify_hill_climbing_stop_at_local_best_v1": 3,
        "verify_simulated_annealing_worse_successor_v1": 4,
        "verify_evolutionary_search_parent_cycle_v1": 1,
        "verify_minimax_max_min_value_choice_v1": 2,
        "verify_alpha_beta_prune_when_bounds_cross_v1": 3,
        "verify_mcts_four_stage_order_v1": 2,
        "verify_ucb_upper_bound_selection_v1": 1,
    }
    for template_id, position in expected_positions.items():
        choices = [item["id"] for item in templates[template_id]["choices"]]
        assert choices.index(templates[template_id]["expected_answer"]["choice_id"]) + 1 == position


def test_p5b_verification_and_evidence_integration_for_new_template():
    template = _production()["verify_local_search_final_state_focus_v1"]
    case = PRODUCTION_TEMPLATE_ACCEPTANCE_CASES[template["id"]]
    service = VerificationDiagnosticService(templates=[template])
    started = service.start(template_ids=[template["id"]])
    completed = service.submit(
        session=started["session"],
        answer=case["correct_answer"],
        submitted_template_id=template["id"],
    )
    assert completed["status"] == "completed"
    assert completed["summary"]["evidence_eligible"] is True
    state = {
        "student_id": "p5b-test",
        "course_id": "intro_ai",
        "mastery": {},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }
    result = DiagnosticStateIntegrationService(
        knowledge_data=load_knowledge_points(ROOT / "data/knowledge_points.json"),
        recommendation_fn=lambda *_args: None,
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])
    assert result["updates"][0]["selected_signal"] == 1.0
    assert result["learner_state"]["mastery"]["local_search"] == 0.35
