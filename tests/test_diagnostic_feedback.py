import copy
import math

import pytest

from introai_tutor.diagnostic_feedback import (
    DiagnosticFeedbackError,
    build_semantic_clarification,
    build_teaching_feedback,
    validate_teaching_support,
)


SUPPORT = {
    "model_answer": "人工审核的参考答案。",
    "explanation": "人工审核的知识解释。",
    "scaffold": "先说明关键条件，再说明选择依据。",
}


def _feedback(*, score=0.4, mastery=0.4, attempts_used=1, support=SUPPORT):
    return build_teaching_feedback(
        score=score,
        concept_ids=["breadth_first_search", "uniform_cost_search"],
        learner_state={
            "mastery": {
                "breadth_first_search": mastery,
                "uniform_cost_search": mastery,
            }
        },
        attempts_used=attempts_used,
        max_attempts=2,
        assessment_feedback=["还需要说明：安全缺失要点。"],
        teaching_support=support,
    )


def test_high_score_or_high_mastery_uses_hint_only():
    high_score = _feedback(score=0.6, mastery=0.0)
    high_mastery = _feedback(score=0.1, mastery=0.6)

    for result in (high_score, high_mastery):
        assert result["mode"] == "hint"
        assert result["remaining_attempts"] == 1
        assert result["messages"] == ["还需要说明：安全缺失要点。"]
        assert result["model_answer"] is None
        assert result["explanation"] is None


def test_middle_first_failure_uses_scaffold_without_model_answer():
    result = _feedback(score=0.4, mastery=0.4)

    assert result["mode"] == "scaffold"
    assert result["messages"] == [
        "还需要说明：安全缺失要点。",
        SUPPORT["scaffold"],
    ]
    assert result["model_answer"] is None
    assert result["explanation"] is None


def test_low_score_and_lowest_link_mastery_use_reveal_with_one_retry_left():
    result = build_teaching_feedback(
        score=0.2,
        concept_ids=["breadth_first_search", "uniform_cost_search"],
        learner_state={
            "mastery": {
                "breadth_first_search": 0.9,
                "uniform_cost_search": 0.2,
            }
        },
        attempts_used=1,
        max_attempts=2,
        assessment_feedback=["还需要说明：安全缺失要点。"],
        teaching_support=SUPPORT,
    )

    assert result["mode"] == "reveal"
    assert result["remaining_attempts"] == 1
    assert result["model_answer"] == SUPPORT["model_answer"]
    assert result["explanation"] == SUPPORT["explanation"]
    assert result["messages"][-1] == "请阅读参考答案后，用自己的话重新作答。"


def test_semantic_clarification_forces_unassisted_scaffold_before_final_attempt():
    question = build_semantic_clarification(
        missing_labels=["BFS 的逐层扩展顺序"],
        semantic_supported_labels=["BFS 的逐层扩展顺序"],
    )
    result = build_teaching_feedback(
        score=0.2,
        concept_ids=["breadth_first_search"],
        learner_state={"mastery": {"breadth_first_search": 0.0}},
        attempts_used=1,
        max_attempts=2,
        assessment_feedback=["还需要说明：BFS 的逐层扩展顺序。"],
        teaching_support=SUPPORT,
        needs_clarification=True,
        clarifying_question=question,
    )

    assert result["mode"] == "scaffold"
    assert result["model_answer"] is None
    assert result["explanation"] is None
    assert question.startswith("请进一步说明")


def test_final_failure_always_reveals_and_marks_step_unresolved():
    result = _feedback(score=1.0, mastery=1.0, attempts_used=2)

    assert result["mode"] == "reveal"
    assert result["remaining_attempts"] == 0
    assert result["messages"][-1] == "已展示参考答案，本题暂未解决并进入下一步。"


def test_legacy_question_without_teaching_support_still_returns_safe_feedback():
    result = _feedback(score=0.2, mastery=0.2, support=None)

    assert result["mode"] == "reveal"
    assert result["model_answer"] is None
    assert result["explanation"] is None


def test_feedback_does_not_modify_learner_state_or_support_data():
    learner_state = {"mastery": {"breadth_first_search": 0.2}}
    support = copy.deepcopy(SUPPORT)
    original_state = copy.deepcopy(learner_state)

    result = build_teaching_feedback(
        score=0.2,
        concept_ids=["breadth_first_search"],
        learner_state=learner_state,
        attempts_used=1,
        max_attempts=2,
        assessment_feedback=["安全反馈"],
        teaching_support=support,
    )
    result["messages"].append("caller mutation")

    assert learner_state == original_state
    assert support == SUPPORT


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"model_answer": "x", "explanation": "x"},
        {**SUPPORT, "unexpected": "x"},
        {**SUPPORT, "scaffold": "   "},
    ],
)
def test_teaching_support_schema_is_strict(value):
    with pytest.raises(DiagnosticFeedbackError, match="teaching_support"):
        validate_teaching_support(value)


@pytest.mark.parametrize("score", [True, -0.1, 1.1, math.nan, math.inf])
def test_policy_rejects_invalid_scores(score):
    with pytest.raises(DiagnosticFeedbackError, match="score"):
        _feedback(score=score)


@pytest.mark.parametrize("mastery", [True, -0.1, 1.1, math.nan, math.inf])
def test_policy_rejects_invalid_mastery_values(mastery):
    with pytest.raises(DiagnosticFeedbackError, match="mastery"):
        _feedback(mastery=mastery)
