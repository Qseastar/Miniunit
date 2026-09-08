from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from introai_tutor.knowledge import validate_knowledge_points


REQUIRED_LEARNER_FIELDS = {
    "student_id",
    "course_id",
    "mastery",
    "learning_evidence",
    "preferred_style",
}


class LearnerStateValidationError(ValueError):
    """Raised when the learner state file is invalid."""


def load_learner_state(path: str | Path, knowledge_data: dict[str, Any]) -> dict[str, Any]:
    """Load and validate learner state from a JSON file."""
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8") as f:
        learner_state = json.load(f)

    validate_learner_state(learner_state, knowledge_data)
    return learner_state


def validate_learner_state(
    learner_state: dict[str, Any],
    knowledge_data: dict[str, Any],
) -> None:
    """Validate learner state against the knowledge point schema."""
    validate_knowledge_points(knowledge_data)

    if not isinstance(learner_state, dict):
        raise LearnerStateValidationError("Learner state must be an object.")

    missing_fields = REQUIRED_LEARNER_FIELDS - set(learner_state.keys())
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise LearnerStateValidationError(f"Learner state is missing required fields: {missing}")

    student_id = learner_state["student_id"]
    if not isinstance(student_id, str) or not student_id.strip():
        raise LearnerStateValidationError("'student_id' must be a non-empty string.")

    mastery = learner_state["mastery"]
    if not isinstance(mastery, dict):
        raise LearnerStateValidationError("'mastery' must be a dictionary.")

    concept_ids = {point["id"] for point in knowledge_data["knowledge_points"]}

    for concept_id, score in mastery.items():
        if concept_id not in concept_ids:
            raise LearnerStateValidationError(f"Unknown mastery concept id: {concept_id}")

        if isinstance(score, bool) or not isinstance(score, int | float):
            raise LearnerStateValidationError(
                f"Mastery score for '{concept_id}' must be a number."
            )

        if not math.isfinite(float(score)) or score < 0 or score > 1:
            raise LearnerStateValidationError(
                f"Mastery score for '{concept_id}' must be between 0 and 1."
            )

    misconceptions = learner_state.get("misconceptions", [])
    if not isinstance(misconceptions, list):
        raise LearnerStateValidationError("'misconceptions' must be a list.")

    for index, misconception in enumerate(misconceptions):
        if isinstance(misconception, str):
            if misconception.strip():
                continue
            raise LearnerStateValidationError(
                f"Misconception at index {index} must be a non-empty string."
            )
        if not isinstance(misconception, dict):
            raise LearnerStateValidationError(
                f"Misconception at index {index} must be an object."
            )

        if "misconception_id" in misconception:
            misconception_id = misconception["misconception_id"]
            if not isinstance(misconception_id, str) or not misconception_id.strip():
                raise LearnerStateValidationError(
                    f"Misconception at index {index} has an invalid misconception_id."
                )
            continue

        concept_id = misconception.get("concept_id")
        if concept_id not in concept_ids:
            raise LearnerStateValidationError(
                f"Unknown misconception concept id: {concept_id}"
            )

    learning_evidence = learner_state["learning_evidence"]
    if not isinstance(learning_evidence, list):
        raise LearnerStateValidationError("'learning_evidence' must be a list.")


def get_mastery(learner_state: dict[str, Any], concept_id: str) -> float:
    """Return mastery score for a concept. Missing concepts default to 0.0."""
    mastery = learner_state.get("mastery", {})
    return float(mastery.get(concept_id, 0.0))
