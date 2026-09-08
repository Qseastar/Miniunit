"""Pure state helpers for Streamlit diagnostic interactions."""

from __future__ import annotations

from copy import deepcopy
import re
import uuid
from typing import Any


DIAGNOSTIC_FLASH_KEY = "introai_diagnostic_flash"
DIAGNOSTIC_ANSWER_KEY_PREFIX = "introai_diagnostic_answer_"
DIAGNOSTIC_VARIANT_ROUND_KEY = "introai_diagnostic_variant_round"
DIAGNOSTIC_UNRESOLVED_MESSAGE = "本题暂未解决，已展示参考答案并进入下一步。"
QA_DIAGNOSTIC_PLAN_KEY = "introai_qa_diagnostic_plan"
PENDING_DIAGNOSTIC_PLAN_KEY = "introai_pending_diagnostic_plan"
DIAGNOSTIC_ORIGIN_KEY = "introai_diagnostic_origin"
HANDOFF_SOURCE_TOPICS_KEY = "introai_handoff_source_topic_ids"
QA_INPUT_SESSION_TOKEN_KEY = "introai_qa_input_session_token"
QA_QUESTION_WIDGET_PREFIX = "introai_qa_question_"
_QA_INPUT_TOKEN = re.compile(r"^[0-9a-f]{32}$")


def bind_qa_diagnostic_plan(
    *, qa_result: dict[str, Any], diagnostic_plan: dict[str, Any]
) -> dict[str, Any]:
    """Return an isolated QA-result snapshot carrying its own diagnostic plan."""
    if not isinstance(qa_result, dict):
        raise ValueError("qa_result must be a dict.")
    if not isinstance(diagnostic_plan, dict):
        raise ValueError("diagnostic_plan must be a dict.")
    result = deepcopy(qa_result)
    result["diagnostic_plan"] = deepcopy(diagnostic_plan)
    return result


def resolve_qa_diagnostic_plan(
    *,
    qa_result: Any,
    cached_plan: Any = None,
) -> dict[str, Any] | None:
    """Resolve the current result's plan, with fallback for legacy QA state."""
    if isinstance(qa_result, dict) and "diagnostic_plan" in qa_result:
        plan = qa_result["diagnostic_plan"]
        return plan if isinstance(plan, dict) else None
    return cached_plan if isinstance(cached_plan, dict) else None


def store_qa_result_with_diagnostic_plan(
    session_state: Any,
    *,
    qa_result: dict[str, Any],
    diagnostic_plan: dict[str, Any],
) -> dict[str, Any]:
    """Atomically replace the current QA snapshot and its compatibility cache."""
    if not hasattr(session_state, "__setitem__"):
        raise ValueError("session_state must be a mutable mapping.")
    bound_result = bind_qa_diagnostic_plan(
        qa_result=qa_result,
        diagnostic_plan=diagnostic_plan,
    )
    session_state["introai_last_qa_result"] = bound_result
    session_state[QA_DIAGNOSTIC_PLAN_KEY] = deepcopy(
        bound_result["diagnostic_plan"]
    )
    return bound_result


def has_active_diagnostic(session_state: Any) -> bool:
    """Return whether an unfinished dual-track diagnostic is already active."""
    if not hasattr(session_state, "get"):
        return False
    result = session_state.get("introai_dual_track_result")
    return isinstance(result, dict) and result.get("phase") in {
        "formative",
        "verification_ready",
        "verification",
        "verification_unavailable",
    }


def qa_question_widget_key(
    session_state: Any,
    *,
    token_factory: Any = lambda: uuid.uuid4().hex,
) -> str:
    """Return a session-local QA widget identity.

    A stable key within one Streamlit session preserves P3e's retry behaviour.
    A fresh, non-persisted identity prevents a browser from restoring an old
    textarea value into a newly opened learner session merely because the
    field label and widget key happen to be the same.
    """
    if not hasattr(session_state, "get") or not hasattr(session_state, "__setitem__"):
        raise ValueError("session_state must be a mutable mapping.")
    token = session_state.get(QA_INPUT_SESSION_TOKEN_KEY)
    if not isinstance(token, str) or not _QA_INPUT_TOKEN.fullmatch(token):
        token = token_factory()
        if not isinstance(token, str) or not _QA_INPUT_TOKEN.fullmatch(token):
            raise ValueError("QA widget token factory must return a UUID4 hex token.")
        session_state[QA_INPUT_SESSION_TOKEN_KEY] = token
    return f"{QA_QUESTION_WIDGET_PREFIX}{token}"


