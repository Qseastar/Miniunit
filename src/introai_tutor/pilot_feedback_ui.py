"""Transient, privacy-safe state for the internal-pilot feedback form."""

from __future__ import annotations

from collections.abc import Callable, Iterable, MutableMapping
import re
import secrets
from typing import Any

from introai_tutor.pilot_feedback import FREE_TEXT_FIELDS, RATING_FIELDS


ANONYMOUS_CODE_KEY = "introai_pilot_anonymous_code"
FORM_REVISION_KEY = "introai_pilot_form_revision"
PREPARED_PAYLOAD_KEY = "introai_pilot_prepared_feedback"
SERIALIZED_PAYLOAD_KEY = "introai_pilot_serialized_feedback_json"
DOWNLOAD_FILENAME_KEY = "introai_pilot_download_filename"
RESET_REQUEST_KEY = "introai_pilot_reset_requested"
RESET_FLASH_KEY = "introai_pilot_reset_flash"
FORM_WIDGET_PREFIX = "introai_pilot_form_"
RESET_BUTTON_KEY = "introai_pilot_reset_form"
LEGACY_TESTER_CODE_KEY = "introai_pilot_tester_code"
LEGACY_FORM_WIDGET_PREFIXES = (
    "introai_pilot_task_",
    "introai_pilot_rating_",
    "introai_pilot_feedback_",
)
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_PATTERN = re.compile(r"^G-[A-HJ-KM-NP-Z2-9]{6}$")


class PilotFeedbackUiError(ValueError):
    """Raised when transient pilot-form state has an invalid shape."""


def generate_anonymous_tester_code(
    *, chooser: Callable[[str], str] = secrets.choice
) -> str:
    """Generate a short non-identifying code without learner-derived input."""
    code = "G-" + "".join(chooser(_CODE_ALPHABET) for _ in range(6))
    validate_anonymous_tester_code(code)
    return code


def validate_anonymous_tester_code(value: Any) -> str:
    if not isinstance(value, str) or not _CODE_PATTERN.fullmatch(value):
        raise PilotFeedbackUiError("anonymous pilot code has an invalid format.")
    return value


def current_form_revision(session_state: MutableMapping[str, Any]) -> int:
    value = session_state.get(FORM_REVISION_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PilotFeedbackUiError("pilot form revision must be a non-negative integer.")
    return value


def ensure_anonymous_tester_code(
    session_state: MutableMapping[str, Any],
    *,
    chooser: Callable[[str], str] = secrets.choice,
) -> str:
    """Return one session-stable code, regenerating only absent/invalid state."""
    value = session_state.get(ANONYMOUS_CODE_KEY)
    if isinstance(value, str):
        try:
            return validate_anonymous_tester_code(value)
        except PilotFeedbackUiError:
            pass
    code = generate_anonymous_tester_code(chooser=chooser)
    session_state[ANONYMOUS_CODE_KEY] = code
    return code


def pilot_widget_inventory(
    *, task_ids: Iterable[str], revision: int
) -> dict[str, Any]:
    """Return all versioned pilot widget keys from one explicit inventory."""
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise PilotFeedbackUiError("pilot widget revision must be a non-negative integer.")
    normalized_task_ids = tuple(task_ids)
    if not normalized_task_ids or any(
        not isinstance(task_id, str) or not task_id for task_id in normalized_task_ids
    ):
        raise PilotFeedbackUiError("pilot widget inventory requires non-empty task IDs.")
    if len(normalized_task_ids) != len(set(normalized_task_ids)):
        raise PilotFeedbackUiError("pilot widget inventory task IDs must be unique.")
    prefix = f"{FORM_WIDGET_PREFIX}{revision}_"
    return {
        "tasks": {task_id: f"{prefix}task_{task_id}" for task_id in normalized_task_ids},
        "ratings": {rating_id: f"{prefix}rating_{rating_id}" for rating_id in RATING_FIELDS},
        "free_text": {field: f"{prefix}feedback_{field}" for field in FREE_TEXT_FIELDS},
        "form": f"{prefix}feedback_form",
        "download": f"{prefix}download_feedback",
        "reset": RESET_BUTTON_KEY,
    }


def reset_pilot_feedback_form(
    session_state: MutableMapping[str, Any],
    *,
    chooser: Callable[[str], str] = secrets.choice,
) -> str:
    """Clear only pilot transient state, then create a new form identity/code."""
    revision = current_form_revision(session_state)
    for key in list(session_state.keys()):
        if isinstance(key, str) and (
            key.startswith(FORM_WIDGET_PREFIX)
            or key.startswith(LEGACY_FORM_WIDGET_PREFIXES)
        ):
            session_state.pop(key, None)
    for key in (
        LEGACY_TESTER_CODE_KEY,
        ANONYMOUS_CODE_KEY,
        PREPARED_PAYLOAD_KEY,
        SERIALIZED_PAYLOAD_KEY,
        DOWNLOAD_FILENAME_KEY,
        RESET_REQUEST_KEY,
        RESET_FLASH_KEY,
    ):
        session_state.pop(key, None)
    session_state[FORM_REVISION_KEY] = revision + 1
    code = ensure_anonymous_tester_code(session_state, chooser=chooser)
    session_state[RESET_FLASH_KEY] = "反馈表已重置，已生成新的匿名测试编号。"
    return code


def consume_reset_flash(session_state: MutableMapping[str, Any]) -> str | None:
    value = session_state.pop(RESET_FLASH_KEY, None)
    return value if isinstance(value, str) and value else None
