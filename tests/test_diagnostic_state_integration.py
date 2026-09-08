import copy
import json
from pathlib import Path

import pytest

from introai_tutor.diagnostic_state_integration import (
    DiagnosticStateIntegrationError,
    DiagnosticStateIntegrationService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.learner import load_learner_state, validate_learner_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
LEARNER_STATE_FILE = PROJECT_ROOT / "data" / "demo_student_state.json"


def _knowledge():
    return load_knowledge_points(KNOWLEDGE_FILE)


def _summary(**overrides):
    value = {
        "purpose": "mastery_verification",
        "evidence_eligible": True,
        "track_id": "bfs_equal_cost_ucs",
        "total_steps": 3,
        "passed_steps": 3,
        "unresolved_steps": 0,
        "concept_observations": {
            "breadth_first_search": [1.0],
            "completeness_optimality_complexity": [0.2, 1.0],
            "uniform_cost_search": [1.0],
        },
        "misconception_ids": ["bfs_always_cost_optimal"],
        "step_results": [
            {
                "question_id": "dq_bfs_expansion_001",
                "status": "passed",
                "best_score": 1.0,
                "attempts": 1,
            },
            {
                "question_id": "dq_bfs_order_001",
                "status": "passed",
                "best_score": 1.0,
                "attempts": 2,
            },
            {
                "question_id": "dq_ucs_when_costs_differ_001",
                "status": "passed",
                "best_score": 1.0,
                "attempts": 1,
            },
        ],
    }
    value.update(overrides)
    return value


def _state(**overrides):
    value = {
        "student_id": "student-1",
        "course_id": "intro_ai",
        "mastery": {
            "breadth_first_search": 0.45,
            "completeness_optimality_complexity": 0.3,
            "uniform_cost_search": 0.2,
        },
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }
    value.update(overrides)
    return value


def _service(recommendation_fn=None, **kwargs):
    return DiagnosticStateIntegrationService(
        knowledge_data=_knowledge(),
        recommendation_fn=recommendation_fn,
        **kwargs,
    )


@pytest.mark.parametrize(
    "overrides,remove_field,match",
    [
        ({"purpose": "formative", "evidence_eligible": False}, None, "purpose"),
        ({"evidence_eligible": False}, None, "evidence_eligible"),
        ({}, "purpose", "purpose"),
        ({}, "evidence_eligible", "evidence_eligible"),
        ({"purpose": "unknown", "evidence_eligible": True}, None, "purpose"),
    ],
)
def test_apply_requires_explicit_mastery_verification_evidence_gate(
    overrides, remove_field, match
):
    calls = []
    state = _state()
    original = copy.deepcopy(state)
    summary = _summary(**overrides)
    if remove_field is not None:
        summary.pop(remove_field)

    with pytest.raises(DiagnosticStateIntegrationError, match=match):
        _service(lambda *_args: calls.append("called")).apply(
            learner_state=state, diagnostic_summary=summary
        )

    assert state == original
    assert calls == []


def test_apply_updates_last_observations_in_summary_order_and_returns_trace():
    calls = []

    def recommendation(knowledge_data, learner_state):
        calls.append((knowledge_data, copy.deepcopy(learner_state)))
        return {"concept_id": "uniform_cost_search", "reason": "injected"}

    state = _state()
    result = _service(recommendation).apply(
        learner_state=state, diagnostic_summary=_summary()
    )

    assert [item["concept_id"] for item in result["updates"]] == [
        "breadth_first_search",
        "completeness_optimality_complexity",
        "uniform_cost_search",
    ]
    assert result["updates"][0] == {
        "concept_id": "breadth_first_search",
        "old_mastery": 0.45,
        "observation_scores": [1.0],
        "observation_assistance": [False],
        "observation_assistance_levels": ["none"],
        "observation_assistance_sources": [None],
        "selected_signal": 1.0,
        "selection_reason": "last_unassisted_observation",
        "new_mastery": pytest.approx(0.6425),
    }
    assert result["updates"][1]["new_mastery"] == pytest.approx(0.545)
    assert result["updates"][2]["new_mastery"] == pytest.approx(0.48)
    assert result["added_misconception_ids"] == ["bfs_always_cost_optimal"]
    assert result["recommendation"] == {"concept_id": "uniform_cost_search", "reason": "injected"}
    assert len(calls) == 1
    assert calls[0][1]["mastery"]["breadth_first_search"] == pytest.approx(0.6425)


def test_last_observation_is_used_not_average_or_best_score():
    state = _state(mastery={"breadth_first_search": 0.5})
    summary = _summary(
        concept_observations={"breadth_first_search": [0.0, 1.0, 0.2]},
        misconception_ids=[],
    )
    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state, diagnostic_summary=summary
    )

    assert result["updates"][0]["selected_signal"] == pytest.approx(0.2)
    assert result["updates"][0]["new_mastery"] == pytest.approx(0.395)