def set_qa_question_value(session_state: Any, question: Any) -> str:
    """Set an explicit trusted QA prefill without changing learner evidence."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("QA prefill must be a non-empty string.")
    key = qa_question_widget_key(session_state)
    session_state[key] = question
    return key


def elapsed_seconds(started_at: float, finished_at: float) -> float:
    """Return a non-negative monotonic elapsed duration."""
    if isinstance(started_at, bool) or not isinstance(started_at, int | float):
        raise ValueError("started_at must be numeric.")
    if isinstance(finished_at, bool) or not isinstance(finished_at, int | float):
        raise ValueError("finished_at must be numeric.")
    return max(0.0, float(finished_at) - float(started_at))


def diagnostic_variant_round(session_state: Any) -> int:
    """Return the current diagnostic variant round, defaulting to zero."""
    value = session_state.get(DIAGNOSTIC_VARIANT_ROUND_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("diagnostic variant round must be a non-negative integer.")
    return value


def advance_diagnostic_variant_round(session_state: Any) -> int:
    """Advance the next diagnostic run by one deterministic variant round."""
    next_round = diagnostic_variant_round(session_state) + 1
    session_state[DIAGNOSTIC_VARIANT_ROUND_KEY] = next_round
    return next_round


def diagnostic_answer_widget_key(*, step_index: int, attempt_number: int) -> str:
    """Build a distinct text-widget key for each step and attempt."""
    if (
        isinstance(step_index, bool)
        or not isinstance(step_index, int)
        or step_index < 0
    ):
        raise ValueError("step_index must be a non-negative integer.")
    if (
        isinstance(attempt_number, bool)
        or not isinstance(attempt_number, int)
        or attempt_number < 1
    ):
        raise ValueError("attempt_number must be a positive integer.")
    return f"{DIAGNOSTIC_ANSWER_KEY_PREFIX}{step_index}_{attempt_number}"


def diagnostic_question_widget_key(question: dict[str, Any]) -> str:
    """Build a widget key from the current workflow question."""
    if not isinstance(question, dict):
        raise ValueError("question must be a dict.")
    step_number = question.get("step_number")
    attempt_number = question.get("attempt_number")
    prompt_id = question.get("prompt_id", question.get("id"))
    if (
        isinstance(step_number, bool)
        or not isinstance(step_number, int)
        or step_number < 1
    ):
        raise ValueError("question.step_number must be a positive integer.")
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        raise ValueError("question.prompt_id must be a non-empty string.")
    return diagnostic_answer_widget_key(
        step_index=step_number - 1,
        attempt_number=attempt_number,
    ) + f"_{prompt_id.strip()}"


def validate_current_diagnostic_question(
    *, session: dict[str, Any], question: dict[str, Any]
) -> dict[str, Any]:
    """Verify that a UI question is exactly the one selected by session state."""
    if not isinstance(session, dict) or not isinstance(question, dict):
        raise ValueError("session and question must be dicts.")
    if session.get("status") != "in_progress":
        raise ValueError("only an in-progress session has a current question.")
    step_index = session.get("step_index")
    attempt_in_step = session.get("attempt_in_step")
    if (
        isinstance(step_index, bool)
        or not isinstance(step_index, int)
        or step_index < 0
        or isinstance(attempt_in_step, bool)
        or not isinstance(attempt_in_step, int)
        or attempt_in_step < 0
    ):
        raise ValueError("session has invalid current step or attempt state.")
    if question.get("step_number") != step_index + 1:
        raise ValueError("question.step_number does not match session.step_index.")
    if question.get("attempt_number") != attempt_in_step + 1:
        raise ValueError("question.attempt_number does not match session.attempt_in_step.")
    question_id = question.get("id")
    prompt_id = question.get("prompt_id")
    prompt = question.get("prompt")
    if not all(isinstance(value, str) and value.strip() for value in (question_id, prompt_id, prompt)):
        raise ValueError("question must include non-empty id, prompt_id, and prompt.")
    selected_prompt_ids = session.get("selected_prompt_ids")
    if selected_prompt_ids is None:
        if prompt_id != question_id:
            raise ValueError("canonical session question has an unexpected prompt_id.")
    elif (
        not isinstance(selected_prompt_ids, list)
        or step_index >= len(selected_prompt_ids)
        or prompt_id != selected_prompt_ids[step_index]
    ):
        raise ValueError("question.prompt_id does not match the selected prompt.")
    return question


def diagnostic_attempt_status(*, session: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    """Derive visible attempt wording from the authoritative session state."""
    if not isinstance(session, dict) or not isinstance(question, dict):
        raise ValueError("session and question must be dicts.")
    attempts_used = session.get("attempt_in_step")
    max_attempts = question.get("max_attempts")
    if (
        isinstance(attempts_used, bool)
        or not isinstance(attempts_used, int)
        or attempts_used < 0
    ):
        raise ValueError("session.attempt_in_step must be a non-negative integer.")
    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts <= 0
    ):
        raise ValueError("question.max_attempts must be a positive integer.")
    if attempts_used >= max_attempts:
        raise ValueError("an answerable question cannot have exhausted attempts.")
    remaining_attempts = max_attempts - attempts_used
    if attempts_used == 0:
        message = f"本题最多作答 {max_attempts} 次"
    elif remaining_attempts == 1:
        message = "还可作答 1 次。本题最后一次作答"
    else:
        message = f"还可作答 {remaining_attempts} 次"
    return {
        "attempts_used": attempts_used,
        "max_attempts": max_attempts,
        "remaining_attempts": remaining_attempts,
        "message": message,
    }


def build_diagnostic_flash(
    *,
    previous_question: dict[str, Any],
    diagnostic: dict[str, Any],
    teaching_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a safe, one-render diagnostic feedback record."""
    if not isinstance(previous_question, dict) or not isinstance(diagnostic, dict):
        raise ValueError("previous_question and diagnostic must be dicts.")
    previous_step = previous_question.get("step_number")
    if (
        isinstance(previous_step, bool)
        or not isinstance(previous_step, int)
        or previous_step < 1
    ):
        raise ValueError("previous_question.step_number must be a positive integer.")

    evaluation = diagnostic.get("evaluation")
    if not isinstance(evaluation, dict):
        raise ValueError("diagnostic.evaluation must be a dict.")
    score = evaluation.get("score", 0.0)
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise ValueError("diagnostic evaluation score must be numeric.")
    feedback = evaluation.get("feedback", [])
    if not isinstance(feedback, list):
        raise ValueError("diagnostic evaluation feedback must be a list.")
    safe_feedback = [item for item in feedback if isinstance(item, str)]
    coverage_score = evaluation.get("coverage_score", score)
    if isinstance(coverage_score, bool) or not isinstance(coverage_score, int | float):
        raise ValueError("diagnostic evaluation coverage_score must be numeric.")
    matched_labels = _safe_student_text_list(evaluation.get("matched_labels", []))
    missing_labels = _safe_student_text_list(evaluation.get("missing_labels", []))
    semantic_supported_labels = _safe_student_text_list(
        evaluation.get("semantic_supported_labels", [])
    )
    needs_clarification = evaluation.get("needs_clarification", False)
    if not isinstance(needs_clarification, bool):
        raise ValueError("diagnostic evaluation needs_clarification must be a bool.")
    clarifying_question = evaluation.get("clarifying_question")
    if clarifying_question is not None and (
        not isinstance(clarifying_question, str) or not clarifying_question.strip()
    ):
        raise ValueError("diagnostic evaluation clarifying_question is invalid.")
    if needs_clarification != bool(semantic_supported_labels):
        raise ValueError("diagnostic clarification labels are inconsistent.")
    misconception_feedback = _safe_student_text_list(
        evaluation.get("misconception_feedback", [])
    )
    developer_trace = _safe_developer_trace(
        coverage_score=coverage_score,
        mastery_score=score,
        semantic_used=evaluation.get("semantic_used", False),
        semantic_judgments=evaluation.get("semantic_judgments", []),
        semantic_status=evaluation.get("semantic_status", "not_used"),
        semantic_confidence=evaluation.get("semantic_confidence"),
    )

    next_question = diagnostic.get("question")
    next_step = None
    if isinstance(next_question, dict):
        candidate = next_question.get("step_number")
        if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 1:
            next_step = candidate
    moved = diagnostic.get("status") == "completed" or next_step != previous_step
    passed = evaluation.get("passed") is True
    assisted = evaluation.get("assisted", False)
    if not isinstance(assisted, bool):
        raise ValueError("diagnostic evaluation assisted must be a bool.")
    assistance_level = evaluation.get("assistance_level", "reveal" if assisted else "none")
    assistance_source = evaluation.get(
        "assistance_source", "model_answer" if assisted else None
    )
    _validate_assistance_provenance(
        assisted=assisted,
        level=assistance_level,
        source=assistance_source,
    )
    unresolved = not passed and moved
    if passed:
        flash_type = "success"
    else:
        flash_type = "warning"

    flash = {
        "type": flash_type,
        "score": float(score),
        "coverage_score": float(coverage_score),
        "feedback": safe_feedback,
        "matched_labels": matched_labels,
        "missing_labels": missing_labels,
        "semantic_supported_labels": semantic_supported_labels,
        "needs_clarification": needs_clarification,
        "clarifying_question": clarifying_question,
        "misconception_feedback": misconception_feedback,
        "developer_trace": developer_trace,
        "previous_step": previous_step,
        "next_step": next_step,
        "moved_to_next_step": moved,
        "unresolved": unresolved,
        "assistance_level": assistance_level,
    }
    if teaching_feedback is not None:
        flash["teaching_feedback"] = _safe_teaching_feedback(teaching_feedback)
    if assisted:
        flash["assisted_practice"] = True
    return flash


