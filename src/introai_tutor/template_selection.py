"""Validated, deterministic selection of reviewed mastery-verification templates."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any


SCORER_QUESTION_TYPES = {
    "single_choice_v1": "single_choice",
    "multiple_choice_v1": "multiple_choice",
    "numeric_answer_v1": "numeric_answer",
    "ordering_v1": "ordering",
}
SUPPORTED_SCORERS = set(SCORER_QUESTION_TYPES)
SUPPORTED_QUESTION_TYPES = set(SCORER_QUESTION_TYPES.values())
REQUIRED_TEMPLATE_FIELDS = {
    "id", "schema_version", "review_status", "purpose", "concept_ids",
    "eligible_intents", "selection_priority", "question_type", "prompt",
    "choices", "expected_answer", "deterministic_scorer", "misconception_rules",
    "teaching_support", "benchmark_case_ids",
}


class DiagnosticTemplateError(ValueError):
    """Raised when reviewed diagnostic template data or selection is invalid."""


def load_diagnostic_templates(
    path: str | Path,
    *,
    valid_concept_ids: set[str] | list[str] | tuple[str, ...],
    valid_misconception_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Load and strictly validate the versioned reviewed-template document."""
    with Path(path).open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    validate_diagnostic_templates(
        data,
        valid_concept_ids=valid_concept_ids,
        valid_misconception_ids=valid_misconception_ids,
    )
    return deepcopy(data)


def validate_diagnostic_templates(
    data: Any,
    *,
    valid_concept_ids: set[str] | list[str] | tuple[str, ...],
    valid_misconception_ids: set[str] | list[str] | tuple[str, ...] | None = None,
    allowed_review_statuses: set[str] | list[str] | tuple[str, ...] = (
        "human_verified",
    ),
) -> None:
    """Validate only human-reviewed, deterministic mastery templates."""
    concepts = _string_set(valid_concept_ids, "valid_concept_ids")
    review_statuses = _string_set(
        allowed_review_statuses, "allowed_review_statuses"
    )
    misconceptions = None if valid_misconception_ids is None else _string_set(
        valid_misconception_ids, "valid_misconception_ids"
    )
    if not isinstance(data, dict) or set(data) != {"schema_version", "templates"}:
        raise DiagnosticTemplateError(
            "Template data must contain exactly schema_version and templates."
        )
    if data["schema_version"] != 1:
        raise DiagnosticTemplateError("Unsupported template schema_version.")
    templates = data["templates"]
    if not isinstance(templates, list) or not templates:
        raise DiagnosticTemplateError("templates must be a non-empty list.")
    ids: set[str] = set()
    for index, template in enumerate(templates):
        location = f"template at index {index}"
        if not isinstance(template, dict) or set(template) != REQUIRED_TEMPLATE_FIELDS:
            raise DiagnosticTemplateError(f"{location} has an invalid schema.")
        template_id = _text(template["id"], f"{location}.id")
        if template_id in ids:
            raise DiagnosticTemplateError(f"Duplicate template id: {template_id}")
        ids.add(template_id)
        if template["schema_version"] != 1:
            raise DiagnosticTemplateError(f"Template '{template_id}' has unsupported schema_version.")
        if template["review_status"] not in review_statuses:
            if review_statuses == {"human_verified"}:
                raise DiagnosticTemplateError(
                    f"Template '{template_id}' must be human_verified."
                )
            raise DiagnosticTemplateError(
                f"Template '{template_id}' has an invalid review_status."
            )
        if template["purpose"] != "mastery_verification":
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid purpose.")
        _validate_concepts(template["concept_ids"], concepts, template_id)
        intents = template["eligible_intents"]
        if not isinstance(intents, list) or not intents or len(intents) != len(set(intents)):
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid eligible_intents.")
        for intent in intents:
            _text(intent, f"Template '{template_id}' eligible intent")
        priority = template["selection_priority"]
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid selection_priority.")
        question_type = template["question_type"]
        scorer_name = template["deterministic_scorer"]
        if question_type not in SUPPORTED_QUESTION_TYPES:
            raise DiagnosticTemplateError(f"Template '{template_id}' has unsupported question_type.")
        if scorer_name not in SUPPORTED_SCORERS:
            raise DiagnosticTemplateError(f"Template '{template_id}' has unsupported deterministic_scorer.")
        if SCORER_QUESTION_TYPES[scorer_name] != question_type:
            raise DiagnosticTemplateError(
                f"Template '{template_id}' has mismatched question_type and deterministic_scorer."
            )
        _text(template["prompt"], f"Template '{template_id}' prompt")
        if scorer_name == "numeric_answer_v1":
            if template["choices"] != []:
                raise DiagnosticTemplateError(
                    f"Template '{template_id}' numeric_answer choices must be empty."
                )
            _validate_numeric_expected_answer(template["expected_answer"], template_id)
            _validate_empty_misconception_rules(
                template["misconception_rules"], template_id
            )
        else:
            choice_ids = _validate_choices(template["choices"], template_id)
            _validate_choice_expected_answer(
                template["expected_answer"],
                scorer_name=scorer_name,
                choice_ids=choice_ids,
                template_id=template_id,
            )
            if scorer_name == "single_choice_v1":
                _validate_misconception_rules(
                    template["misconception_rules"],
                    choice_ids,
                    misconceptions,
                    template_id,
                )
            else:
                _validate_empty_misconception_rules(
                    template["misconception_rules"], template_id
                )
        support = template["teaching_support"]
        if not isinstance(support, dict) or set(support) != {"hint", "explanation"}:
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid teaching_support.")
        _text(support["hint"], f"Template '{template_id}' teaching_support.hint")
        _text(support["explanation"], f"Template '{template_id}' teaching_support.explanation")
        benchmark_ids = template["benchmark_case_ids"]
        if not isinstance(benchmark_ids, list) or not benchmark_ids or len(benchmark_ids) != len(set(benchmark_ids)):
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid benchmark_case_ids.")
        for case_id in benchmark_ids:
            _text(case_id, f"Template '{template_id}' benchmark_case_id")


