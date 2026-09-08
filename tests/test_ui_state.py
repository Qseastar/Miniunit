from copy import deepcopy

import pytest

from introai_tutor.ui_state import (
    DIAGNOSTIC_VARIANT_ROUND_KEY,
    DIAGNOSTIC_UNRESOLVED_MESSAGE,
    DIAGNOSTIC_FLASH_KEY,
    advance_diagnostic_variant_round,
    bind_qa_diagnostic_plan,
    build_diagnostic_flash,
    clear_diagnostic_state,
    consume_diagnostic_flash,
    diagnostic_attempt_status,
    diagnostic_answer_widget_key,
    diagnostic_question_widget_key,
    validate_current_diagnostic_question,
    diagnostic_variant_round,
    elapsed_seconds,
    HANDOFF_SOURCE_TOPICS_KEY,
    DIAGNOSTIC_ORIGIN_KEY,
    PENDING_DIAGNOSTIC_PLAN_KEY,
    QA_DIAGNOSTIC_PLAN_KEY,
    resolve_qa_diagnostic_plan,
    store_qa_result_with_diagnostic_plan,
    has_active_diagnostic,
    QA_INPUT_SESSION_TOKEN_KEY,
    QA_QUESTION_WIDGET_PREFIX,
    qa_question_widget_key,
    set_qa_question_value,
)


def _question(step_number=1, attempt_number=1):
    return {
        "id": f"question_{step_number}",
        "prompt_id": f"question_{step_number}",
        "prompt": f"prompt {step_number}",
        "step_number": step_number,
        "attempt_number": attempt_number,
        "total_steps": 3,
    }


def _diagnostic(*, passed, step_number=None, status="in_progress"):
    return {
        "status": status,
        "question": _question(step_number) if step_number is not None else None,
        "evaluation": {
            "score": 1.0 if passed else 0.25,
            "passed": passed,
            "feedback": ["safe feedback"],
        },
    }


def test_widget_keys_change_for_retry_and_next_step():
    assert diagnostic_answer_widget_key(step_index=0, attempt_number=1) == (
        "introai_diagnostic_answer_0_1"
    )


def test_qa_widget_key_is_session_local_stable_and_prefill_is_explicit():
    first: dict = {}
    second: dict = {}
    first_token = "a" * 32
    second_token = "b" * 32

    first_key = qa_question_widget_key(
        first, token_factory=lambda: first_token
    )
    assert first_key == QA_QUESTION_WIDGET_PREFIX + first_token
    assert first[QA_INPUT_SESSION_TOKEN_KEY] == first_token
    assert qa_question_widget_key(first, token_factory=lambda: second_token) == first_key

    prefill_key = set_qa_question_value(first, "请结合课件讲解搜索问题建模。")
    assert prefill_key == first_key
    assert first[prefill_key] == "请结合课件讲解搜索问题建模。"
    assert qa_question_widget_key(second, token_factory=lambda: second_token) == (
        QA_QUESTION_WIDGET_PREFIX + second_token
    )


def test_qa_widget_key_rejects_an_invalid_injected_token():
    with pytest.raises(ValueError, match="token"):
        qa_question_widget_key({}, token_factory=lambda: "not-a-uuid")
    with pytest.raises(ValueError, match="prefill"):
        set_qa_question_value({}, "  ")


def test_current_question_validation_rejects_stale_result_question_after_step_advance():
    session = {
        "status": "in_progress",
        "step_index": 2,
        "attempt_in_step": 0,
        "selected_prompt_ids": ["question_1", "question_2", "ucs_variant"],
    }
    current = {
        "id": "dq_ucs_when_costs_differ_001",
        "prompt_id": "ucs_variant",
        "prompt": "UCS 当前题面",
        "step_number": 3,
        "attempt_number": 1,
    }
    stale = {
        "id": "dq_bfs_order_001",
        "prompt_id": "question_2",
        "prompt": "路径甲只走2步",
        "step_number": 2,
        "attempt_number": 1,
    }

    assert validate_current_diagnostic_question(session=session, question=current) == current
    assert diagnostic_question_widget_key(current) != diagnostic_question_widget_key(stale)
    with pytest.raises(ValueError, match="step_number"):
        validate_current_diagnostic_question(session=session, question=stale)
    assert diagnostic_question_widget_key(_question(1, 2)) != diagnostic_question_widget_key(
        _question(2, 1)
    )