def _validate_assistance_provenance(*, assisted: bool, level: Any, source: Any) -> None:
    sources = {
        "hint": "deterministic_feedback",
        "scaffold": "deterministic_feedback",
        "clarification": "semantic_advisory",
        "reveal": "model_answer",
    }
    if not isinstance(level, str) or level not in {"none", *sources}:
        raise ValueError("diagnostic evaluation assistance_level is invalid.")
    if assisted != (level != "none"):
        raise ValueError("diagnostic evaluation assistance provenance is inconsistent.")
    if level == "none":
        if source is not None:
            raise ValueError("diagnostic evaluation assistance_source is invalid.")
    elif source != sources[level]:
        raise ValueError("diagnostic evaluation assistance_source is invalid.")


def _safe_student_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("student-facing evaluation field must be a list.")
    return [item for item in value if isinstance(item, str) and item.strip()]


def _safe_developer_trace(
    *,
    coverage_score: float | int,
    mastery_score: float | int,
    semantic_used: Any,
    semantic_judgments: Any,
    semantic_status: Any,
    semantic_confidence: Any,
) -> dict[str, Any]:
    """Keep only validated, non-raw scoring metadata for developer details."""
    if not isinstance(semantic_used, bool):
        raise ValueError("diagnostic evaluation semantic_used must be a bool.")
    if not isinstance(semantic_judgments, list):
        raise ValueError("diagnostic evaluation semantic_judgments must be a list.")
    if semantic_status not in {"advisory", "abstained", "rejected", "not_used"}:
        raise ValueError("diagnostic evaluation semantic_status is invalid.")
    if semantic_confidence is not None and (
        isinstance(semantic_confidence, bool)
        or not isinstance(semantic_confidence, int | float)
        or not 0.0 <= semantic_confidence <= 1.0
    ):
        raise ValueError("diagnostic evaluation semantic_confidence is invalid.")
    judgments: list[dict[str, str]] = []
    for judgment in semantic_judgments:
        if not isinstance(judgment, dict) or set(judgment) != {
            "criterion_id",
            "status",
        }:
            raise ValueError("diagnostic evaluation semantic judgment is invalid.")
        criterion_id = judgment["criterion_id"]
        status = judgment["status"]
        if not isinstance(criterion_id, str) or not criterion_id.strip() or not isinstance(status, str):
            raise ValueError("diagnostic evaluation semantic judgment is invalid.")
        judgments.append({"criterion_id": criterion_id, "status": status})
    return {
        "coverage_score": float(coverage_score),
        "mastery_score": float(mastery_score),
        "assessment_source": "deterministic",
        "semantic_status": semantic_status,
        "semantic_confidence": semantic_confidence,
        "semantic_judgments": judgments,
    }


