from __future__ import annotations

import math
import re
import unicodedata
from itertools import product
from typing import Any

from introai_tutor.deepseek_adapter import DeepSeekRequestError, DeepSeekResponseError
from introai_tutor.diagnostic_feedback import build_semantic_clarification
from introai_tutor.diagnostic_semantics import DiagnosticSemanticAdjudicationError

# ── evaluation result constants ──────────────────────────────────────────────

VALID_RESULTS = {"correct", "partially_correct", "incorrect"}

# Target mastery values for each result type.
RESULT_TARGET = {
    "correct": 1.0,
    "partially_correct": 0.7,
    "incorrect": 0.0,
}

DEFAULT_LEARNING_RATE = 0.15
OPTIONAL_GROUP_BONUS = 0.20
# A semantic judgment may supplement a narrow phrase rubric only when the
# injected classifier explicitly reports a sufficiently confident result.
# This is a product-safety boundary, not an empirically calibrated threshold.
SEMANTIC_MIN_CONFIDENCE = 0.75


def assess_structured_answer(
    answer: str,
    assessment: dict,
    *,
    semantic_adjudicator: Any | None = None,
    question_context: str | None = None,
) -> dict[str, Any]:
    """Assess an answer with Python-controlled coverage and pass/fail.

    ``coverage_score`` and legacy ``score`` measure deterministic rubric
    propositions. ``mastery_score`` is the conservative observation used by
    diagnostic state updates: deterministic coverage when there is no blocking
    misconception, or ``0.0`` when there is one. The optional injected
    adjudicator is advisory only: it can identify a proposition that merits a
    student clarification, but can never make an answer pass or raise mastery.
    """
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer must be a non-empty string.")
    if semantic_adjudicator is not None and not callable(
        getattr(semantic_adjudicator, "adjudicate", None)
    ):
        raise DiagnosticSemanticAdjudicationError(
            "semantic_adjudicator must provide a callable adjudicate method."
        )
    if question_context is not None and (
        not isinstance(question_context, str) or not question_context.strip()
    ):
        raise ValueError("question_context must be a non-empty string when provided.")
    _validate_structured_assessment(assessment)

    normalized_answer = _normalize_structured_text(answer)
    required_groups = assessment["required_groups"]
    optional_groups = assessment["optional_groups"]
    matched_required = [
        group["id"] for group in required_groups if _group_matches(normalized_answer, group)
    ]
    matched_optional = [
        group["id"] for group in optional_groups if _group_matches(normalized_answer, group)
    ]
    misconceptions = [
        item
        for item in assessment["blocking_misconceptions"]
        if any(
            _blocking_pattern_matches(normalized_answer, pattern)
            for pattern in item["patterns"]
        )
    ]
    missing_required = [
        group["id"] for group in required_groups if group["id"] not in matched_required
    ]

    semantic_used = False
    semantic_applied = False
    semantic_judgments: list[dict[str, str]] = []
    semantic_supported_group_ids: list[str] = []
    semantic_confidence: float | None = None
    semantic_abstain_reason: str | None = None
    semantic_rejection_reason: str | None = None
    semantic_status = "not_used"
    semantic_eligibility_reason = _semantic_trigger_reason(
        normalized_answer=normalized_answer,
        matched_required=matched_required,
        missing_required=missing_required,
        misconceptions=misconceptions,
        assessment=assessment,
        semantic_adjudicator=object(),
    )
    semantic_trigger_reason = _semantic_trigger_reason(
        normalized_answer=normalized_answer,
        matched_required=matched_required,
        missing_required=missing_required,
        misconceptions=misconceptions,
        assessment=assessment,
        semantic_adjudicator=semantic_adjudicator,
    )
    if semantic_trigger_reason == "eligible_incomplete_answer":
        try:
            adjudication = _validate_semantic_adjudication(
                semantic_adjudicator.adjudicate(
                    answer=answer,
                    criteria=_semantic_criteria(assessment),
                    question_context=question_context,
                ),
                allowed_ids={
                    item["id"]
                    for item in [
                        *required_groups,
                        *optional_groups,
                        *assessment["blocking_misconceptions"],
                    ]
                },
            )
        except (DeepSeekRequestError, DeepSeekResponseError):
            # An unavailable optional model must not stop an offline diagnostic.
            adjudication = None
            semantic_status = "rejected"
            semantic_rejection_reason = "adapter_unavailable"
        except DiagnosticSemanticAdjudicationError:
            # A malformed semantic response is not a learner-facing scoring
            # failure. Keep the deterministic result and record only a stable
            # internal reason; never expose the raw model response.
            adjudication = None
            semantic_status = "rejected"
            semantic_rejection_reason = "invalid_semantic_response"
        if adjudication is not None:
            semantic_used = True
            semantic_judgments = list(adjudication["judgments"])
            semantic_confidence = adjudication["confidence"]
            group_ids = {group["id"] for group in [*required_groups, *optional_groups]}
            misconception_by_id = {
                item["id"]: item for item in assessment["blocking_misconceptions"]
            }
            conflict = _semantic_conflicts_with_deterministic_evidence(
                semantic_judgments=semantic_judgments,
                deterministic_group_ids={*matched_required, *matched_optional},
                deterministic_misconception_ids={item["id"] for item in misconceptions},
                group_ids=group_ids,
                misconception_ids=set(misconception_by_id),
            )
            if semantic_confidence < SEMANTIC_MIN_CONFIDENCE:
                semantic_abstain_reason = "low_confidence"
                semantic_status = "abstained"
            elif conflict:
                semantic_abstain_reason = "conflicting_judgment"
                semantic_status = "abstained"
            else:
                for judgment in semantic_judgments:
                    criterion_id = judgment["criterion_id"]
                    if (
                        judgment["status"] == "entailed"
                        and criterion_id in missing_required
                        and criterion_id not in semantic_supported_group_ids
                    ):
                        semantic_supported_group_ids.append(criterion_id)
                semantic_supported_group_ids = [
                    group["id"]
                    for group in required_groups
                    if group["id"] in semantic_supported_group_ids
                ]
                if semantic_supported_group_ids:
                    semantic_applied = True
                    semantic_status = "advisory"

    required_coverage = len(matched_required) / len(required_groups)
    optional_coverage = (
        len(matched_optional) / len(optional_groups) if optional_groups else 0.0
    )
    coverage_score = min(
        1.0, required_coverage + OPTIONAL_GROUP_BONUS * optional_coverage
    )
    score = coverage_score
    mastery_score = 0.0 if misconceptions else coverage_score
    passed = coverage_score >= assessment["pass_threshold"] and not misconceptions
    if coverage_score == 1.0 and not misconceptions:
        # Make the scoring invariant explicit for future rubric changes.
        passed = True
    labels = {
        group["id"]: group["label"] for group in [*required_groups, *optional_groups]
    }
    matched_labels = [labels[group_id] for group_id in [*matched_required, *matched_optional]]
    missing_labels = [labels[group_id] for group_id in missing_required]
    semantic_supported_labels = [
        labels[group_id] for group_id in semantic_supported_group_ids
    ]
    needs_clarification = bool(semantic_supported_group_ids)
    clarifying_question = (
        build_semantic_clarification(
            missing_labels=missing_labels,
            semantic_supported_labels=semantic_supported_labels,
        )
        if needs_clarification
        else None
    )
    misconception_feedback = [item["feedback"] for item in misconceptions]
    feedback_items = [f"还需要说明：{label}。" for label in missing_labels]
    feedback_items.extend(misconception_feedback)
    if semantic_abstain_reason is not None:
        feedback_items.append("回答仍需补充说明，以确认关键条件。")
    return {
        "score": score,
        "coverage_score": coverage_score,
        "mastery_score": mastery_score,
        "passed": passed,
        "matched_required_group_ids": matched_required,
        "missing_required_group_ids": missing_required,
        "matched_optional_group_ids": matched_optional,
        "misconception_ids": [item["id"] for item in misconceptions],
        "matched_labels": matched_labels,
        "missing_labels": missing_labels,
        "misconception_feedback": misconception_feedback,
        "feedback_items": feedback_items,
        "semantic_uncertain": _is_semantic_uncertain(
            normalized_answer=normalized_answer,
            missing_required=missing_required,
            misconceptions=misconceptions,
            assessment=assessment,
        ),
        "semantic_used": semantic_used,
        "semantic_applied": semantic_applied,
        "semantic_authority_applied": False,
        "semantic_confidence": semantic_confidence,
        "semantic_abstained": semantic_abstain_reason is not None,
        "semantic_abstain_reason": semantic_abstain_reason,
        "semantic_rejection_reason": semantic_rejection_reason,
        "semantic_status": semantic_status,
        "semantic_supported_group_ids": semantic_supported_group_ids,
        "semantic_supported_labels": semantic_supported_labels,
        "needs_clarification": needs_clarification,
        "clarifying_question": clarifying_question,
        "semantic_trigger_eligible": semantic_eligibility_reason
        == "eligible_incomplete_answer",
        "semantic_eligibility_reason": semantic_eligibility_reason,
        "semantic_trigger_reason": semantic_trigger_reason,
        "semantic_judgments": semantic_judgments,
    }


