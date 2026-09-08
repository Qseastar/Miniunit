"""Pure, deterministic teaching feedback for diagnostic retries.

The thresholds below are MVP heuristics for the current three-step diagnostic
track. They are intentionally explicit configuration, not empirically
validated educational thresholds.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


LOW_SCORE_REVEAL_THRESHOLD = 0.25
LOW_MASTERY_REVEAL_THRESHOLD = 0.30
HIGH_SCORE_HINT_THRESHOLD = 0.60
HIGH_MASTERY_HINT_THRESHOLD = 0.60

_TEACHING_SUPPORT_FIELDS = {"model_answer", "explanation", "scaffold"}

# These are student-visible canonical labels, not rubric IDs or matching terms.
# They make the MVP clarification concrete without asking a model to invent
# teaching content. Unknown future labels use the safe generic fallback below.
_CLARIFYING_QUESTIONS = {
    "BFS 的逐层扩展顺序": (
        "请进一步说明：队列的处理顺序如何使 BFS 先完成当前层，再进入下一层？"
    ),
    "动作或边代价不同时使用 UCS": (
        "请再明确：这种搜索策略叫什么，通常用于哪种动作代价情形？"
    ),
}


class DiagnosticFeedbackError(ValueError):
    """Raised when teaching-support data or feedback inputs are invalid."""


def validate_teaching_support(value: Any) -> None:
    """Validate the optional, human-authored teaching-support schema."""
    if not isinstance(value, dict) or set(value) != _TEACHING_SUPPORT_FIELDS:
        fields = ", ".join(sorted(_TEACHING_SUPPORT_FIELDS))
        raise DiagnosticFeedbackError(
            f"teaching_support must be an object with exactly: {fields}."
        )
    for field in sorted(_TEACHING_SUPPORT_FIELDS):
        text = value[field]
        if not isinstance(text, str) or not text.strip():
            raise DiagnosticFeedbackError(
                f"teaching_support.{field} must be a non-empty string."
            )


def build_semantic_clarification(
    *,
    missing_labels: Any,
    semantic_supported_labels: Any,
) -> str | None:
    """Return one deterministic clarification question for advisory evidence.

    Only student-visible labels enter this function. It deliberately receives
    neither internal rubric terms nor raw semantic judgments.
    """
    normalized_missing = _validate_messages(missing_labels)
    normalized_supported = _validate_messages(semantic_supported_labels)
    candidates = [
        label for label in normalized_missing if label in normalized_supported
    ]
    if not candidates:
        return None
    label = candidates[0]
    return _CLARIFYING_QUESTIONS.get(label, f"请进一步说明：{label}。")


def build_teaching_feedback(
    *,
    score: Any,
    concept_ids: Any,
    learner_state: Any,
    attempts_used: Any,
    max_attempts: Any,
    assessment_feedback: Any,
    teaching_support: Any = None,
    needs_clarification: Any = False,
    clarifying_question: Any = None,
) -> dict[str, Any]:
    """Return safe student-facing feedback without modifying any input.

    ``assessment_feedback`` is already the sanitized feedback from the
    deterministic assessor. The returned object deliberately excludes rubrics,
    matching terms, misconception patterns, and internal thresholds.
    """
    normalized_score = _validate_unit_number(score, "score")
    normalized_concept_ids = _validate_concept_ids(concept_ids)
    mastery_signal = _mastery_signal(learner_state, normalized_concept_ids)
    normalized_attempts, normalized_max_attempts = _validate_attempts(
        attempts_used, max_attempts
    )
    messages = _validate_messages(assessment_feedback)
    if teaching_support is not None:
        validate_teaching_support(teaching_support)
    if not isinstance(needs_clarification, bool):
        raise DiagnosticFeedbackError("needs_clarification must be a bool.")
    if clarifying_question is not None and (
        not isinstance(clarifying_question, str) or not clarifying_question.strip()
    ):
        raise DiagnosticFeedbackError("clarifying_question must be a non-empty string or None.")
    if needs_clarification and clarifying_question is None:
        raise DiagnosticFeedbackError(
            "clarifying_question is required when needs_clarification is true."
        )

    remaining_attempts = normalized_max_attempts - normalized_attempts
    if remaining_attempts == 0:
        mode = "reveal"
    elif needs_clarification:
        # Advisory semantic evidence may help the student formulate a retry.
        # The workflow records that help as provenance for the next attempt;
        # this assessment itself remains an independent raw observation.
        mode = "scaffold"
    elif (
        normalized_attempts == 1
        and normalized_score < LOW_SCORE_REVEAL_THRESHOLD
        and mastery_signal < LOW_MASTERY_REVEAL_THRESHOLD
    ):
        mode = "reveal"
    elif normalized_attempts == 1 and (
        normalized_score >= HIGH_SCORE_HINT_THRESHOLD
        or mastery_signal >= HIGH_MASTERY_HINT_THRESHOLD
    ):
        mode = "hint"
    else:
        mode = "scaffold"

    model_answer = None
    explanation = None
    if mode == "scaffold":
        if teaching_support is not None:
            messages.append(teaching_support["scaffold"])
    elif mode == "reveal":
        if teaching_support is not None:
            model_answer = teaching_support["model_answer"]
            explanation = teaching_support["explanation"]
        if remaining_attempts:
            messages.append(
                "请阅读参考答案后，用自己的话重新作答。"
                if teaching_support is not None
                else "请结合上述提示，用自己的话重新作答。"
            )
        else:
            messages.append(
                "已展示参考答案，本题暂未解决并进入下一步。"
                if teaching_support is not None
                else "本题暂未解决并进入下一步。"
            )

    return {
        "mode": mode,
        "remaining_attempts": remaining_attempts,
        "messages": messages,
        "model_answer": model_answer,
        "explanation": explanation,
    }


def _validate_unit_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DiagnosticFeedbackError(f"{field_name} must be a finite number from 0 to 1.")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise DiagnosticFeedbackError(f"{field_name} must be a finite number from 0 to 1.")
    return result


def _validate_concept_ids(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DiagnosticFeedbackError("concept_ids must be a non-empty list.")
    result: list[str] = []
    for concept_id in value:
        if not isinstance(concept_id, str) or not concept_id.strip():
            raise DiagnosticFeedbackError("concept_ids must contain non-empty strings.")
        if concept_id not in result:
            result.append(concept_id)
    return result


def _mastery_signal(learner_state: Any, concept_ids: list[str]) -> float:
    if not isinstance(learner_state, dict):
        raise DiagnosticFeedbackError("learner_state must be a dict.")
    mastery = learner_state.get("mastery", {})
    if not isinstance(mastery, dict):
        raise DiagnosticFeedbackError("learner_state.mastery must be a dict.")
    values: list[float] = []
    for concept_id in concept_ids:
        value = mastery.get(concept_id, 0.0)
        values.append(_validate_unit_number(value, f"mastery[{concept_id!r}]"))
    return min(values)


def _validate_attempts(attempts_used: Any, max_attempts: Any) -> tuple[int, int]:
    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts <= 0
    ):
        raise DiagnosticFeedbackError("max_attempts must be a positive integer.")
    if (
        isinstance(attempts_used, bool)
        or not isinstance(attempts_used, int)
        or attempts_used < 1
        or attempts_used > max_attempts
    ):
        raise DiagnosticFeedbackError(
            "attempts_used must be an integer from 1 through max_attempts."
        )
    return attempts_used, max_attempts


def _validate_messages(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise DiagnosticFeedbackError("assessment_feedback must be a list of strings.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise DiagnosticFeedbackError(
                "assessment_feedback must contain non-empty strings."
            )
        result.append(item)
    return deepcopy(result)
