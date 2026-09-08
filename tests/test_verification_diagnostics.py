import copy
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.diagnostic_state_integration import DiagnosticStateIntegrationService
from introai_tutor.template_selection import load_diagnostic_templates
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError,
    VerificationDiagnosticService,
)


ROOT = Path(__file__).resolve().parents[1]


def _service():
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    concepts = {point["id"] for point in knowledge["knowledge_points"]}
    templates = load_diagnostic_templates(
        ROOT / "data" / "diagnostic_templates.json", valid_concept_ids=concepts
    )
    return VerificationDiagnosticService(templates=templates["templates"])


@pytest.mark.smoke
def test_verified_choices_create_evidence_summary_only_at_completion():
    service = _service()
    started = service.start(template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])
    second = service.submit(session=started["session"], answer="A", submitted_template_id="verify_bfs_frontier_choice_v1")
    third = service.submit(session=second["session"], answer="equal_cost", submitted_template_id="verify_bfs_equal_cost_condition_v1")
    completed = service.submit(session=third["session"], answer="A", submitted_template_id="verify_ucs_min_g_choice_v1")

    assert started["purpose"] == "mastery_verification"
    assert started["evidence_eligible"] is True
    assert completed["status"] == "completed"
    assert completed["summary"]["evidence_eligible"] is True
    assert completed["summary"]["concept_observations"]["breadth_first_search"] == [1.0, 1.0]


def test_reviewed_template_sequence_is_stable_and_ends_with_ucs_min_g():
    service = _service()
    started = service.start(template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])
    second = service.submit(session=started["session"], answer="A", submitted_template_id="verify_bfs_frontier_choice_v1")
    third = service.submit(session=second["session"], answer="equal_cost", submitted_template_id="verify_bfs_equal_cost_condition_v1")

    assert started["session"]["template_ids"] == [
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ]
    assert second["question"]["id"] == "verify_bfs_equal_cost_condition_v1"
    assert second["question"]["template_id"] == "verify_bfs_equal_cost_condition_v1"
    assert second["question"]["concept_ids"] == [
        "breadth_first_search", "completeness_optimality_complexity"
    ]
    assert [choice["text"] for choice in second["question"]["choices"]] == [
        "所有动作或边的代价相同", "所有边权非负", "图中不存在环", "使用优先队列"
    ]
    assert third["question"]["id"] == "verify_ucs_min_g_choice_v1"
    assert third["question"]["template_id"] == "verify_ucs_min_g_choice_v1"
    assert "UCS" in third["question"]["prompt"] and "g(n)" in third["question"]["prompt"]
    assert "BFS 找到的最少步数路径" not in third["question"]["prompt"]
    assert [choice["text"] for choice in third["question"]["choices"]] == ["B", "A", "C"]
    assert third["question"]["concept_ids"] == ["uniform_cost_search"]


@pytest.mark.parametrize(
    ("template_id", "answer", "concept_id"),
    [
        (
            "verify_graph_search_repeated_state_handling_v1",
            "discard_repeat",
            "tree_search_vs_graph_search",
        ),
        (
            "verify_dfs_frontier_choice_v1",
            "node_c",
            "depth_first_search",
        ),
        (
            "verify_iddfs_depth_limit_schedule_v1",
            "restart_limit_2",
            "iterative_deepening_search",
        ),
    ],
)
def test_p2d_promoted_single_choice_templates_start_and_complete_with_primary_evidence(
    template_id, answer, concept_id
):
    service = _service()
    started = service.start(template_ids=[template_id])
    completed = service.submit(
        session=started["session"],
        answer=answer,
        submitted_template_id=template_id,
    )

    assert started["question"]["template_id"] == template_id
    assert started["question"]["question_type"] == "single_choice"
    assert started["question"]["concept_ids"] == [concept_id]
    assert completed["status"] == "completed"
    assert completed["evaluation"]["passed"] is True
    assert completed["summary"]["concept_observations"] == {
        concept_id: [1.0]
    }