def validate_structured_assessment(assessment: dict) -> None:
    """Public validation helper for optional diagnostic-question rubrics."""
    _validate_structured_assessment(assessment)


def _validate_structured_assessment(assessment: Any) -> None:
    if not isinstance(assessment, dict):
        raise ValueError("assessment must be an object.")
    required_fields = {
        "required_groups",
        "optional_groups",
        "blocking_misconceptions",
        "pass_threshold",
    }
    missing = sorted(required_fields - assessment.keys())
    if missing:
        raise ValueError("assessment is missing fields: " + ", ".join(missing))
    required_groups = _validate_groups(
        assessment["required_groups"], "required_groups", require_non_empty=True
    )
    optional_groups = _validate_groups(
        assessment["optional_groups"], "optional_groups", require_non_empty=False
    )
    group_ids = [group["id"] for group in [*required_groups, *optional_groups]]
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("assessment group ids must be unique.")

    misconceptions = assessment["blocking_misconceptions"]
    if not isinstance(misconceptions, list):
        raise ValueError("blocking_misconceptions must be a list.")
    misconception_ids: set[str] = set()
    for index, item in enumerate(misconceptions):
        if not isinstance(item, dict):
            raise ValueError(f"blocking_misconceptions[{index}] must be an object.")
        for field in ("id", "patterns", "feedback"):
            if field not in item:
                raise ValueError(f"blocking_misconceptions[{index}] is missing {field}.")
        misconception_id = _validate_non_empty_string(item["id"], f"blocking_misconceptions[{index}].id")
        if misconception_id in misconception_ids:
            raise ValueError("blocking_misconception ids must be unique.")
        misconception_ids.add(misconception_id)
        _validate_string_list(
            item["patterns"], f"blocking_misconceptions[{index}].patterns", require_non_empty=True
        )
        _validate_non_empty_string(item["feedback"], f"blocking_misconceptions[{index}].feedback")
        if "proposition" in item:
            _validate_non_empty_string(
                item["proposition"], f"blocking_misconceptions[{index}].proposition"
            )
    if set(group_ids) & misconception_ids:
        raise ValueError("assessment group and blocking misconception ids must be distinct.")

    threshold = assessment["pass_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, int | float):
        raise ValueError("pass_threshold must be a number between 0 and 1.")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("pass_threshold must be between 0 and 1.")


def _validate_groups(value: Any, name: str, *, require_non_empty: bool) -> list[dict]:
    if not isinstance(value, list) or (require_non_empty and not value):
        qualifier = "a non-empty list" if require_non_empty else "a list"
        raise ValueError(f"{name} must be {qualifier}.")
    result: list[dict] = []
    for index, group in enumerate(value):
        if not isinstance(group, dict):
            raise ValueError(f"{name}[{index}] must be an object.")
        for field in ("id", "label", "terms"):
            if field not in group:
                raise ValueError(f"{name}[{index}] is missing {field}.")
        _validate_non_empty_string(group["id"], f"{name}[{index}].id")
        _validate_non_empty_string(group["label"], f"{name}[{index}].label")
        _validate_string_list(group["terms"], f"{name}[{index}].terms", require_non_empty=True)
        if "conditional_match" in group:
            _validate_conditional_match(
                group["conditional_match"], f"{name}[{index}].conditional_match"
            )
        result.append(group)
    return result


def _validate_conditional_match(value: Any, name: str) -> None:
    """Validate a bounded, data-declared relation matcher for one criterion."""
    if not isinstance(value, dict) or set(value) != {"term_sets", "relation_terms"}:
        raise ValueError(f"{name} must contain exactly term_sets and relation_terms.")
    term_sets = value["term_sets"]
    if not isinstance(term_sets, list) or len(term_sets) < 2:
        raise ValueError(f"{name}.term_sets must contain at least two term lists.")
    for index, terms in enumerate(term_sets):
        _validate_string_list(terms, f"{name}.term_sets[{index}]", require_non_empty=True)
    _validate_string_list(value["relation_terms"], f"{name}.relation_terms", require_non_empty=True)


def _validate_non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise ValueError(f"{name} must be a non-empty string.")
    return normalized


def _validate_string_list(value: Any, name: str, *, require_non_empty: bool) -> None:
    if not isinstance(value, list) or (require_non_empty and not value):
        qualifier = "a non-empty list" if require_non_empty else "a list"
        raise ValueError(f"{name} must be {qualifier}.")
    for index, item in enumerate(value):
        _validate_non_empty_string(item, f"{name}[{index}]")


def _normalize_structured_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[,，。！？!?；;：:、】【】『』“”‘’\"'`]+", " ", normalized)
    normalized = re.sub(r"[-–—_/\\]+", " ", normalized)
    return " ".join(normalized.split())


def _group_matches(normalized_answer: str, group: dict) -> bool:
    return any(_term_matches(normalized_answer, term) for term in group["terms"]) or (
        "conditional_match" in group
        and _conditional_group_matches(normalized_answer, group["conditional_match"])
    )


def _conditional_group_matches(normalized_answer: str, conditional_match: dict) -> bool:
    """Match two or more propositions only when a stated relation links them.

    This is deliberately narrower than generic semantic similarity: every
    configured concept set and one configured limiting/contrast relation must
    occur in the span delimited by those configured concepts. It supports reviewed constructions
    such as ``步数最少才等价于路径总代价最小`` without treating two unrelated
    occurrences of ``最小`` as a distinction.
    """
    term_set_spans = [
        [
            span
            for term in terms
            for span in _term_spans(normalized_answer, term)
        ]
        for terms in conditional_match["term_sets"]
    ]
    if any(not spans for spans in term_set_spans):
        return False
    relation_spans = [
        span
        for term in conditional_match["relation_terms"]
        for span in _term_spans(normalized_answer, term)
    ]
    if not relation_spans:
        return False
    for concept_spans in product(*term_set_spans):
        start = min(span[0] for span in concept_spans)
        end = max(span[1] for span in concept_spans)
        if any(start <= relation_start and relation_end <= end for relation_start, relation_end in relation_spans):
            return True
    return False


def _term_spans(normalized_answer: str, term: str) -> list[tuple[int, int]]:
    normalized_term = _normalize_structured_text(term)
    if not normalized_term:
        return []
    if re.fullmatch(r"[a-z0-9 ()+*]+", normalized_term):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
    else:
        pattern = re.escape(normalized_term)
    return [(match.start(), match.end()) for match in re.finditer(pattern, normalized_answer)]


def _semantic_criteria(assessment: dict) -> list[dict[str, str]]:
    """Build the adjudicator's explicit, allow-listed proposition catalog."""
    criteria: list[dict[str, str]] = []
    for group in [*assessment["required_groups"], *assessment["optional_groups"]]:
        criteria.append(
            {
                "criterion_id": group["id"],
                "kind": "coverage",
                "statement": group["label"],
            }
        )
    for item in assessment["blocking_misconceptions"]:
        criteria.append(
            {
                "criterion_id": item["id"],
                "kind": "misconception",
                "statement": item.get("proposition", item["feedback"]),
            }
        )
    return criteria


def _validate_semantic_adjudication(
    value: Any, *, allowed_ids: set[str]
) -> dict[str, Any]:
    """Defend the Python decision boundary even for a custom injected judge."""
    if not isinstance(value, dict) or set(value) != {"judgments", "confidence"}:
        raise DiagnosticSemanticAdjudicationError(
            "semantic adjudication must contain exactly judgments and confidence."
        )
    confidence = value["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not math.isfinite(float(confidence))
        or not 0.0 <= confidence <= 1.0
    ):
        raise DiagnosticSemanticAdjudicationError(
            "semantic confidence must be a number between 0 and 1."
        )
    if not isinstance(value["judgments"], list):
        raise DiagnosticSemanticAdjudicationError("semantic judgments must be a list.")
    judgments: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in value["judgments"]:
        if not isinstance(item, dict) or set(item) != {"criterion_id", "status"}:
            raise DiagnosticSemanticAdjudicationError(
                "semantic judgment has an invalid schema."
            )
        criterion_id = item["criterion_id"]
        status = item["status"]
        if not isinstance(criterion_id, str) or criterion_id not in allowed_ids:
            raise DiagnosticSemanticAdjudicationError(
                "semantic judgment has an unknown criterion_id."
            )
        if criterion_id in seen_ids:
            raise DiagnosticSemanticAdjudicationError(
                "semantic judgment duplicates criterion_id."
            )
        if status not in {"entailed", "contradicted", "not_mentioned"}:
            raise DiagnosticSemanticAdjudicationError(
                "semantic judgment has an invalid status."
            )
        seen_ids.add(criterion_id)
        judgments.append({"criterion_id": criterion_id, "status": status})
    return {"judgments": judgments, "confidence": float(confidence)}


def _should_request_semantic_adjudication(
    *,
    normalized_answer: str,
    matched_required: list[str],
    missing_required: list[str],
    misconceptions: list[dict],
    assessment: dict,
    semantic_adjudicator: Any | None,
) -> bool:
    """Limit model use to substantial, in-scope incomplete answers only."""
    return (
        _semantic_trigger_reason(
            normalized_answer=normalized_answer,
            matched_required=matched_required,
            missing_required=missing_required,
            misconceptions=misconceptions,
            assessment=assessment,
            semantic_adjudicator=semantic_adjudicator,
        )
        == "eligible_incomplete_answer"
    )


def _semantic_trigger_reason(
    *,
    normalized_answer: str,
    matched_required: list[str],
    missing_required: list[str],
    misconceptions: list[dict],
    assessment: dict,
    semantic_adjudicator: Any | None,
) -> str:
    """Return a controlled internal reason for the semantic-call decision."""
    if semantic_adjudicator is None or misconceptions or not missing_required:
        if semantic_adjudicator is None:
            return "not_configured"
        if misconceptions:
            return "confirmed_blocking_misconception"
        return "complete_deterministic"
    if not _has_substantive_answer(normalized_answer):
        return "insubstantial_answer"
    if _looks_like_prompt_injection(normalized_answer):
        return "untrusted_instruction"
    if not _has_course_reasoning_anchor(normalized_answer):
        return "no_course_reasoning_anchor"
    # A natural-language explanation can be relevant even when none of the
    # deliberately narrow deterministic phrases matched. The adjudicator gets
    # only the rubric's allow-listed propositions and cannot decide a score.
    return "eligible_incomplete_answer"


def _has_substantive_answer(normalized_answer: str) -> bool:
    """Reject short acknowledgements while allowing a real free-text explanation."""
    if len(normalized_answer) < 16:
        return False
    return len(re.findall(r"[\w\u4e00-\u9fff]", normalized_answer)) >= 8


def _looks_like_prompt_injection(normalized_answer: str) -> bool:
    """Reject explicit instruction attacks before an optional model call."""
    markers = (
        "ignore previous instructions",
        "ignore all instructions",
        "system prompt",
        "reveal the rubric",
        "忽略之前的指令",
        "忽略所有指令",
        "输出评分",
        "泄露评分标准",
    )
    return any(marker in normalized_answer for marker in markers)


def _has_course_reasoning_anchor(normalized_answer: str) -> bool:
    """Keep clearly off-topic prose away from an otherwise useful fallback.

    These are compact domain anchors, deliberately broader than rubric terms:
    a natural paraphrase can reach semantic adjudication without making every
    unrelated long answer an API call.
    """
    anchors = (
        "bfs",
        "ucs",
        "search",
        "搜索",
        "路径",
        "节点",
        "frontier",
        "队列",
        "代价",
        "成本",
        "花费",
        "费用",
        "扩展",
        "深度",
        "g(n)",
    )
    return any(anchor in normalized_answer for anchor in anchors)


def _semantic_conflicts_with_deterministic_evidence(
    *,
    semantic_judgments: list[dict[str, str]],
    deterministic_group_ids: set[str],
    deterministic_misconception_ids: set[str],
    group_ids: set[str],
    misconception_ids: set[str],
) -> bool:
    """Detect evidence disagreement before semantic advice is shown as support."""
    for judgment in semantic_judgments:
        criterion_id = judgment["criterion_id"]
        status = judgment["status"]
        if status == "contradicted" and criterion_id in deterministic_group_ids:
            return True
        if (
            status == "entailed"
            and criterion_id in misconception_ids
            and criterion_id not in deterministic_misconception_ids
        ):
            return True
    return False


def _is_semantic_uncertain(
    *,
    normalized_answer: str,
    missing_required: list[str],
    misconceptions: list[dict],
    assessment: dict,
) -> bool:
    """Expose the deterministic uncertainty signal without calling a model."""
    return _should_request_semantic_adjudication(
        normalized_answer=normalized_answer,
        matched_required=[],
        missing_required=missing_required,
        misconceptions=misconceptions,
        assessment=assessment,
        semantic_adjudicator=object(),
    )


def _term_matches(normalized_answer: str, term: str) -> bool:
    normalized_term = _normalize_structured_text(term)
    if re.search(r"[a-z0-9]", normalized_term):
        pattern = r"(?<![a-z0-9_])" + re.escape(normalized_term) + r"(?![a-z0-9_])"
        return re.search(pattern, normalized_answer) is not None
    return normalized_term in normalized_answer


_NEGATION_MARKERS = tuple(
    _normalize_structured_text(marker)
    for marker in (
        "并不总是",
        "不总是",
        "并不",
        "并非",
        "不是",
        "不会",
        "不",
        "does not",
        "doesn't",
        "is not",
        "isn't",
        "never",
        "not",
    )
)

# Some Chinese and English negations include the relation verb immediately
# before the misconception phrase (for example, ``不是按路径总步数``).  They
# cannot be caught by a simple ``endswith("不是")`` check after normalization.
_NEGATED_RELATION_PREFIXES = tuple(
    _normalize_structured_text(marker)
    for marker in (
        "不按",
        "不是按",
        "并不是按",
        "不依据",
        "不根据",
        "不只看",
        "不是只看",
        "not based on",
        "does not use",
        "doesn't use",
    )
)

_NEGATED_CLAIM_MARKERS = tuple(
    _normalize_structured_text(marker)
    for marker in (
        "不保证",
        "并不保证",
        "不能保证",
        "并非",
        "不是",
        "不保证在",
        "并不保证在",
        "不一定",
        "未必",
        "but not",
        "does not guarantee",
        "doesn't guarantee",
    )
)


def _blocking_pattern_matches(normalized_answer: str, pattern: str) -> bool:
    """Match a misconception unless its local occurrence is explicitly negated."""
    normalized_pattern = _normalize_structured_text(pattern)
    if not normalized_pattern:
        return False
    if re.search(r"[a-z0-9]", normalized_pattern):
        expression = r"(?<![a-z0-9_])" + re.escape(normalized_pattern) + r"(?![a-z0-9_])"
    else:
        expression = re.escape(normalized_pattern)
    for match in re.finditer(expression, normalized_answer):
        local_prefix = normalized_answer[max(0, match.start() - 24) : match.start()].rstrip()
        local_suffix = normalized_answer[match.end() : match.end() + 16].lstrip()
        local_context = f"{local_prefix} {local_suffix}"
        if (
            not any(local_prefix.endswith(marker) for marker in _NEGATION_MARKERS)
            and not any(marker in local_prefix for marker in _NEGATED_RELATION_PREFIXES)
            and not any(marker in local_context for marker in _NEGATED_CLAIM_MARKERS)
        ):
            return True
    return False


# ── answer evaluation ────────────────────────────────────────────────────────

def evaluate_answer(
    student_answer: str,
    expected_keywords: list[str] | None = None,
    *,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Evaluate a student answer against expected keywords.

    Parameters
    ----------
    student_answer : str
        The free-text answer provided by the student.
    expected_keywords : list[str] or None
        Keywords that should appear in a correct answer.
        If None or empty, the answer is treated as unevaluable and returns
        ``"unknown"``.
    case_sensitive : bool
        If True, keyword matching is case-sensitive (default False).

    Returns
    -------
    dict
        {"result": "correct"|"partially_correct"|"incorrect"|"unknown",
         "matched": [...], "missing": [...], "feedback": str}
    """
    if not expected_keywords:
        return {
            "result": "unknown",
            "matched": [],
            "missing": [],
            "feedback": "No evaluation criteria provided.",
        }

    compare = student_answer if case_sensitive else student_answer.lower()
    keywords = (
        [kw if case_sensitive else kw.lower() for kw in expected_keywords]
    )

    matched = [kw for kw in keywords if kw in compare]
    missing = [kw for kw in keywords if kw not in compare]

    if len(matched) == len(keywords) and len(keywords) > 0:
        result = "correct"
        feedback = "All expected keywords matched."
    elif len(matched) == 0:
        result = "incorrect"
        feedback = (
            f"None of the expected keywords were found. "
            f"Expected concepts: {', '.join(keywords)}."
        )
    else:
        result = "partially_correct"
        feedback = (
            f"Partial match: found {matched} but missing {missing}."
        )

    return {
        "result": result,
        "matched": matched,
        "missing": missing,
        "feedback": feedback,
    }


# ── mastery update ───────────────────────────────────────────────────────────

def update_mastery(
    learner_state: dict[str, Any],
    concept_id: str,
    result: str,
    *,
    learning_rate: float = DEFAULT_LEARNING_RATE,
) -> float:
    """Update the mastery score for a concept based on an evaluation result.

    Uses an exponential-moving-average formula::

        new = old + learning_rate * (target - old)

    Where *target* depends on *result*:

    * ``"correct"`` → 1.0
    * ``"partially_correct"`` → 0.7
    * ``"incorrect"`` → 0.0

    Parameters
    ----------
    learner_state : dict
        The full learner state (mutated in-place).
    concept_id : str
        The knowledge point ID to update.
    result : str
        One of ``"correct"``, ``"partially_correct"``, ``"incorrect"``.
    learning_rate : float
        How aggressively the score shifts (default 0.15).

    Returns
    -------
    float
        The new mastery score (clamped to [0.0, 1.0]).
    """
    if result not in VALID_RESULTS:
        raise ValueError(
            f"Invalid evaluation result: {result!r}. "
            f"Must be one of {sorted(VALID_RESULTS)}."
        )

    mastery = learner_state.setdefault("mastery", {})
    old_score = float(mastery.get(concept_id, 0.0))

    target = RESULT_TARGET[result]
    new_score = old_score + learning_rate * (target - old_score)

    # Clamp to [0.0, 1.0]
    new_score = max(0.0, min(1.0, new_score))

    mastery[concept_id] = new_score
    return new_score


# ── evidence & misconception recording ───────────────────────────────────────

def record_learning_evidence(
    learner_state: dict[str, Any],
    concept_id: str,
    activity_id: str,
    result: str,
    note: str = "",
) -> None:
    """Append a learning-evidence entry to the learner state.

    Parameters
    ----------
    learner_state : dict
        The full learner state (mutated in-place).
    concept_id : str
        The knowledge point ID the activity covers.
    activity_id : str
        A short identifier for the activity (e.g. ``"quiz_001"``).
    result : str
        The evaluation result (``"correct"``, ``"partially_correct"``, or
        ``"incorrect"``).
    note : str
        Optional human-readable note about the interaction.
    """
    evidence = learner_state.setdefault("learning_evidence", [])
    evidence.append(
        {
            "concept_id": concept_id,
            "activity_id": activity_id,
            "result": result,
            "note": note,
        }
    )


def add_misconception(
    learner_state: dict[str, Any],
    concept_id: str,
    description: str,
) -> None:
    """Record a detected misconception for a concept.

    Parameters
    ----------
    learner_state : dict
        The full learner state (mutated in-place).
    concept_id : str
        The knowledge point ID the misconception relates to.
    description : str
        A description of the misconception.
    """
    misconceptions = learner_state.setdefault("misconceptions", [])
    misconceptions.append(
        {
            "concept_id": concept_id,
            "description": description,
        }
    )


# ── full assessment pipeline ─────────────────────────────────────────────────

def assess_answer(
    learner_state: dict[str, Any],
    concept_id: str,
    student_answer: str,
    expected_keywords: list[str] | None = None,
    *,
    activity_id: str = "",
    learning_rate: float = DEFAULT_LEARNING_RATE,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Run the full assessment pipeline for a student answer.

    1. Evaluate the answer against expected keywords.
    2. Update the mastery score for *concept_id*.
    3. Record the interaction as learning evidence.

    Parameters
    ----------
    learner_state : dict
        The full learner state (mutated in-place).
    concept_id : str
        The knowledge point ID being assessed.
    student_answer : str
        The free-text answer provided by the student.
    expected_keywords : list[str] or None
        Keywords expected in a correct answer.
    activity_id : str
        Identifier for the activity (used in learning evidence).
    learning_rate : float
        Passed through to :func:`update_mastery`.
    case_sensitive : bool
        Passed through to :func:`evaluate_answer`.

    Returns
    -------
    dict
        {"evaluation": ..., "old_mastery": float, "new_mastery": float,
         "concept_id": str}
    """
    evaluation = evaluate_answer(
        student_answer,
        expected_keywords,
        case_sensitive=case_sensitive,
    )

    old_mastery = float(
        learner_state.get("mastery", {}).get(concept_id, 0.0)
    )

    result = evaluation["result"]

    if result in VALID_RESULTS:
        new_mastery = update_mastery(
            learner_state, concept_id, result, learning_rate=learning_rate
        )
    else:
        # "unknown" — cannot evaluate, leave mastery unchanged
        new_mastery = old_mastery

    record_learning_evidence(
        learner_state,
        concept_id,
        activity_id or "unnamed_activity",
        result,
        note=evaluation["feedback"],
    )

    return {
        "concept_id": concept_id,
        "evaluation": evaluation,
        "old_mastery": old_mastery,
        "new_mastery": new_mastery,
    }
