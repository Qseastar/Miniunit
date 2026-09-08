from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from introai_tutor.assessment import validate_structured_assessment
from introai_tutor.diagnostic_feedback import validate_teaching_support
from introai_tutor.knowledge import validate_knowledge_points


REQUIRED_QUESTION_FIELDS = {
    "id",
    "concept_ids",
    "question_text",
    "expected_answer",
    "rubric",
    "difficulty",
}

ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}


class DiagnosticQuestionValidationError(ValueError):
    """Raised when diagnostic question data is invalid."""


def load_diagnostic_questions(
    path: str | Path,
    knowledge_data: dict[str, Any],
) -> dict[str, Any]:
    """Load and validate diagnostic questions from a JSON file."""
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8") as f:
        question_data = json.load(f)

    validate_diagnostic_questions(question_data, knowledge_data)
    return question_data


def validate_diagnostic_questions(
    question_data: dict[str, Any],
    knowledge_data: dict[str, Any],
) -> None:
    """Validate diagnostic questions against the knowledge point schema."""
    validate_knowledge_points(knowledge_data)

    if not isinstance(question_data, dict):
        raise DiagnosticQuestionValidationError("Question data must be an object.")

    questions = question_data.get("diagnostic_questions")
    if not isinstance(questions, list) or not questions:
        raise DiagnosticQuestionValidationError(
            "'diagnostic_questions' must be a non-empty list."
        )

    concept_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
    question_ids: set[str] = set()

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise DiagnosticQuestionValidationError(
                f"Diagnostic question at index {index} must be an object."
            )

        missing_fields = REQUIRED_QUESTION_FIELDS - set(question.keys())
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise DiagnosticQuestionValidationError(
                f"Diagnostic question at index {index} is missing required fields: {missing}"
            )

        question_id = question["id"]
        if not isinstance(question_id, str) or not question_id.strip():
            raise DiagnosticQuestionValidationError(
                f"Diagnostic question at index {index} has invalid id."
            )

        if question_id in question_ids:
            raise DiagnosticQuestionValidationError(f"Duplicate diagnostic question id: {question_id}")

        question_ids.add(question_id)

        _validate_non_empty_string(question, "question_text", question_id)
        _validate_non_empty_string(question, "expected_answer", question_id)
        _validate_non_empty_string(question, "rubric", question_id)
        _validate_concept_ids(question, concept_ids, question_id)
        _validate_difficulty(question, question_id)
        if "assessment" in question:
            try:
                validate_structured_assessment(question["assessment"])
            except ValueError as error:
                raise DiagnosticQuestionValidationError(
                    f"Diagnostic question '{question_id}' has invalid assessment: {error}"
                ) from None
        if "teaching_support" in question:
            try:
                validate_teaching_support(question["teaching_support"])
            except ValueError as error:
                raise DiagnosticQuestionValidationError(
                    f"Diagnostic question '{question_id}' has invalid teaching_support: {error}"
                ) from None


def _validate_non_empty_string(
    question: dict[str, Any],
    field_name: str,
    question_id: str,
) -> None:
    value = question[field_name]
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticQuestionValidationError(
            f"Diagnostic question '{question_id}' has invalid {field_name}."
        )


def _validate_concept_ids(
    question: dict[str, Any],
    valid_concept_ids: set[str],
    question_id: str,
) -> None:
    concept_ids = question["concept_ids"]
    if not isinstance(concept_ids, list) or not concept_ids:
        raise DiagnosticQuestionValidationError(
            f"Diagnostic question '{question_id}' must have a non-empty concept_ids list."
        )

    for concept_id in concept_ids:
        if not isinstance(concept_id, str) or not concept_id.strip():
            raise DiagnosticQuestionValidationError(
                f"Diagnostic question '{question_id}' has invalid concept id."
            )

        if concept_id not in valid_concept_ids:
            raise DiagnosticQuestionValidationError(
                f"Diagnostic question '{question_id}' has unknown concept id: {concept_id}"
            )


def _validate_difficulty(question: dict[str, Any], question_id: str) -> None:
    difficulty = question["difficulty"]
    if difficulty not in ALLOWED_DIFFICULTIES:
        allowed = ", ".join(sorted(ALLOWED_DIFFICULTIES))
        raise DiagnosticQuestionValidationError(
            f"Diagnostic question '{question_id}' has invalid difficulty. Expected one of: {allowed}"
        )