def test_last_unassisted_observation_is_selected_when_later_raw_score_is_assisted():
    state = _state(mastery={"breadth_first_search": 0.5})
    summary = _summary(
        concept_observations={"breadth_first_search": [0.0, 1.0]},
        concept_observation_assistance={"breadth_first_search": [False, True]},
        misconception_ids=[],
    )

    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state, diagnostic_summary=summary
    )

    update = result["updates"][0]
    assert update["observation_scores"] == [0.0, 1.0]
    assert update["observation_assistance"] == [False, True]
    assert update["observation_assistance_levels"] == ["none", "reveal"]
    assert update["observation_assistance_sources"] == [None, "model_answer"]
    assert update["selected_signal"] == 0.0
    assert update["selection_reason"] == "last_unassisted_observation"
    assert update["new_mastery"] == pytest.approx(0.325)


def test_only_assisted_observations_use_conservative_no_update_fallback():
    calls = []

    def recommendation(_knowledge, learner_state):
        calls.append(copy.deepcopy(learner_state))
        return {"concept_id": None}

    state = _state(mastery={"breadth_first_search": 0.5})
    original = copy.deepcopy(state)
    summary = _summary(
        concept_observations={"breadth_first_search": [1.0]},
        concept_observation_assistance={"breadth_first_search": [True]},
        misconception_ids=[],
    )

    result = _service(recommendation).apply(
        learner_state=state, diagnostic_summary=summary
    )

    update = result["updates"][0]
    assert update["selected_signal"] is None
    assert update["selection_reason"] == "no_unassisted_observation_no_mastery_update"
    assert update["new_mastery"] == 0.5
    assert calls[0]["mastery"]["breadth_first_search"] == 0.5
    assert state == original


@pytest.mark.parametrize(
    "observations,levels,sources,expected_signal,expected_mastery",
    [
        ([0.2, 1.0], ["none", "clarification"], [None, "semantic_advisory"], 0.2, 0.07),
        ([0.5, 1.0], ["none", "scaffold"], [None, "deterministic_feedback"], 0.5, 0.175),
        ([1.0], ["none"], [None], 1.0, 0.35),
        ([0.2, 0.5, 1.0], ["none", "none", "clarification"], [None, None, "semantic_advisory"], 0.5, 0.175),
    ],
)
def test_last_unassisted_raw_score_remains_mastery_signal_after_assisted_pass(
    observations, levels, sources, expected_signal, expected_mastery
):
    """Passing after help never replaces the last independent raw observation."""
    state = _state(mastery={"breadth_first_search": 0.0})
    summary = _summary(
        concept_observations={"breadth_first_search": observations},
        concept_observation_assistance={
            "breadth_first_search": [level != "none" for level in levels]
        },
        concept_observation_assistance_levels={"breadth_first_search": levels},
        concept_observation_assistance_sources={"breadth_first_search": sources},
        misconception_ids=[],
    )

    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state, diagnostic_summary=summary
    )

    update = result["updates"][0]
    assert update["observation_scores"] == observations
    assert update["observation_assistance_levels"] == levels
    assert update["selected_signal"] == pytest.approx(expected_signal)
    assert update["selection_reason"] == "last_unassisted_observation"
    assert update["new_mastery"] == pytest.approx(expected_mastery)


def test_legacy_assisted_boolean_keeps_unassisted_partial_signal():
    state = _state(mastery={"breadth_first_search": 0.0})
    summary = _summary(
        concept_observations={"breadth_first_search": [0.2, 1.0]},
        concept_observation_assistance={"breadth_first_search": [False, True]},
        misconception_ids=[],
    )

    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state, diagnostic_summary=summary
    )

    update = result["updates"][0]
    assert update["observation_assistance_levels"] == ["none", "reveal"]
    assert update["selected_signal"] == pytest.approx(0.2)
    assert update["new_mastery"] == pytest.approx(0.07)


