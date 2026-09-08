import copy
import json
from pathlib import Path

import pytest

from introai_tutor.diagnostic_state_integration import (
    DiagnosticStateIntegrationService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import (
    DiagnosticTemplateError,
    validate_diagnostic_templates,
)
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError,
    VerificationDiagnosticService,
)


ROOT = Path(__file__).resolve().parents[1]
CONCEPT_ID = "breadth_first_search"


def _template(scorer_name, *, expected_answer=None):
    question_types = {
        "multiple_choice_v1": "multiple_choice",
        "numeric_answer_v1": "numeric_answer",
        "ordering_v1": "ordering",
    }
    choices = (
        []
        if scorer_name == "numeric_answer_v1"
        else [
            {"id": "A", "text": "选项 A"},
            {"id": "B", "text": "选项 B"},
            {"id": "C", "text": "选项 C"},
            {"id": "D", "text": "选项 D"},
        ]
    )
    defaults = {
        "multiple_choice_v1": {"choice_ids": ["A", "C"]},
        "numeric_answer_v1": {"value": 5},
        "ordering_v1": {"ordered_choice_ids": ["A", "B", "C"]},
    }
    return {
        "id": f"test_{scorer_name}",
        "schema_version": 1,
        "review_status": "human_verified",
        "purpose": "mastery_verification",
        "concept_ids": [CONCEPT_ID],
        "eligible_intents": ["diagnostic_request"],
        "selection_priority": 1,
        "question_type": question_types[scorer_name],
        "prompt": "仅用于离线 scorer contract 测试。",
        "choices": choices,
        "expected_answer": (
            copy.deepcopy(defaults[scorer_name])
            if expected_answer is None
            else copy.deepcopy(expected_answer)
        ),
        "deterministic_scorer": scorer_name,
        "misconception_rules": [],
        "teaching_support": {
            "hint": "请重新检查受控输入。",
            "explanation": "这是虚构测试数据，不是生产诊断题。",
        },
        "benchmark_case_ids": [f"case_{scorer_name}"],
    }


def _validate(template):
    validate_diagnostic_templates(
        {"schema_version": 1, "templates": [template]},
        valid_concept_ids={CONCEPT_ID},
    )


def _service(template):
    _validate(template)
    return VerificationDiagnosticService(templates=[template])


def _submit_once(template, answer):
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    return service, started, service.submit(
        session=started["session"],
        answer=answer,
        submitted_template_id=template["id"],
    )


def _learner_state():
    return {
        "student_id": "scorer-foundation-test",
        "course_id": "intro_ai",
        "mastery": {},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }


def test_multiple_choice_exact_set_match_is_order_independent_and_repeatable():
    template = _template("multiple_choice_v1")
    original_template = copy.deepcopy(template)
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    answer = ["C", "A"]
    original_answer = copy.deepcopy(answer)
    original_session = copy.deepcopy(started["session"])

    first = service.submit(
        session=started["session"],
        answer=answer,
        submitted_template_id=template["id"],
    )
    second = service.submit(
        session=started["session"],
        answer=answer,
        submitted_template_id=template["id"],
    )

    assert first == second
    assert first["evaluation"]["score"] == 1.0
    assert first["evaluation"]["passed"] is True
    assert first["session"]["history"][0]["submitted_answer"] == ["C", "A"]
    json.dumps(first["session"])
    assert answer == original_answer
    assert template == original_template
    assert started["session"] == original_session


@pytest.mark.parametrize(
    "answer",
    [
        ["A"],
        ["A", "B", "C"],
        ["B", "C"],
    ],
)
def test_multiple_choice_fewer_extra_or_wrong_known_choices_score_zero(answer):
    _service, _started, result = _submit_once(
        _template("multiple_choice_v1"), answer
    )

    assert result["evaluation"]["score"] == 0.0
    assert result["evaluation"]["passed"] is False