def test_submitted_template_and_choice_must_match_current_session_without_mutation():
    service = _service()
    started = service.start(template_ids=[
        "verify_bfs_frontier_choice_v1", "verify_bfs_equal_cost_condition_v1"
    ])
    original = copy.deepcopy(started["session"])

    with pytest.raises(VerificationDiagnosticError, match="submitted template"):
        service.submit(
            session=started["session"], answer="A",
            submitted_template_id="verify_bfs_equal_cost_condition_v1",
        )
    assert started["session"] == original

    with pytest.raises(VerificationDiagnosticError, match="displayed choice IDs"):
        service.submit(
            session=started["session"], answer="equal_cost",
            submitted_template_id="verify_bfs_frontier_choice_v1",
        )
    assert started["session"] == original


@pytest.mark.parametrize("answer", [None, "", "not_a_displayed_choice"])
def test_missing_or_invalid_choice_is_rejected_without_creating_an_attempt(answer):
    service = _service()
    started = service.start(template_ids=["verify_bfs_frontier_choice_v1"])
    original = copy.deepcopy(started["session"])

    with pytest.raises(VerificationDiagnosticError):
        service.submit(
            session=started["session"],
            answer=answer,
            submitted_template_id="verify_bfs_frontier_choice_v1",
        )

    assert started["session"] == original
    assert started["session"]["history"] == []
    assert started["session"]["attempt_in_step"] == 0
    assert started["session"]["step_index"] == 0


def test_retry_starts_a_new_attempt_without_a_persisted_choice():
    service = _service()
    started = service.start(template_ids=["verify_bfs_frontier_choice_v1"])
    retry_ready = service.submit(
        session=started["session"],
        answer="C",
        submitted_template_id="verify_bfs_frontier_choice_v1",
    )
    retry = service.choose_hint_retry(
        session=retry_ready["session"], template_id="verify_bfs_frontier_choice_v1"
    )

    assert retry["question"]["attempt_number"] == 2
    assert retry["session"]["history"][-1]["selected_choice_id"] == "C"
    assert "selected_choice_id" not in retry["session"]


def test_completed_summary_records_template_bound_evidence_for_each_answer():
    service = _service()
    result = service.start(template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])
    for answer, template_id in (
        ("A", "verify_bfs_frontier_choice_v1"),
        ("equal_cost", "verify_bfs_equal_cost_condition_v1"),
        ("A", "verify_ucs_min_g_choice_v1"),
    ):
        result = service.submit(
            session=result["session"], answer=answer, submitted_template_id=template_id
        )

    records = result["summary"]["observation_records"]
    assert [(item["step_index"], item["template_id"], item["selected_choice_id"], item["expected_choice_id"], item["score"]) for item in records] == [
        (0, "verify_bfs_frontier_choice_v1", "A", "A", 1.0),
        (1, "verify_bfs_equal_cost_condition_v1", "equal_cost", "equal_cost", 1.0),
        (2, "verify_ucs_min_g_choice_v1", "A", "A", 1.0),
    ]
    assert records[2]["concept_ids"] == ["uniform_cost_search"]


@pytest.mark.smoke
def test_wrong_reviewed_choice_records_only_its_explicit_misconception_mapping():
    service = _service()
    retry = service.submit(
        session=service.start(template_ids=["verify_bfs_frontier_choice_v1"])["session"],
        answer="C", submitted_template_id="verify_bfs_frontier_choice_v1",
    )

    assert retry["evaluation"]["passed"] is False
    assert retry["evaluation"]["misconception_ids"] == ["bfs_is_depth_first"]
    assert retry["evaluation"]["assistance_level"] == "none"
    assert retry["session"]["interaction_state"] == "retry_ready"
    assert "pending_assistance" not in retry["session"]