def test_missing_mastery_defaults_to_zero_without_filling_other_concepts():
    state = _state(mastery={})
    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state,
        diagnostic_summary=_summary(
            concept_observations={"uniform_cost_search": [1.0]},
            misconception_ids=[],
            total_steps=1,
            passed_steps=1,
            unresolved_steps=0,
            step_results=[_summary()["step_results"][2]],
        ),
    )

    assert result["updates"][0]["old_mastery"] == 0.0
    assert result["learner_state"]["mastery"] == {"uniform_cost_search": pytest.approx(0.35)}


def test_mastery_can_decrease_and_other_mastery_is_preserved():
    state = _state()
    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state,
        diagnostic_summary=_summary(
            concept_observations={"breadth_first_search": [0.0]},
            misconception_ids=[],
        ),
    )

    assert result["learner_state"]["mastery"]["breadth_first_search"] == pytest.approx(0.2925)
    assert result["learner_state"]["mastery"]["uniform_cost_search"] == 0.2
    assert result["learner_state"]["mastery"]["completeness_optimality_complexity"] == 0.3


def test_missing_misconceptions_field_is_normalized_only_on_copy():
    state = _state()
    del state["misconceptions"]
    original = copy.deepcopy(state)
    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state,
        diagnostic_summary=_summary(misconception_ids=[]),
    )

    assert "misconceptions" not in state
    assert result["learner_state"]["misconceptions"] == []
    assert state == original


def test_misconceptions_are_appended_once_and_existing_records_remain():
    state = _state(
        misconceptions=[
            {"concept_id": "breadth_first_search", "description": "legacy record"},
            {"misconception_id": "bfs_always_cost_optimal", "description": "old id"},
        ]
    )
    summary = _summary(
        misconception_ids=[
            "bfs_always_cost_optimal",
            "ucs_uses_depth_or_step_count",
            "bfs_always_cost_optimal",
        ]
    )
    result = _service(lambda _knowledge, _state: None).apply(
        learner_state=state, diagnostic_summary=summary
    )

    assert result["added_misconception_ids"] == ["ucs_uses_depth_or_step_count"]
    assert result["learner_state"]["misconceptions"][:2] == state["misconceptions"]
    assert result["learner_state"]["misconceptions"][-1]["misconception_id"] == (
        "ucs_uses_depth_or_step_count"
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update({"track_id": ""}),
        lambda value: value.update({"total_steps": True}),
        lambda value: value.update({"passed_steps": 2, "unresolved_steps": 0}),
        lambda value: value.update({"concept_observations": {}}),
        lambda value: value["concept_observations"].update({"unknown": [1.0]}),
        lambda value: value["concept_observations"].update({"breadth_first_search": []}),
        lambda value: value["concept_observations"].update({"breadth_first_search": [True]}),
        lambda value: value["concept_observations"].update({"breadth_first_search": [1.1]}),
        lambda value: value.update({"misconception_ids": "bad"}),
        lambda value: value.update({"misconception_ids": [""]}),
        lambda value: value.update({"step_results": []}),
        lambda value: value["step_results"][0].update({"status": "in_progress"}),
        lambda value: value["step_results"][0].update({"attempts": True}),
    ],
)
def test_invalid_completed_summary_is_rejected_without_partial_update(mutator):
    state = _state()
    original_state = copy.deepcopy(state)
    summary = _summary()
    mutator(summary)

    with pytest.raises(DiagnosticStateIntegrationError):
        _service(lambda _knowledge, _state: None).apply(
            learner_state=state, diagnostic_summary=summary
        )
    assert state == original_state


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update(
            {"concept_observation_assistance": {"breadth_first_search": [False]}}
        ),
        lambda value: value.update(
            {
                "concept_observation_assistance": {
                    "breadth_first_search": ["false"],
                    "completeness_optimality_complexity": [False, False],
                    "uniform_cost_search": [False],
                }
            }
        ),
        lambda value: value["step_results"][0].update(
            {"attempt_assistance": [False], "final_attempt_assisted": "false"}
        ),
        lambda value: value.update(
            {
                "concept_observation_assistance_levels": {
                    "breadth_first_search": ["clarification"],
                    "completeness_optimality_complexity": ["none", "none"],
                    "uniform_cost_search": ["none"],
                },
                "concept_observation_assistance_sources": {
                    "breadth_first_search": ["model_answer"],
                    "completeness_optimality_complexity": [None, None],
                    "uniform_cost_search": [None],
                },
            }
        ),
    ],
)
def test_invalid_assistance_metadata_is_rejected_without_partial_update(mutator):
    state = _state()
    original = copy.deepcopy(state)
    summary = _summary()
    mutator(summary)

    with pytest.raises(
        DiagnosticStateIntegrationError, match="Assistance|assistance|assisted"
    ):
        _service(lambda _knowledge, _state: None).apply(
            learner_state=state, diagnostic_summary=summary
        )
    assert state == original


