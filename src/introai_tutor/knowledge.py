from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "id",
    "title_zh",
    "title_en",
    "module",
    "description",
    "prerequisites",
    "learning_objectives",
    "common_misconceptions",
    "mastery_criteria",
}


class KnowledgeValidationError(ValueError):
    """Raised when the knowledge points file is invalid."""


def load_knowledge_points(path: str | Path) -> dict[str, Any]:
    """Load knowledge points from a JSON file."""
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    validate_knowledge_points(data)
    return data


def validate_knowledge_points(data: dict[str, Any]) -> None:
    """Validate the structure and internal consistency of knowledge points."""
    if not isinstance(data, dict):
        raise KnowledgeValidationError("Top-level JSON value must be an object.")

    points = data.get("knowledge_points")

    if not isinstance(points, list) or not points:
        raise KnowledgeValidationError("'knowledge_points' must be a non-empty list.")

    ids: set[str] = set()

    for index, point in enumerate(points):
        if not isinstance(point, dict):
            raise KnowledgeValidationError(f"Knowledge point at index {index} must be an object.")

        missing_fields = REQUIRED_FIELDS - set(point.keys())
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise KnowledgeValidationError(
                f"Knowledge point at index {index} is missing required fields: {missing}"
            )

        point_id = point["id"]

        if not isinstance(point_id, str) or not point_id.strip():
            raise KnowledgeValidationError(f"Knowledge point at index {index} has invalid id.")

        if point_id in ids:
            raise KnowledgeValidationError(f"Duplicate knowledge point id: {point_id}")

        ids.add(point_id)

        prerequisites = point["prerequisites"]
        if not isinstance(prerequisites, list):
            raise KnowledgeValidationError(
                f"Knowledge point '{point_id}' has invalid prerequisites. Expected a list."
            )

    for point in points:
        point_id = point["id"]

        for prerequisite_id in point["prerequisites"]:
            if prerequisite_id not in ids:
                raise KnowledgeValidationError(
                    f"Knowledge point '{point_id}' has unknown prerequisite: {prerequisite_id}"
                )
            
def get_knowledge_point(data: dict[str, Any], point_id: str) -> dict[str, Any]:
    """Return a knowledge point by ID."""
    validate_knowledge_points(data)

    for point in data["knowledge_points"]:
        if point["id"] == point_id:
            return point

    raise KnowledgeValidationError(f"Unknown knowledge point id: {point_id}")


def get_prerequisite_ids(data: dict[str, Any], point_id: str) -> list[str]:
    """Return prerequisite IDs for a knowledge point."""
    point = get_knowledge_point(data, point_id)
    return list(point["prerequisites"])
