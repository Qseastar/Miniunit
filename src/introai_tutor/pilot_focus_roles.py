"""Reviewed focus-role configuration for the six-person internal pilot."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from introai_tutor.pilot_tasks import ordered_tasks


FOCUS_ROLE_SCHEMA_VERSION = 1
PILOT_EXECUTION_RELEASE = "p4d"
_DOCUMENT_FIELDS = {"schema_version", "pilot_release", "roles"}
_ROLE_FIELDS = {
    "role_id",
    "title_zh",
    "focus",
    "required_core_task_ids",
    "observation_prompts",
    "expected_duration_minutes",
}
_ROLE_ID = re.compile(r"^role_[a-f]$")
_FORBIDDEN_TERMS = (
    "learner",
    "uuid",
    "answer",
    "template_id",
    "verify_",
    "api_key",
    "authorization",
    ".env",
    "/home/",
    "prompt",
)


class PilotFocusRoleError(ValueError):
    """Raised when focus-role configuration is malformed or unsafe."""


def load_focus_roles(
    path: str | Path,
    *,
    tasks_data: dict[str, Any],
) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PilotFocusRoleError("pilot focus-role configuration is missing.") from None
    except json.JSONDecodeError:
        raise PilotFocusRoleError("pilot focus-role configuration is not valid JSON.") from None
    validate_focus_roles(data, tasks_data=tasks_data)
    return deepcopy(data)


def validate_focus_roles(data: Any, *, tasks_data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or set(data) != _DOCUMENT_FIELDS:
        raise PilotFocusRoleError("pilot focus-role document has an invalid schema.")
    if data["schema_version"] != FOCUS_ROLE_SCHEMA_VERSION:
        raise PilotFocusRoleError("unsupported pilot focus-role schema_version.")
    if data["pilot_release"] != PILOT_EXECUTION_RELEASE:
        raise PilotFocusRoleError("pilot focus-role document has an invalid release.")
    valid_tasks = {task["task_id"] for task in ordered_tasks(tasks_data)}
    roles = data["roles"]
    if not isinstance(roles, list) or len(roles) != 6:
        raise PilotFocusRoleError("pilot focus-role document must contain six roles.")
    seen: set[str] = set()
    for index, role in enumerate(roles):
        if not isinstance(role, dict) or set(role) != _ROLE_FIELDS:
            raise PilotFocusRoleError(f"role at index {index} has an invalid schema.")
        role_id = role["role_id"]
        if not isinstance(role_id, str) or not _ROLE_ID.fullmatch(role_id) or role_id in seen:
            raise PilotFocusRoleError(f"role at index {index} has an invalid or duplicate role_id.")
        seen.add(role_id)
        _non_empty_text(role["title_zh"], "title_zh")
        _non_empty_text(role["focus"], "focus")
        prompts = role["observation_prompts"]
        if not isinstance(prompts, list) or not prompts or not all(
            isinstance(item, str) and item.strip() for item in prompts
        ):
            raise PilotFocusRoleError(f"role '{role_id}' observation_prompts is invalid.")
        task_ids = role["required_core_task_ids"]
        if (
            not isinstance(task_ids, list)
            or not task_ids
            or len(task_ids) != len(set(task_ids))
            or set(task_ids) != valid_tasks
            or any(not isinstance(item, str) or item not in valid_tasks for item in task_ids)
        ):
            raise PilotFocusRoleError(f"role '{role_id}' must require every core pilot task exactly once.")
        minutes = role["expected_duration_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
            raise PilotFocusRoleError(f"role '{role_id}' expected_duration_minutes is invalid.")
        _reject_sensitive_public_content(role, role_id)
    if seen != {f"role_{letter}" for letter in "abcdef"}:
        raise PilotFocusRoleError("focus roles must be role_a through role_f.")


def ordered_focus_roles(data: dict[str, Any], *, tasks_data: dict[str, Any]) -> list[dict[str, Any]]:
    validate_focus_roles(data, tasks_data=tasks_data)
    return sorted((deepcopy(role) for role in data["roles"]), key=lambda item: item["role_id"])


def _non_empty_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PilotFocusRoleError(f"focus role {field} must be non-empty text.")


def _reject_sensitive_public_content(role: dict[str, Any], role_id: str) -> None:
    # Field names are part of the reviewed schema (``observation_prompts`` is
    # intentionally required), so only inspect public values.  Checking the
    # serialized object would reject the schema's own field name ``prompt``.
    public_values = [
        value
        for key, value in role.items()
        if key not in {"role_id", "required_core_task_ids", "expected_duration_minutes"}
    ]
    public_text = json.dumps(public_values, ensure_ascii=False).casefold()
    if any(term in public_text for term in _FORBIDDEN_TERMS):
        raise PilotFocusRoleError(f"role '{role_id}' contains prohibited internal content.")
