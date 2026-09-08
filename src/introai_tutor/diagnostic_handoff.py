"""Plan reviewed mastery-verification templates from validated QA topics.

This module intentionally creates neither a diagnostic session nor learner
evidence.  It is the deterministic handoff boundary between free-question
understanding and a learner's optional, later verification choice.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from introai_tutor.template_selection import (
    SUPPORTED_SCORERS,
    DiagnosticTemplateError,
)


PLAN_SCHEMA_VERSION = 1
DEFAULT_MAX_TEMPLATES = 2
MAX_TEMPLATES_LIMIT = 10
DEFAULT_INTENT = "diagnostic_request"
NO_TEMPLATE_MESSAGE = "当前没有与本问题对应的审核验证题，本次仅提供课程回答。"
OUT_OF_SCOPE_MESSAGE = "该问题不在当前课程范围内，暂不提供掌握度验证题。"
CLARIFICATION_MESSAGE = "当前问题仍需澄清，暂不提供掌握度验证题。"
MISSING_TOPICS_MESSAGE = "当前回答未提供可用于掌握度验证的课程知识点。"


class DiagnosticHandoffError(ValueError):
    """Raised when a diagnostic-plan request violates the public contract."""


class DiagnosticHandoffService:
    """Deterministically plan only reviewed verification templates.

    The injected selector remains the authority for the validated template
    bank and known concept IDs.  This service adds planning-specific limits,
    ranking, and a safe adapter for a real ``TutorService.ask()`` result.
    """

    def __init__(
        self,
        *,
        template_selection_service: Any,
        max_templates_limit: int = MAX_TEMPLATES_LIMIT,
    ) -> None:
        if not callable(getattr(template_selection_service, "select", None)):
            raise DiagnosticHandoffError(
                "template_selection_service must provide callable select()."
            )
        self._max_templates_limit = _positive_int(
            max_templates_limit, "max_templates_limit", maximum=MAX_TEMPLATES_LIMIT
        )
        self._selector = template_selection_service

    def plan(
        self,
        *,
        topic_ids: list[str],
        intent: str | None = None,
        max_templates: int = DEFAULT_MAX_TEMPLATES,
        question: str | None = None,
        exposed_template_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """Return a no-side-effect plan for optional reviewed verification."""
        normalized_topics = _normalize_topic_ids(topic_ids)
        normalized_intent = _normalize_intent(intent)
        limit = _positive_int(
            max_templates, "max_templates", maximum=self._max_templates_limit
        )
        normalized_question = _normalize_optional_question(question)
        exposed = _normalize_exposed_template_ids(exposed_template_ids)
        try:
            selection_kwargs = {
                "concept_ids": list(normalized_topics), "intent": normalized_intent
            }
            if exposed:
                selection_kwargs["exposed_template_ids"] = set(exposed)
            candidates = self._selector.select(**selection_kwargs)
        except DiagnosticTemplateError as error:
            raise DiagnosticHandoffError(f"Invalid diagnostic planning input: {error}") from None
        if not isinstance(candidates, list):
            raise DiagnosticHandoffError("template_selection_service must return a list.")

        requested = set(normalized_topics)
        eligible = [
            template
            for template in candidates
            if _is_eligible_template(template, requested)
            and _primary_concept_id(template) in requested
        ]
        # A verification template may update several concept records, but its
        # first concept is the reviewed primary capability slice. Select at
        # most one template per direct primary concept so a shared abstraction
        # (for example completeness/optimality) cannot pull in unrelated
        # algorithms by itself.
        best_by_primary: dict[str, dict[str, Any]] = {}
        for template in eligible:
            primary = _primary_concept_id(template)
            current = best_by_primary.get(primary)
            if current is None or _exposure_ranking_key(
                template, requested, normalized_question, exposed
            ) < _exposure_ranking_key(current, requested, normalized_question, exposed):
                best_by_primary[primary] = template
        ordered = sorted(
            best_by_primary.values(),
            key=lambda template: _exposure_ranking_key(
                template, requested, normalized_question, exposed
            ),
        )[:limit]
        template_ids = [template["id"] for template in ordered]
        matched_concept_ids = {
            template["id"]: [
                concept_id
                for concept_id in normalized_topics
                if concept_id in template["concept_ids"]
            ]
            for template in ordered
        }
        covered = {
            concept_id
            for concepts in matched_concept_ids.values()
            for concept_id in concepts
        }
        uncovered_topic_ids = [
            concept_id for concept_id in normalized_topics if concept_id not in covered
        ]
        available = bool(ordered)
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "purpose": "diagnostic_plan",
            "available": available,
            "source": "reviewed_template_bank",
            "topic_ids": list(normalized_topics),
            "planning_topic_ids": list(normalized_topics),
            "all_topic_ids": list(normalized_topics),
            "supporting_topic_ids": [],
            "planning_source": "explicit_topic_ids",
            "intent": normalized_intent,
            "template_ids": template_ids,
            "matched_concept_ids": matched_concept_ids,
            "uncovered_topic_ids": uncovered_topic_ids,
            "evidence_eligible": False,
            "evidence_policy": "mastery_verification_only",
            "message": (
                "已找到可由你主动启动的审核掌握度验证题。"
                if available
                else NO_TEMPLATE_MESSAGE
            ),
        }

    def plan_from_qa_result(
        self, *, qa_result: dict[str, Any], exposed_template_ids: set[str] | None = None
    ) -> dict[str, Any]:
        """Plan from the validated nested ``understanding`` in TutorService output.

        A free-question result that is out of scope, still needs clarification,
        or carries no usable topics is an ordinary unavailable plan.  It never
        triggers verification, state integration, or recommendation.
        """
        if not isinstance(qa_result, dict):
            raise DiagnosticHandoffError("qa_result must be an object.")
        # TutorService.ask() nests the validated object under
        # ``understanding``; QuestionUnderstandingService.understand() returns
        # that same object directly.  Accept both existing public shapes.
        understanding = qa_result.get("understanding", qa_result)
        if not isinstance(understanding, dict):
            return _unavailable_plan(message=MISSING_TOPICS_MESSAGE)
        topic_ids = understanding.get("topic_ids")
        has_diagnostic_roles = "diagnostic_topic_ids" in understanding
        has_supporting_roles = "supporting_topic_ids" in understanding
        if has_diagnostic_roles != has_supporting_roles:
            raise DiagnosticHandoffError(
                "diagnostic_topic_ids and supporting_topic_ids must be provided together."
            )
        if not has_diagnostic_roles:
            if not isinstance(topic_ids, list) or not topic_ids:
                if (
                    understanding.get("in_scope") is False
                    or understanding.get("intent") == "out_of_scope"
                ):
                    return _unavailable_plan(message=OUT_OF_SCOPE_MESSAGE)
                return _unavailable_plan(message=MISSING_TOPICS_MESSAGE)
            if understanding.get("in_scope") is False or understanding.get("intent") == "out_of_scope":
                return _unavailable_plan(message=OUT_OF_SCOPE_MESSAGE)
            if understanding.get("needs_clarification") is True:
                return _unavailable_plan(message=CLARIFICATION_MESSAGE)
            plan = self.plan(
                topic_ids=topic_ids,
                intent=understanding.get("intent"),
                question=qa_result.get("question"),
                exposed_template_ids=exposed_template_ids,
            )
            return _with_topic_roles(
                plan,
                all_topic_ids=plan["topic_ids"],
                planning_topic_ids=plan["topic_ids"],
                supporting_topic_ids=[],
                planning_source="legacy_topic_ids_fallback",
            )

        all_topics = _normalize_strict_role_ids(topic_ids, "topic_ids")
        diagnostic_topics = _normalize_strict_role_ids(
            understanding["diagnostic_topic_ids"], "diagnostic_topic_ids"
        )
        supporting_topics = _normalize_strict_role_ids(
            understanding["supporting_topic_ids"], "supporting_topic_ids"
        )
        _validate_topic_partition(
            all_topic_ids=all_topics,
            diagnostic_topic_ids=diagnostic_topics,
            supporting_topic_ids=supporting_topics,
        )
        intent = _normalize_intent(understanding.get("intent"))
        self._validate_known_topics(all_topics, intent=intent)
        if understanding.get("in_scope") is False or intent == "out_of_scope":
            if diagnostic_topics:
                raise DiagnosticHandoffError(
                    "out-of-scope QA results must not contain diagnostic_topic_ids."
                )
            return _unavailable_plan(
                message=OUT_OF_SCOPE_MESSAGE,
                all_topic_ids=all_topics,
                supporting_topic_ids=supporting_topics,
                planning_source="diagnostic_topic_ids",
            )
        if understanding.get("needs_clarification") is True:
            if diagnostic_topics:
                raise DiagnosticHandoffError(
                    "clarification QA results must not contain diagnostic_topic_ids."
                )
            return _unavailable_plan(
                message=CLARIFICATION_MESSAGE,
                all_topic_ids=all_topics,
                supporting_topic_ids=supporting_topics,
                planning_source="diagnostic_topic_ids",
            )
        if not diagnostic_topics:
            return _unavailable_plan(
                message=NO_TEMPLATE_MESSAGE,
                all_topic_ids=all_topics,
                supporting_topic_ids=supporting_topics,
                planning_source="diagnostic_topic_ids",
            )
        plan = self.plan(
            topic_ids=diagnostic_topics,
            intent=intent,
            question=qa_result.get("question"),
            exposed_template_ids=exposed_template_ids,
        )
        return _with_topic_roles(
            plan,
            all_topic_ids=all_topics,
            planning_topic_ids=diagnostic_topics,
            supporting_topic_ids=supporting_topics,
            planning_source="diagnostic_topic_ids",
        )

    def _validate_known_topics(self, topic_ids: list[str], *, intent: str) -> None:
        if not topic_ids:
            return
        try:
            self._selector.select(concept_ids=list(topic_ids), intent=intent)
        except DiagnosticTemplateError as error:
            raise DiagnosticHandoffError(
                f"Invalid diagnostic planning input: {error}"
            ) from None


def _normalize_topic_ids(topic_ids: Any) -> list[str]:
    if not isinstance(topic_ids, list) or not topic_ids:
        raise DiagnosticHandoffError("topic_ids must be a non-empty list of strings.")
    normalized: list[str] = []
    for index, concept_id in enumerate(topic_ids):
        if not isinstance(concept_id, str) or not (value := concept_id.strip()):
            raise DiagnosticHandoffError(
                f"topic_ids[{index}] must be a non-empty string."
            )
        if value not in normalized:
            normalized.append(value)
    return normalized


def _normalize_strict_role_ids(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise DiagnosticHandoffError(f"{field_name} must be a list of strings.")
    normalized: list[str] = []
    for index, concept_id in enumerate(value):
        if not isinstance(concept_id, str) or not (item := concept_id.strip()):
            raise DiagnosticHandoffError(
                f"{field_name}[{index}] must be a non-empty string."
            )
        if item in normalized:
            raise DiagnosticHandoffError(f"{field_name} must not contain duplicates.")
        normalized.append(item)
    return normalized


def _validate_topic_partition(
    *,
    all_topic_ids: list[str],
    diagnostic_topic_ids: list[str],
    supporting_topic_ids: list[str],
) -> None:
    all_topics = set(all_topic_ids)
    diagnostic_topics = set(diagnostic_topic_ids)
    supporting_topics = set(supporting_topic_ids)
    if not diagnostic_topics.issubset(all_topics):
        raise DiagnosticHandoffError("diagnostic_topic_ids must be a subset of topic_ids.")
    if not supporting_topics.issubset(all_topics):
        raise DiagnosticHandoffError("supporting_topic_ids must be a subset of topic_ids.")
    if diagnostic_topics.intersection(supporting_topics):
        raise DiagnosticHandoffError(
            "diagnostic_topic_ids and supporting_topic_ids must not overlap."
        )
    if diagnostic_topics.union(supporting_topics) != all_topics:
        raise DiagnosticHandoffError(
            "diagnostic and supporting topic roles must cover topic_ids."
        )


def _normalize_intent(intent: Any) -> str:
    if intent is None:
        return DEFAULT_INTENT
    if not isinstance(intent, str) or not (normalized := intent.strip()):
        raise DiagnosticHandoffError("intent must be null or a non-empty string.")
    return normalized


def _normalize_optional_question(question: Any) -> str:
    if question is None:
        return ""
    if not isinstance(question, str):
        raise DiagnosticHandoffError("question must be null or a string.")
    return question.strip()


def _normalize_exposed_template_ids(value: Any) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, set) or not all(
        isinstance(template_id, str) and template_id.strip() for template_id in value
    ):
        raise DiagnosticHandoffError("exposed_template_ids must be a set of non-empty strings.")
    return set(value)


def _positive_int(value: Any, name: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise DiagnosticHandoffError(f"{name} must be an integer between 1 and {maximum}.")
    return value


def _is_eligible_template(template: Any, requested: set[str]) -> bool:
    if not isinstance(template, dict):
        return False
    concept_ids = template.get("concept_ids")
    return (
        isinstance(template.get("id"), str)
        and bool(template["id"].strip())
        and template.get("review_status") == "human_verified"
        and template.get("purpose") == "mastery_verification"
        and template.get("deterministic_scorer") in SUPPORTED_SCORERS
        and isinstance(concept_ids, list)
        and bool(requested.intersection(concept_ids))
        and isinstance(template.get("selection_priority"), int)
        and not isinstance(template["selection_priority"], bool)
    )


def _primary_concept_id(template: dict[str, Any]) -> str:
    concept_ids = template.get("concept_ids")
    if not isinstance(concept_ids, list) or not concept_ids or not isinstance(concept_ids[0], str):
        raise DiagnosticHandoffError("eligible template must declare a primary concept.")
    return concept_ids[0]


def _ranking_key(
    template: dict[str, Any], requested: set[str], question: str
) -> tuple[int, int, float, int, str]:
    question_relevance = _question_relevance(template, question)
    matched_count = len(requested.intersection(template["concept_ids"]))
    coverage_ratio = matched_count / len(template["concept_ids"])
    return (
        -question_relevance,
        -matched_count,
        -coverage_ratio,
        -template["selection_priority"],
        template["id"],
    )


def _exposure_ranking_key(
    template: dict[str, Any], requested: set[str], question: str, exposed_template_ids: set[str]
) -> tuple[int, int, int, float, int, str]:
    """Keep existing ranking while deterministically preferring unseen forms."""
    return (
        int(template["id"] in exposed_template_ids),
        *_ranking_key(template, requested, question),
    )


def _question_relevance(template: dict[str, Any], question: str) -> int:
    """Prefer a reviewed capability whose student-facing prompt matches the ask.

    This is a deterministic, bounded tie-breaker. It neither scores a student
    answer nor inspects expected answers; it only compares the user's question
    to reviewed prompt wording when two templates share a primary concept.
    """
    if not question:
        return 0
    prompt = template.get("prompt")
    if not isinstance(prompt, str):
        return 0
    prompt_text = _normalize_match_text(prompt)
    question_text = _normalize_match_text(question)
    score = sum(1 for term in _question_terms(question) if term in prompt_text)
    # A direct value-computation request should prefer a reviewed prompt that
    # asks for that value, rather than a different prompt that happens to
    # reuse the same numeric example while asking for a frontier choice.
    if "多少" in question_text and "多少" in prompt_text:
        score += 3
    return score


def _question_terms(value: str) -> list[str]:
    normalized = _normalize_match_text(value)
    terms: list[str] = []
    for token in re.findall(r"[a-z0-9*()]+", normalized):
        if len(token) > 1 and token not in terms:
            terms.append(token)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    for index in range(len(chinese) - 1):
        token = chinese[index : index + 2]
        if token not in terms:
            terms.append(token)
    return terms


def _normalize_match_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _with_topic_roles(
    plan: dict[str, Any],
    *,
    all_topic_ids: list[str],
    planning_topic_ids: list[str],
    supporting_topic_ids: list[str],
    planning_source: str,
) -> dict[str, Any]:
    result = dict(plan)
    result["topic_ids"] = list(planning_topic_ids)
    result["planning_topic_ids"] = list(planning_topic_ids)
    result["all_topic_ids"] = list(all_topic_ids)
    result["supporting_topic_ids"] = list(supporting_topic_ids)
    result["planning_source"] = planning_source
    return result


def _unavailable_plan(
    *,
    message: str,
    all_topic_ids: list[str] | None = None,
    supporting_topic_ids: list[str] | None = None,
    planning_source: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "purpose": "diagnostic_plan",
        "available": False,
        "source": "reviewed_template_bank",
        "topic_ids": [],
        "planning_topic_ids": [],
        "all_topic_ids": list(all_topic_ids or []),
        "supporting_topic_ids": list(supporting_topic_ids or []),
        "planning_source": planning_source,
        "intent": None,
        "template_ids": [],
        "matched_concept_ids": {},
        "uncovered_topic_ids": [],
        "evidence_eligible": False,
        "evidence_policy": "mastery_verification_only",
        "message": message,
    }