def _safe_teaching_feedback(value: Any) -> dict[str, Any]:
    """Keep only the explicitly student-facing teaching-feedback fields."""
    if not isinstance(value, dict):
        raise ValueError("teaching_feedback must be a dict.")
    mode = value.get("mode")
    remaining_attempts = value.get("remaining_attempts")
    messages = value.get("messages")
    model_answer = value.get("model_answer")
    explanation = value.get("explanation")
    if mode not in {"hint", "scaffold", "reveal"}:
        raise ValueError("teaching_feedback.mode is invalid.")
    if (
        isinstance(remaining_attempts, bool)
        or not isinstance(remaining_attempts, int)
        or remaining_attempts < 0
    ):
        raise ValueError("teaching_feedback.remaining_attempts is invalid.")
    if not isinstance(messages, list) or not all(
        isinstance(message, str) and message.strip() for message in messages
    ):
        raise ValueError("teaching_feedback.messages is invalid.")
    if model_answer is not None and (
        not isinstance(model_answer, str) or not model_answer.strip()
    ):
        raise ValueError("teaching_feedback.model_answer is invalid.")
    if explanation is not None and (
        not isinstance(explanation, str) or not explanation.strip()
    ):
        raise ValueError("teaching_feedback.explanation is invalid.")
    return {
        "mode": mode,
        "remaining_attempts": remaining_attempts,
        "messages": list(messages),
        "model_answer": model_answer,
        "explanation": explanation,
    }