def test_summary_and_knowledge_inputs_are_not_mutated():
    knowledge = _knowledge()
    summary = _summary(misconception_ids=["bfs_always_cost_optimal", "bfs_always_cost_optimal"])
    knowledge_before = copy.deepcopy(knowledge)
    summary_before = copy.deepcopy(summary)

    _service(lambda _knowledge, _state: None).apply(
        learner_state=_state(), diagnostic_summary=summary
    )

    assert knowledge == knowledge_before
    assert summary == summary_before


def test_recommendation_is_called_once_with_updated_state_and_raw_result_is_preserved():
    calls = []

    def recommendation(knowledge_data, learner_state):
        calls.append((knowledge_data, learner_state))
        return {"raw": ["result"], "concept_id": None}

    result = _service(recommendation).apply(
        learner_state=_state(), diagnostic_summary=_summary(misconception_ids=[])
    )

    assert len(calls) == 1
    assert calls[0][1]["mastery"]["breadth_first_search"] == pytest.approx(0.6425)
    assert result["recommendation"] == {"raw": ["result"], "concept_id": None}


def test_mutating_recommendation_cannot_change_returned_state_or_knowledge():
    knowledge = _knowledge()

    def mutating_recommendation(knowledge_data, learner_state):
        knowledge_data["knowledge_points"].clear()
        learner_state["mastery"]["breadth_first_search"] = 0.0
        return {"concept_id": "breadth_first_search"}

    result = DiagnosticStateIntegrationService(
        knowledge_data=knowledge,
        recommendation_fn=mutating_recommendation,
    ).apply(learner_state=_state(), diagnostic_summary=_summary(misconception_ids=[]))

    assert len(knowledge["knowledge_points"]) == 26
    assert result["learner_state"]["mastery"]["breadth_first_search"] == pytest.approx(0.6425)


def test_recommendation_exception_propagates_and_original_state_is_unchanged():
    state = _state()
    original = copy.deepcopy(state)

    def failing_recommendation(_knowledge, learner_state):
        learner_state["mastery"].clear()
        raise RuntimeError("recommendation failed")

    with pytest.raises(RuntimeError, match="recommendation failed"):
        _service(failing_recommendation).apply(
            learner_state=state, diagnostic_summary=_summary()
        )
    assert state == original


@pytest.mark.parametrize("weight", [-0.1, 1.1, True, float("nan"), float("inf"), "0.35"])
def test_invalid_observation_weight_is_rejected(weight):
    with pytest.raises(DiagnosticStateIntegrationError, match="observation_weight"):
        _service(observation_weight=weight)


def test_invalid_learner_mastery_bool_is_rejected():
    state = _state(mastery={"breadth_first_search": True})
    with pytest.raises(DiagnosticStateIntegrationError, match="learner state"):
        _service().apply(learner_state=state, diagnostic_summary=_summary())


def test_real_recommendation_runs_once_with_real_data():
    knowledge = _knowledge()
    state = load_learner_state(LEARNER_STATE_FILE, knowledge)
    original = copy.deepcopy(state)
    result = DiagnosticStateIntegrationService(knowledge_data=knowledge).apply(
        learner_state=state,
        diagnostic_summary=_summary(),
    )

    assert result["recommendation"]["concept_id"] in {
        point["id"] for point in knowledge["knowledge_points"]
    } | {None}
    assert state == original


def test_legacy_learner_state_without_misconceptions_still_validates(tmp_path):
    knowledge = _knowledge()
    legacy = _state()
    del legacy["misconceptions"]
    path = tmp_path / "legacy_state.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = load_learner_state(path, knowledge)
    validate_learner_state(loaded, knowledge)
    assert "misconceptions" not in loaded