@pytest.mark.smoke
def test_hint_assisted_retry_passes_but_p5b_selects_prior_unassisted_zero():
    service = _service()
    first = service.start(template_ids=["verify_bfs_frontier_choice_v1"])
    retry = service.submit(session=first["session"], answer="C", submitted_template_id="verify_bfs_frontier_choice_v1")
    retry_ready = service.choose_hint_retry(
        session=retry["session"], template_id="verify_bfs_frontier_choice_v1"
    )
    completed = service.submit(session=retry_ready["session"], answer="A", submitted_template_id="verify_bfs_frontier_choice_v1")

    history = completed["session"]["history"]
    assert [(item["score"], item["assisted"], item["assistance_level"]) for item in history] == [
        (0.0, False, "none"),
        (1.0, True, "hint"),
    ]
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    state = {
        "student_id": "verification-test",
        "course_id": "intro_ai",
        "mastery": {"breadth_first_search": 0.0},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }
    update = DiagnosticStateIntegrationService(
        knowledge_data=knowledge, recommendation_fn=lambda *_args: None
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])

    assert update["updates"][0]["selected_signal"] == 0.0
    assert update["updates"][0]["selection_reason"] == "last_unassisted_observation"


def test_first_attempt_correct_is_unassisted_and_selects_one():
    service = _service()
    completed = service.submit(
        session=service.start(template_ids=["verify_bfs_frontier_choice_v1"])["session"],
        answer="A", submitted_template_id="verify_bfs_frontier_choice_v1",
    )

    assert completed["session"]["history"][0]["assisted"] is False
    assert completed["session"]["history"][0]["assistance_level"] == "none"
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    state = {
        "student_id": "verification-test",
        "course_id": "intro_ai",
        "mastery": {}, "misconceptions": [], "learning_evidence": [],
        "preferred_style": "visual_example",
    }
    update = DiagnosticStateIntegrationService(
        knowledge_data=knowledge, recommendation_fn=lambda *_args: None
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])
    assert update["updates"][0]["selected_signal"] == 1.0


def test_hint_provenance_is_consumed_once_and_cannot_cross_template_or_be_forged():
    service = _service()
    started = service.start(template_ids=[
        "verify_bfs_frontier_choice_v1", "verify_bfs_equal_cost_condition_v1"
    ])
    retry = service.submit(session=started["session"], answer="C", submitted_template_id="verify_bfs_frontier_choice_v1")
    retry_ready = service.choose_hint_retry(
        session=retry["session"], template_id="verify_bfs_frontier_choice_v1"
    )
    second_question = service.submit(session=retry_ready["session"], answer="A", submitted_template_id="verify_bfs_frontier_choice_v1")

    assert "pending_assistance" not in second_question["session"]
    assert second_question["session"]["history"][-1]["assisted"] is True
    forged = copy.deepcopy(retry_ready["session"])
    forged["pending_assistance"] = {
        "level": "hint", "source": "deterministic_feedback",
        "template_id": "verify_ucs_min_g_choice_v1",
    }
    with pytest.raises(VerificationDiagnosticError, match="template"):
        service.submit(session=forged, answer="A", submitted_template_id="verify_bfs_frontier_choice_v1")

    for invalid in (
        {"level": "scaffold", "source": "deterministic_feedback", "template_id": "verify_bfs_frontier_choice_v1"},
        {"level": "hint", "source": "semantic_advisory", "template_id": "verify_bfs_frontier_choice_v1"},
        {"level": "hint", "source": "deterministic_feedback"},
    ):
        forged = copy.deepcopy(retry_ready["session"])
        forged["pending_assistance"] = invalid
        with pytest.raises(VerificationDiagnosticError, match="pending_assistance"):
            service.submit(session=forged, answer="A", submitted_template_id="verify_bfs_frontier_choice_v1")


