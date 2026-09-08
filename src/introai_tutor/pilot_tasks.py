"""Strict versioned task-list loading for the internal pilot."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any


TASK_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = {"schema_version", "pilot_name", "tasks"}
_TASK_FIELDS = {
    "task_id",
    "order",
    "title_zh",
    "instructions_zh",
    "observations_zh",
    "estimated_minutes",
}
_TASK_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class PilotTaskError(ValueError):
    """Raised when the fixed pilot task document is invalid."""


def load_pilot_tasks(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    validate_pilot_tasks(data)
    return deepcopy(data)


def validate_pilot_tasks(data: Any) -> None:
    if not isinstance(data, dict) or set(data) != _DOCUMENT_FIELDS:
        raise PilotTaskError("pilot task document has an invalid schema.")
    if data["schema_version"] != TASK_SCHEMA_VERSION:
        raise PilotTaskError("pilot task document has an unsupported schema_version.")
    _text(data["pilot_name"], "pilot_name")
    tasks = data["tasks"]
    if not isinstance(tasks, list) or len(tasks) != 6:
        raise PilotTaskError("pilot task document must contain exactly six tasks.")
    ids: set[str] = set()
    orders: set[int] = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict) or set(task) != _TASK_FIELDS:
            raise PilotTaskError(f"task at index {index} has an invalid schema.")
        task_id = task["task_id"]
        if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
            raise PilotTaskError(f"task at index {index} has an invalid task_id.")
        if task_id in ids:
            raise PilotTaskError(f"duplicate pilot task id: {task_id}")
        ids.add(task_id)
        order = task["order"]
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise PilotTaskError(f"task '{task_id}' has an invalid order.")
        if order in orders:
            raise PilotTaskError(f"duplicate pilot task order: {order}")
        orders.add(order)
        for field in ("title_zh", "instructions_zh", "observations_zh"):
            _text(task[field], f"task '{task_id}' {field}")
        minutes = task["estimated_minutes"]
        if minutes is not None and (
            isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1
        ):
            raise PilotTaskError(f"task '{task_id}' has invalid estimated_minutes.")
        _reject_internal_content(task, task_id)
    if orders != set(range(1, len(tasks) + 1)):
        raise PilotTaskError("pilot task orders must be consecutive from one.")


def ordered_tasks(data: dict[str, Any]) -> list[dict[str, Any]]:
    validate_pilot_tasks(data)
    return sorted((deepcopy(item) for item in data["tasks"]), key=lambda item: item["order"])


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PilotTaskError(f"{name} must be non-empty text.")
    return value.strip()


def _reject_internal_content(task: dict[str, Any], task_id: str) -> None:
    public_text = " ".join(
        str(task[field]) for field in ("title_zh", "instructions_zh", "observations_zh")
    ).casefold()
    if "verify_" in public_text or "_v1" in public_text or "expected_answer" in public_text:
        raise PilotTaskError(f"task '{task_id}' exposes internal template content.")