class TemplateSelectionService:
    """Choose reviewed templates in stable Python-controlled order."""

    def __init__(
        self,
        *,
        templates_data: dict[str, Any],
        valid_concept_ids: set[str] | list[str] | tuple[str, ...],
        valid_misconception_ids: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> None:
        validate_diagnostic_templates(
            templates_data,
            valid_concept_ids=valid_concept_ids,
            valid_misconception_ids=valid_misconception_ids,
        )
        self._valid_concept_ids = _string_set(valid_concept_ids, "valid_concept_ids")
        self._templates = deepcopy(templates_data["templates"])

    def select(
        self,
        *,
        concept_ids: list[str],
        intent: str,
        exposed_template_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return reviewed templates matching the requested concepts and intent."""
        if not isinstance(concept_ids, list) or not concept_ids:
            raise DiagnosticTemplateError("concept_ids must be a non-empty list.")
        if len(concept_ids) != len(set(concept_ids)):
            raise DiagnosticTemplateError("concept_ids must not contain duplicates.")
        requested = set()
        for concept_id in concept_ids:
            _text(concept_id, "concept_id")
            if concept_id not in self._valid_concept_ids:
                raise DiagnosticTemplateError(f"Unknown concept id: {concept_id}")
            requested.add(concept_id)
        _text(intent, "intent")
        if exposed_template_ids is not None:
            if not isinstance(exposed_template_ids, set) or not all(
                isinstance(template_id, str) and template_id in {item["id"] for item in self._templates}
                for template_id in exposed_template_ids
            ):
                raise DiagnosticTemplateError("exposed_template_ids must contain known template IDs.")
        selected = [
            template for template in self._templates
            if intent in template["eligible_intents"]
            and requested.intersection(template["concept_ids"])
        ]
        exposed = exposed_template_ids or set()
        return deepcopy(sorted(
            selected,
            key=lambda item: (item["id"] in exposed, -item["selection_priority"], item["id"]),
        ))


def _string_set(value: Any, name: str) -> set[str]:
    if not isinstance(value, set | list | tuple) or not value:
        raise DiagnosticTemplateError(f"{name} must be a non-empty set, list, or tuple.")
    result = set()
    for item in value:
        result.add(_text(item, name))
    return result


def _text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticTemplateError(f"{location} must be a non-empty string.")
    return value


def _validate_concepts(values: Any, concepts: set[str], template_id: str) -> None:
    if not isinstance(values, list) or not values or len(values) != len(set(values)):
        raise DiagnosticTemplateError(f"Template '{template_id}' has invalid concept_ids.")
    for concept_id in values:
        _text(concept_id, f"Template '{template_id}' concept_id")
        if concept_id not in concepts:
            raise DiagnosticTemplateError(f"Template '{template_id}' has unknown concept id: {concept_id}")


def _validate_choices(values: Any, template_id: str) -> set[str]:
    if not isinstance(values, list) or len(values) < 2:
        raise DiagnosticTemplateError(f"Template '{template_id}' must have at least two choices.")
    choice_ids: set[str] = set()
    for choice in values:
        if not isinstance(choice, dict) or set(choice) != {"id", "text"}:
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid choice schema.")
        choice_id = _text(choice["id"], f"Template '{template_id}' choice id")
        _text(choice["text"], f"Template '{template_id}' choice text")
        if choice_id in choice_ids:
            raise DiagnosticTemplateError(f"Template '{template_id}' has duplicate choice id: {choice_id}")
        choice_ids.add(choice_id)
    return choice_ids


def _validate_choice_expected_answer(
    answer: Any,
    *,
    scorer_name: str,
    choice_ids: set[str],
    template_id: str,
) -> None:
    if scorer_name == "single_choice_v1":
        valid = (
            isinstance(answer, dict)
            and set(answer) == {"choice_id"}
            and answer["choice_id"] in choice_ids
        )
    elif scorer_name == "multiple_choice_v1":
        valid = (
            isinstance(answer, dict)
            and set(answer) == {"choice_ids"}
            and _valid_unique_known_ids(answer["choice_ids"], choice_ids)
        )
    elif scorer_name == "ordering_v1":
        ordered_ids = (
            answer.get("ordered_choice_ids") if isinstance(answer, dict) else None
        )
        valid = (
            isinstance(answer, dict)
            and set(answer) == {"ordered_choice_ids"}
            and _valid_unique_known_ids(ordered_ids, choice_ids)
        )
    else:  # pragma: no cover - caller is guarded by the scorer registry
        valid = False
    if not valid:
        raise DiagnosticTemplateError(
            f"Template '{template_id}' has invalid expected_answer."
        )


def _valid_unique_known_ids(values: Any, valid_ids: set[str]) -> bool:
    return (
        isinstance(values, list)
        and bool(values)
        and all(isinstance(item, str) and item in valid_ids for item in values)
        and len(values) == len(set(values))
    )


def _validate_numeric_expected_answer(answer: Any, template_id: str) -> None:
    if not isinstance(answer, dict) or set(answer) not in (
        {"value"},
        {"value", "absolute_tolerance"},
    ):
        raise DiagnosticTemplateError(
            f"Template '{template_id}' has invalid expected_answer."
        )
    if not _finite_json_number(answer["value"]):
        raise DiagnosticTemplateError(
            f"Template '{template_id}' has invalid numeric expected value."
        )
    tolerance = answer.get("absolute_tolerance", 0)
    if not _finite_json_number(tolerance) or tolerance < 0:
        raise DiagnosticTemplateError(
            f"Template '{template_id}' has invalid absolute_tolerance."
        )


def _finite_json_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return isinstance(value, int) or math.isfinite(value)


def _validate_empty_misconception_rules(rules: Any, template_id: str) -> None:
    if rules != []:
        raise DiagnosticTemplateError(
            f"Template '{template_id}' scorer requires empty misconception_rules."
        )


def _validate_misconception_rules(
    rules: Any, choice_ids: set[str], valid_ids: set[str] | None, template_id: str
) -> None:
    if not isinstance(rules, list):
        raise DiagnosticTemplateError(f"Template '{template_id}' misconception_rules must be a list.")
    choices_seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"choice_id", "misconception_id"}:
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid misconception rule.")
        choice_id = rule["choice_id"]
        misconception_id = _text(rule["misconception_id"], f"Template '{template_id}' misconception_id")
        if choice_id not in choice_ids or choice_id in choices_seen:
            raise DiagnosticTemplateError(f"Template '{template_id}' has invalid misconception choice.")
        if valid_ids is not None and misconception_id not in valid_ids:
            raise DiagnosticTemplateError(f"Template '{template_id}' has unknown misconception id: {misconception_id}")
        choices_seen.add(choice_id)