@pytest.mark.smoke
def test_first_attempt_reveal_creates_no_observation_and_acknowledgement_completes():
    service = _service()
    started = service.start(template_ids=["verify_bfs_frontier_choice_v1"])
    revealed = service.request_reveal(
        session=started["session"], template_id="verify_bfs_frontier_choice_v1"
    )

    assert revealed["session"]["interaction_state"] == "revealing"
    assert revealed["session"]["history"] == []
    assert revealed["session"]["reveal"]["reveal_reason"] == "requested_before_attempt"
    assert service.current_reveal(session=revealed["session"]) == {
        "template_id": "verify_bfs_frontier_choice_v1",
        "correct_choice_text": "A",
        "explanation": "BFS 按先进先出的顺序处理 frontier，因此 A 先于 B、C 被扩展。",
        "reveal_reason": "requested_before_attempt",
        "assistance_level": "reveal",
        "assistance_source": "model_answer",
    }
    with pytest.raises(VerificationDiagnosticError, match="not allowed"):
        service.submit(
            session=revealed["session"], answer="A",
            submitted_template_id="verify_bfs_frontier_choice_v1",
        )
    completed = service.acknowledge_reveal(
        session=revealed["session"], template_id="verify_bfs_frontier_choice_v1"
    )
    assert completed["status"] == "completed"
    assert completed["summary"]["concept_observations"] == {}
    assert completed["summary"]["no_observation_reason"] == "all_revealed"
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    state = {
        "student_id": "reveal-test", "course_id": "intro_ai",
        "mastery": {}, "misconceptions": [], "learning_evidence": [],
        "preferred_style": "visual_example",
    }
    update = DiagnosticStateIntegrationService(
        knowledge_data=knowledge, recommendation_fn=lambda *_args: None
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])
    assert update["updates"] == []
    assert update["learner_state"] == state


def test_wrong_then_reveal_preserves_only_unassisted_zero_evidence():
    service = _service()
    started = service.start(template_ids=["verify_bfs_frontier_choice_v1"])
    wrong = service.submit(
        session=started["session"], answer="C",
        submitted_template_id="verify_bfs_frontier_choice_v1",
    )
    revealed = service.request_reveal(
        session=wrong["session"], template_id="verify_bfs_frontier_choice_v1"
    )
    completed = service.acknowledge_reveal(
        session=revealed["session"], template_id="verify_bfs_frontier_choice_v1"
    )

    assert revealed["session"]["reveal"]["reveal_reason"] == "requested_after_wrong"
    assert [(entry["score"], entry["assisted"]) for entry in completed["session"]["history"]] == [(0.0, False)]
    assert completed["summary"]["concept_observations"]["breadth_first_search"] == [0.0]


def test_two_wrong_attempts_enter_reveal_without_auto_advance():
    service = _service()
    started = service.start(template_ids=[
        "verify_bfs_frontier_choice_v1", "verify_bfs_equal_cost_condition_v1"
    ])
    wrong = service.submit(
        session=started["session"], answer="C",
        submitted_template_id="verify_bfs_frontier_choice_v1",
    )
    retry = service.choose_hint_retry(
        session=wrong["session"], template_id="verify_bfs_frontier_choice_v1"
    )
    revealed = service.submit(
        session=retry["session"], answer="B",
        submitted_template_id="verify_bfs_frontier_choice_v1",
    )

    assert revealed["session"]["interaction_state"] == "revealing"
    assert revealed["session"]["step_index"] == 0
    assert revealed["session"]["reveal"]["reveal_reason"] == "attempts_exhausted"
    assert [(entry["score"], entry["assisted"]) for entry in revealed["session"]["history"]] == [
        (0.0, False), (0.0, True)
    ]
    next_step = service.acknowledge_reveal(
        session=revealed["session"], template_id="verify_bfs_frontier_choice_v1"
    )
    assert next_step["question"]["template_id"] == "verify_bfs_equal_cost_condition_v1"
    assert next_step["session"]["interaction_state"] == "answering"


def test_reveal_session_tampering_is_rejected_without_mutating_input():
    service = _service()
    revealed = service.request_reveal(
        session=service.start(template_ids=["verify_bfs_frontier_choice_v1"])["session"],
        template_id="verify_bfs_frontier_choice_v1",
    )
    forged = copy.deepcopy(revealed["session"])
    forged["reveal"]["template_id"] = "verify_ucs_min_g_choice_v1"

    with pytest.raises(VerificationDiagnosticError, match="reveal template"):
        service.acknowledge_reveal(
            session=forged, template_id="verify_bfs_frontier_choice_v1"
        )
    assert revealed["session"]["reveal"]["template_id"] == "verify_bfs_frontier_choice_v1"