def test_attempt_status_uses_real_attempts_used_not_next_attempt_number():
    initial = diagnostic_attempt_status(
        session={"attempt_in_step": 0}, question={"max_attempts": 2}
    )
    retry = diagnostic_attempt_status(
        session={"attempt_in_step": 1}, question={"max_attempts": 2}
    )

    assert initial["remaining_attempts"] == 2
    assert initial["message"] == "本题最多作答 2 次"
    assert retry["remaining_attempts"] == 1
    assert retry["message"] == "还可作答 1 次。本题最后一次作答"
    assert DIAGNOSTIC_UNRESOLVED_MESSAGE == "本题暂未解决，已展示参考答案并进入下一步。"


def test_answerable_question_cannot_report_zero_remaining_attempts():
    with pytest.raises(ValueError, match="exhausted"):
        diagnostic_attempt_status(
            session={"attempt_in_step": 2}, question={"max_attempts": 2}
        )


def test_widget_key_rejects_invalid_positions():
    with pytest.raises(ValueError):
        diagnostic_answer_widget_key(step_index=-1, attempt_number=1)
    with pytest.raises(ValueError):
        diagnostic_answer_widget_key(step_index=0, attempt_number=0)
    with pytest.raises(ValueError):
        diagnostic_question_widget_key({"step_number": 0, "attempt_number": 1})


def test_elapsed_seconds_is_non_negative_and_validated():
    assert elapsed_seconds(10.0, 10.25) == 0.25
    assert elapsed_seconds(10.0, 9.0) == 0.0
    with pytest.raises(ValueError):
        elapsed_seconds("start", 1.0)


def test_diagnostic_variant_round_defaults_to_zero_and_only_advances_explicitly():
    state = {}

    assert diagnostic_variant_round(state) == 0
    assert diagnostic_variant_round(state) == 0
    assert advance_diagnostic_variant_round(state) == 1
    assert diagnostic_variant_round(state) == 1


def test_handoff_state_is_active_only_for_unfinished_diagnostic_and_is_cleared():
    state = {
        "introai_last_qa_result": {"understanding": {"topic_ids": ["uniform_cost_search"]}},
        QA_DIAGNOSTIC_PLAN_KEY: {"template_ids": ["verify_ucs_min_g_choice_v1"]},
        PENDING_DIAGNOSTIC_PLAN_KEY: {"template_ids": ["verify_ucs_min_g_choice_v1"]},
        DIAGNOSTIC_ORIGIN_KEY: "qa_handoff",
        HANDOFF_SOURCE_TOPICS_KEY: ["uniform_cost_search"],
        "introai_scroll_request": {"target": "diagnostic_handoff", "event_id": "qa-explicit-diagnostic-1"},
        "introai_scroll_consumed_events": ["qa-explicit-diagnostic-1"],
        "introai_dual_track_result": {"phase": "verification"},
        "introai_verification_quick": "choice",
    }

    assert has_active_diagnostic(state) is True
    clear_diagnostic_state(state)

    assert state["introai_last_qa_result"]["understanding"]["topic_ids"] == [
        "uniform_cost_search"
    ]
    assert QA_DIAGNOSTIC_PLAN_KEY not in state
    assert PENDING_DIAGNOSTIC_PLAN_KEY not in state
    assert DIAGNOSTIC_ORIGIN_KEY not in state
    assert HANDOFF_SOURCE_TOPICS_KEY not in state
    assert "introai_scroll_request" not in state
    assert "introai_scroll_consumed_events" not in state
    assert "introai_verification_quick" not in state
    assert has_active_diagnostic(state) is False