@pytest.mark.parametrize(
    "answer, message",
    [
        (["A", "A"], "duplicate"),
        ([], "non-empty list"),
        ("AC", "non-empty list"),
        (["A", "unknown"], "unknown IDs"),
    ],
)
def test_multiple_choice_malformed_answers_are_rejected_without_attempt(
    answer, message
):
    template = _template("multiple_choice_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    original = copy.deepcopy(started["session"])

    with pytest.raises(VerificationDiagnosticError, match=message):
        service.submit(
            session=started["session"],
            answer=answer,
            submitted_template_id=template["id"],
        )

    assert started["session"] == original
    assert started["session"]["history"] == []


@pytest.mark.parametrize(
    "expected",
    [
        {"choice_ids": []},
        {"choice_ids": ["A", "A"]},
        {"choice_ids": ["unknown"]},
        {"choice_id": "A"},
    ],
)
def test_multiple_choice_invalid_expected_answer_is_rejected(expected):
    with pytest.raises(DiagnosticTemplateError, match="expected_answer"):
        _validate(_template("multiple_choice_v1", expected_answer=expected))


@pytest.mark.parametrize(
    "expected, answer",
    [
        ({"value": 5}, 5),
        ({"value": 5}, "5.0"),
        ({"value": 1.25}, "1.25"),
        ({"value": -2}, "-2"),
        ({"value": 0}, 0),
        ({"value": 5, "absolute_tolerance": 0.1}, "4.9"),
        ({"value": 5, "absolute_tolerance": 0.1}, "5.1"),
    ],
)
def test_numeric_answer_accepts_exact_and_absolute_tolerance_boundary(
    expected, answer
):
    _service, _started, result = _submit_once(
        _template("numeric_answer_v1", expected_answer=expected), answer
    )

    assert result["evaluation"]["score"] == 1.0
    assert result["evaluation"]["passed"] is True


@pytest.mark.parametrize(
    "expected, answer",
    [
        ({"value": 5}, "5.01"),
        ({"value": 5, "absolute_tolerance": 0.1}, "4.899"),
        ({"value": -2}, "-1"),
        ({"value": 0}, "0.01"),
    ],
)
def test_numeric_answer_outside_exact_or_tolerance_scores_zero(expected, answer):
    _service, _started, result = _submit_once(
        _template("numeric_answer_v1", expected_answer=expected), answer
    )

    assert result["evaluation"]["score"] == 0.0
    assert result["evaluation"]["passed"] is False


@pytest.mark.parametrize(
    "answer",
    ["", "   ", "1+1", "1e2", True, float("nan"), float("inf"), -float("inf"), None],
)
def test_numeric_answer_rejects_malformed_nonfinite_or_non_decimal_input(answer):
    template = _template("numeric_answer_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    original = copy.deepcopy(started["session"])

    with pytest.raises(VerificationDiagnosticError, match="numeric answer"):
        service.submit(
            session=started["session"],
            answer=answer,
            submitted_template_id=template["id"],
        )

    assert started["session"] == original
    assert started["session"]["history"] == []


@pytest.mark.parametrize(
    "expected, message",
    [
        ({"value": True}, "numeric expected"),
        ({"value": "5"}, "numeric expected"),
        ({"value": float("nan")}, "numeric expected"),
        ({"value": float("inf")}, "numeric expected"),
        ({"value": 5, "absolute_tolerance": -0.1}, "absolute_tolerance"),
        ({"value": 5, "absolute_tolerance": True}, "absolute_tolerance"),
        ({}, "expected_answer"),
    ],
)
def test_numeric_invalid_expected_answer_or_tolerance_is_rejected(
    expected, message
):
    with pytest.raises(DiagnosticTemplateError, match=message):
        _validate(_template("numeric_answer_v1", expected_answer=expected))


def test_numeric_answer_repeated_scoring_is_identical():
    template = _template(
        "numeric_answer_v1",
        expected_answer={"value": 3.5, "absolute_tolerance": 0.01},
    )
    service = _service(template)
    started = service.start(template_ids=[template["id"]])

    first = service.submit(
        session=started["session"],
        answer="3.50",
        submitted_template_id=template["id"],
    )
    second = service.submit(
        session=started["session"],
        answer="3.50",
        submitted_template_id=template["id"],
    )

    assert first == second
    json.dumps(first["summary"])


@pytest.mark.parametrize(
    "answer, expected_score",
    [
        (["A", "B", "C"], 1.0),
        (["B", "A", "C"], 0.0),
        (["C", "B", "A"], 0.0),
        (["A", "B"], 0.0),
        (["A", "B", "C", "D"], 0.0),
    ],
)
def test_ordering_requires_exact_complete_sequence(answer, expected_score):
    _service, _started, result = _submit_once(_template("ordering_v1"), answer)

    assert result["evaluation"]["score"] == expected_score
    assert result["evaluation"]["passed"] is (expected_score == 1.0)


@pytest.mark.parametrize(
    "answer, message",
    [
        (["A", "A", "C"], "duplicate"),
        (["A", "unknown", "C"], "unknown IDs"),
        ([], "non-empty list"),
        ("ABC", "non-empty list"),
    ],
)
def test_ordering_rejects_duplicate_unknown_empty_or_non_list(answer, message):
    template = _template("ordering_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])

    with pytest.raises(VerificationDiagnosticError, match=message):
        service.submit(
            session=started["session"],
            answer=answer,
            submitted_template_id=template["id"],
        )

    assert started["session"]["history"] == []


@pytest.mark.parametrize(
    "expected",
    [
        {"ordered_choice_ids": []},
        {"ordered_choice_ids": ["A", "A"]},
        {"ordered_choice_ids": ["A", "unknown"]},
        {"choice_ids": ["A", "B"]},
    ],
)
def test_ordering_invalid_expected_answer_is_rejected(expected):
    with pytest.raises(DiagnosticTemplateError, match="expected_answer"):
        _validate(_template("ordering_v1", expected_answer=expected))


def test_ordering_repeated_scoring_is_identical_and_json_serializable():
    template = _template("ordering_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])

    first = service.submit(
        session=started["session"],
        answer=["A", "B", "C"],
        submitted_template_id=template["id"],
    )
    second = service.submit(
        session=started["session"],
        answer=["A", "B", "C"],
        submitted_template_id=template["id"],
    )

    assert first == second
    json.dumps(first["session"])


@pytest.mark.parametrize(
    "scorer_name, answer",
    [
        ("multiple_choice_v1", ["A", "C"]),
        ("numeric_answer_v1", "5"),
        ("ordering_v1", ["A", "B", "C"]),
    ],
)
def test_new_registry_scorers_create_evidence_only_through_completed_summary(
    scorer_name, answer
):
    template = _template(scorer_name)
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    completed = service.submit(
        session=started["session"],
        answer=answer,
        submitted_template_id=template["id"],
    )
    state = _learner_state()
    original_state = copy.deepcopy(state)
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")

    update = DiagnosticStateIntegrationService(
        knowledge_data=knowledge, recommendation_fn=lambda *_args: None
    ).apply(learner_state=state, diagnostic_summary=completed["summary"])

    assert started["summary"] is None
    assert completed["summary"]["evidence_eligible"] is True
    assert update["updates"][0]["selected_signal"] == 1.0
    assert update["updates"][0]["selection_reason"] == "last_unassisted_observation"
    assert state == original_state


def test_new_scorer_hint_assisted_correct_preserves_unassisted_zero_signal():
    template = _template("multiple_choice_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    wrong = service.submit(
        session=started["session"],
        answer=["A"],
        submitted_template_id=template["id"],
    )
    retry = service.choose_hint_retry(
        session=wrong["session"], template_id=template["id"]
    )
    completed = service.submit(
        session=retry["session"],
        answer=["A", "C"],
        submitted_template_id=template["id"],
    )
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    update = DiagnosticStateIntegrationService(
        knowledge_data=knowledge, recommendation_fn=lambda *_args: None
    ).apply(
        learner_state=_learner_state(),
        diagnostic_summary=completed["summary"],
    )

    assert completed["summary"]["concept_observations"][CONCEPT_ID] == [0.0, 1.0]
    assert completed["summary"]["concept_observation_assistance"][CONCEPT_ID] == [
        False,
        True,
    ]
    assert update["updates"][0]["selected_signal"] == 0.0


def test_new_scorer_reveal_creates_no_observation():
    template = _template("numeric_answer_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    revealed = service.request_reveal(
        session=started["session"], template_id=template["id"]
    )
    completed = service.acknowledge_reveal(
        session=revealed["session"], template_id=template["id"]
    )

    assert service.current_reveal(session=revealed["session"])[
        "correct_choice_text"
    ] == "5"
    assert completed["summary"]["concept_observations"] == {}
    assert completed["summary"]["no_observation_reason"] == "all_revealed"


def test_new_scorer_history_tampering_is_rejected_before_retry():
    template = _template("multiple_choice_v1")
    service = _service(template)
    started = service.start(template_ids=[template["id"]])
    wrong = service.submit(
        session=started["session"],
        answer=["A"],
        submitted_template_id=template["id"],
    )
    forged = copy.deepcopy(wrong["session"])
    forged["history"][0]["score"] = 1.0
    original = copy.deepcopy(wrong["session"])

    with pytest.raises(VerificationDiagnosticError, match="scoring evidence"):
        service.choose_hint_retry(
            session=forged,
            template_id=template["id"],
        )

    assert wrong["session"] == original


def test_unknown_scorer_and_mismatched_question_type_fail_closed():
    unknown = _template("multiple_choice_v1")
    unknown["deterministic_scorer"] = "unknown_v1"
    with pytest.raises(DiagnosticTemplateError, match="unsupported"):
        _validate(unknown)
    with pytest.raises(VerificationDiagnosticError, match="Unsupported"):
        VerificationDiagnosticService(templates=[unknown])

    mismatched = _template("multiple_choice_v1")
    mismatched["question_type"] = "ordering"
    with pytest.raises(DiagnosticTemplateError, match="mismatched"):
        _validate(mismatched)


def test_production_template_bank_preserves_legacy_and_promotes_approved_scorers():
    data = json.loads(
        (ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8")
    )

    templates = data["templates"]
    assert [item["id"] for item in templates[:3]] == [
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ]
    assert {
        (item["question_type"], item["deterministic_scorer"])
        for item in templates[:3]
    } == {("single_choice", "single_choice_v1")}
    assert [
        (
            item["id"],
            item["question_type"],
            item["deterministic_scorer"],
        )
        for item in templates[3:]
    ] == [
        (
            "verify_search_problem_components_v1",
            "multiple_choice",
            "multiple_choice_v1",
        ),
        (
            "verify_successor_operator_v1",
            "single_choice",
            "single_choice_v1",
        ),
            (
                "verify_frontier_explored_membership_v1",
                "multiple_choice",
                "multiple_choice_v1",
            ),
            (
                "verify_graph_search_repeated_state_handling_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_dfs_frontier_choice_v1",
                "single_choice",
                "single_choice_v1",
            ),
        (
            "verify_iddfs_depth_limit_schedule_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_informed_search_g_h_roles_v1",
            "multiple_choice",
            "multiple_choice_v1",
        ),
        (
            "verify_greedy_min_h_choice_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_astar_min_f_choice_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_admissibility_no_overestimate_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_path_cost_accumulation_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_search_node_state_distinction_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_dfs_infinite_branch_risk_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_search_algorithm_properties_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_greedy_suboptimality_v1",
            "single_choice",
            "single_choice_v1",
        ),
        (
            "verify_astar_f_value_v1",
            "single_choice",
            "single_choice_v1",
        ),
            (
                "verify_consistency_edge_check_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_local_search_final_state_focus_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_hill_climbing_stop_at_local_best_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_simulated_annealing_worse_successor_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_evolutionary_search_parent_cycle_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_minimax_max_min_value_choice_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_alpha_beta_prune_when_bounds_cross_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_mcts_four_stage_order_v1",
                "single_choice",
                "single_choice_v1",
            ),
            (
                "verify_ucb_upper_bound_selection_v1",
                "single_choice",
                "single_choice_v1",
            ),
        ]