def consume_diagnostic_flash(session_state: Any) -> dict[str, Any] | None:
    """Pop the diagnostic flash so it can only be rendered once."""
    flash = session_state.pop(DIAGNOSTIC_FLASH_KEY, None)
    return flash if isinstance(flash, dict) else None


def clear_diagnostic_state(
    session_state: Any, *, preserve_learning_outcome: bool = False
) -> None:
    """Clear diagnostic-only state while optionally retaining completed outcomes."""
    qa_result = session_state.get("introai_last_qa_result")
    if isinstance(qa_result, dict) and "diagnostic_plan" in qa_result:
        preserved_qa_result = deepcopy(qa_result)
        preserved_qa_result.pop("diagnostic_plan", None)
        session_state["introai_last_qa_result"] = preserved_qa_result
    for key in (
        "introai_diagnostic_session",
        "introai_diagnostic_result",
        "introai_diagnostic_error",
        "introai_diagnostic_answer",
        DIAGNOSTIC_FLASH_KEY,
        "introai_dual_track_result",
        "introai_dual_track_session",
        "introai_diagnostic_mode",
        "introai_formative_feedback_error",
        QA_DIAGNOSTIC_PLAN_KEY,
        PENDING_DIAGNOSTIC_PLAN_KEY,
        DIAGNOSTIC_ORIGIN_KEY,
        HANDOFF_SOURCE_TOPICS_KEY,
        "introai_scroll_request",
        "introai_scroll_consumed_events",
    ):
        session_state.pop(key, None)
    if not preserve_learning_outcome:
        session_state.pop("introai_last_recommendation", None)
    for key in list(session_state.keys()):
        if isinstance(key, str) and (
            key.startswith(DIAGNOSTIC_ANSWER_KEY_PREFIX)
            or key.startswith("introai_formative_answer_")
            or key.startswith("introai_verification_")
        ):
            session_state.pop(key, None)