def test_current_qa_result_owns_plan_and_does_not_mutate_inputs():
    qa_result = {"question": "UCS 如何选择节点？", "understanding": {}}
    plan = {
        "available": True,
        "planning_topic_ids": ["uniform_cost_search"],
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    original_result = deepcopy(qa_result)
    original_plan = deepcopy(plan)
    state = {}

    bound = store_qa_result_with_diagnostic_plan(
        state, qa_result=qa_result, diagnostic_plan=plan
    )
    resolved = resolve_qa_diagnostic_plan(
        qa_result=state["introai_last_qa_result"],
        cached_plan=state[QA_DIAGNOSTIC_PLAN_KEY],
    )

    assert qa_result == original_result
    assert plan == original_plan
    assert bound is state["introai_last_qa_result"]
    assert resolved is bound["diagnostic_plan"]
    assert resolved == plan
    assert state[QA_DIAGNOSTIC_PLAN_KEY] == plan
    assert state[QA_DIAGNOSTIC_PLAN_KEY] is not resolved


def test_current_result_plan_wins_over_a_stale_legacy_cache():
    current_plan = {
        "available": True,
        "planning_topic_ids": ["uniform_cost_search"],
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    stale_plan = {
        "available": False,
        "planning_topic_ids": ["a_star_search"],
        "template_ids": [],
    }
    bound = bind_qa_diagnostic_plan(
        qa_result={"question": "UCS"}, diagnostic_plan=current_plan
    )

    assert resolve_qa_diagnostic_plan(
        qa_result=bound, cached_plan=stale_plan
    ) is bound["diagnostic_plan"]


def test_new_qa_result_replaces_unavailable_plan_with_ucs_plan_and_reverse():
    a_star_plan = {
        "available": False,
        "planning_topic_ids": [
            "a_star_search",
            "admissibility_and_consistency",
        ],
        "template_ids": [],
    }
    ucs_plan = {
        "available": True,
        "planning_topic_ids": ["uniform_cost_search"],
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    state = {}

    store_qa_result_with_diagnostic_plan(
        state, qa_result={"question": "A*"}, diagnostic_plan=a_star_plan
    )
    store_qa_result_with_diagnostic_plan(
        state, qa_result={"question": "UCS"}, diagnostic_plan=ucs_plan
    )
    assert resolve_qa_diagnostic_plan(
        qa_result=state["introai_last_qa_result"],
        cached_plan=state[QA_DIAGNOSTIC_PLAN_KEY],
    ) == ucs_plan

    store_qa_result_with_diagnostic_plan(
        state, qa_result={"question": "A* again"}, diagnostic_plan=a_star_plan
    )
    assert resolve_qa_diagnostic_plan(
        qa_result=state["introai_last_qa_result"],
        cached_plan=state[QA_DIAGNOSTIC_PLAN_KEY],
    ) == a_star_plan


def test_legacy_qa_result_can_use_cached_plan_but_clear_removes_the_binding():
    cached_plan = {
        "available": True,
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    state = {
        "introai_last_qa_result": {"question": "legacy UCS"},
        QA_DIAGNOSTIC_PLAN_KEY: cached_plan,
    }

    assert resolve_qa_diagnostic_plan(
        qa_result=state["introai_last_qa_result"],
        cached_plan=state[QA_DIAGNOSTIC_PLAN_KEY],
    ) == cached_plan

    store_qa_result_with_diagnostic_plan(
        state,
        qa_result=state["introai_last_qa_result"],
        diagnostic_plan=cached_plan,
    )
    clear_diagnostic_state(state)

    assert state["introai_last_qa_result"] == {"question": "legacy UCS"}
    assert QA_DIAGNOSTIC_PLAN_KEY not in state
    assert resolve_qa_diagnostic_plan(
        qa_result=state["introai_last_qa_result"],
        cached_plan=state.get(QA_DIAGNOSTIC_PLAN_KEY),
    ) is None


@pytest.mark.parametrize("value", [-1, True, 1.5, "1"])
def test_invalid_diagnostic_variant_round_is_rejected(value):
    with pytest.raises(ValueError):
        diagnostic_variant_round({DIAGNOSTIC_VARIANT_ROUND_KEY: value})


def test_passed_answer_creates_success_flash_and_next_step_message_data():
    flash = build_diagnostic_flash(
        previous_question=_question(1),
        diagnostic=_diagnostic(passed=True, step_number=2),
    )

    assert flash == {
        "type": "success",
        "score": 1.0,
        "coverage_score": 1.0,
        "feedback": ["safe feedback"],
        "matched_labels": [],
        "missing_labels": [],
        "semantic_supported_labels": [],
        "needs_clarification": False,
        "clarifying_question": None,
        "misconception_feedback": [],
        "developer_trace": {
            "coverage_score": 1.0,
            "mastery_score": 1.0,
            "assessment_source": "deterministic",
            "semantic_status": "not_used",
            "semantic_confidence": None,
            "semantic_judgments": [],
        },
        "previous_step": 1,
        "next_step": 2,
        "moved_to_next_step": True,
        "unresolved": False,
        "assistance_level": "none",
    }


def test_failed_retry_flash_is_warning_and_contains_no_hidden_assessment_fields():
    flash = build_diagnostic_flash(
        previous_question=_question(1, 1),
        diagnostic=_diagnostic(passed=False, step_number=1),
    )

    assert flash["type"] == "warning"
    assert flash["moved_to_next_step"] is False
    assert flash["unresolved"] is False
    assert "rubric" not in flash
    assert "terms" not in flash
    assert "patterns" not in flash


def test_flash_keeps_semantic_metadata_only_in_validated_developer_trace():
    diagnostic = _diagnostic(passed=False, step_number=1)
    diagnostic["evaluation"].update(
        {
            "coverage_score": 0.5,
            "score": 0.0,
            "semantic_used": True,
            "semantic_status": "advisory",
            "semantic_confidence": 0.9,
            "semantic_judgments": [
                {"criterion_id": "cumulative_path_cost", "status": "entailed"}
            ],
        }
    )

    flash = build_diagnostic_flash(
        previous_question=_question(1), diagnostic=diagnostic
    )

    assert flash["coverage_score"] == 0.5
    assert flash["developer_trace"] == {
        "coverage_score": 0.5,
        "mastery_score": 0.0,
        "assessment_source": "deterministic",
        "semantic_status": "advisory",
        "semantic_confidence": 0.9,
        "semantic_judgments": [
            {"criterion_id": "cumulative_path_cost", "status": "entailed"}
        ],
    }


def test_flash_keeps_advisory_labels_and_clarifying_question_student_safe():
    diagnostic = _diagnostic(passed=False, step_number=1)
    diagnostic["evaluation"].update(
        {
            "semantic_status": "advisory",
            "semantic_confidence": 1.0,
            "semantic_supported_labels": ["BFS 的逐层扩展顺序"],
            "needs_clarification": True,
            "clarifying_question": "请进一步说明：队列的处理顺序如何使 BFS 先完成当前层，再进入下一层？",
        }
    )

    flash = build_diagnostic_flash(
        previous_question=_question(1), diagnostic=diagnostic
    )

    assert flash["semantic_supported_labels"] == ["BFS 的逐层扩展顺序"]
    assert flash["needs_clarification"] is True
    assert flash["clarifying_question"].startswith("请进一步说明")
    assert "terms" not in flash
    assert "patterns" not in flash


def test_unresolved_attempt_advances_with_warning_flash():
    flash = build_diagnostic_flash(
        previous_question=_question(1, 2),
        diagnostic=_diagnostic(passed=False, step_number=2),
    )

    assert flash["type"] == "warning"
    assert flash["moved_to_next_step"] is True
    assert flash["unresolved"] is True
    assert flash["next_step"] == 2


def test_flash_keeps_only_public_teaching_feedback_fields():
    flash = build_diagnostic_flash(
        previous_question=_question(1, 2),
        diagnostic=_diagnostic(passed=False, step_number=2),
        teaching_feedback={
            "mode": "reveal",
            "remaining_attempts": 0,
            "messages": ["已展示参考答案，本题暂未解决并进入下一步。"],
            "model_answer": "人工审核参考答案",
            "explanation": "人工审核解析",
            "rubric": "must not enter flash",
            "terms": ["must not enter flash"],
        },
    )

    assert flash["teaching_feedback"] == {
        "mode": "reveal",
        "remaining_attempts": 0,
        "messages": ["已展示参考答案，本题暂未解决并进入下一步。"],
        "model_answer": "人工审核参考答案",
        "explanation": "人工审核解析",
    }
    assert "rubric" not in flash["teaching_feedback"]
    assert "terms" not in flash["teaching_feedback"]


def test_assisted_pass_creates_only_a_safe_practice_flash_marker():
    diagnostic = _diagnostic(passed=True, step_number=2)
    diagnostic["evaluation"]["assisted"] = True

    flash = build_diagnostic_flash(
        previous_question=_question(1, 2), diagnostic=diagnostic
    )

    assert flash["assisted_practice"] is True
    assert "full_answer_revealed" not in flash
    assert "rubric" not in flash


def test_clarification_assisted_pass_uses_safe_provenance_without_model_content():
    diagnostic = _diagnostic(passed=True, step_number=2)
    diagnostic["evaluation"].update(
        {
            "assisted": True,
            "assistance_level": "clarification",
            "assistance_source": "semantic_advisory",
        }
    )

    flash = build_diagnostic_flash(
        previous_question=_question(1, 2), diagnostic=diagnostic
    )

    assert flash["assisted_practice"] is True
    assert flash["assistance_level"] == "clarification"
    assert "semantic_advisory" not in flash


def test_flash_is_consumed_once_and_diagnostic_reset_preserves_qa_state():
    state = {
        DIAGNOSTIC_FLASH_KEY: {"type": "success"},
        "introai_diagnostic_result": {},
        "introai_diagnostic_session": {},
        "introai_diagnostic_answer_0_1": "old answer",
        "introai_dual_track_result": {},
        "introai_dual_track_session": {},
        "introai_diagnostic_mode": "quick",
        "introai_formative_feedback_error": True,
        "introai_formative_answer_1_1": "old formative answer",
        "introai_verification_answer_1_1": "old verification answer",
        "introai_last_recommendation": {"concept_id": "uniform_cost_search"},
        DIAGNOSTIC_VARIANT_ROUND_KEY: 1,
        "introai_qa_question": "keep this question",
        "introai_last_qa_result": {"status": "answered"},
    }

    assert consume_diagnostic_flash(state) == {"type": "success"}
    assert consume_diagnostic_flash(state) is None
    clear_diagnostic_state(state)

    assert "introai_diagnostic_result" not in state
    assert "introai_diagnostic_session" not in state
    assert "introai_diagnostic_answer_0_1" not in state
    assert "introai_dual_track_result" not in state
    assert "introai_dual_track_session" not in state
    assert "introai_diagnostic_mode" not in state
    assert "introai_formative_feedback_error" not in state
    assert "introai_formative_answer_1_1" not in state
    assert "introai_verification_answer_1_1" not in state
    assert "introai_last_recommendation" not in state
    assert state[DIAGNOSTIC_VARIANT_ROUND_KEY] == 1
    assert state["introai_qa_question"] == "keep this question"
    assert state["introai_last_qa_result"] == {"status": "answered"}


def test_non_destructive_diagnostic_exit_preserves_recommendation_and_learning_outcome():
    state = {
        "introai_dual_track_result": {"phase": "completed"},
        "introai_dual_track_session": {"phase": "completed"},
        "introai_verification_answer_fixture": "A",
        "introai_last_recommendation": {"concept_id": "uniform_cost_search"},
        "introai_completed_verification_summaries": [{"evidence_eligible": True}],
        "introai_learner_state": {"mastery": {"uniform_cost_search": 0.35}},
    }

    clear_diagnostic_state(state, preserve_learning_outcome=True)

    assert "introai_dual_track_result" not in state
    assert "introai_dual_track_session" not in state
    assert "introai_verification_answer_fixture" not in state
    assert state["introai_last_recommendation"] == {"concept_id": "uniform_cost_search"}
    assert state["introai_completed_verification_summaries"] == [{"evidence_eligible": True}]
    assert state["introai_learner_state"]["mastery"] == {"uniform_cost_search": 0.35}
