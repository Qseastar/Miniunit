"""Privacy-minimal, download-only feedback payloads for the internal pilot."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import re
from typing import Any

from introai_tutor.pilot_tasks import ordered_tasks


FEEDBACK_SCHEMA_VERSION = 1
PILOT_NAME = "introai_search_algorithms_internal"
# New remote-pilot exports identify the actual delivery release.  P4a payloads
# were already downloaded before this correction and remain valid history.
PILOT_RELEASE = "p4d"
SUPPORTED_PILOT_RELEASES = frozenset({"p4a", PILOT_RELEASE})
RATING_FIELDS = {
    "qa_clarity": "自由问答内容清晰度",
    "citation_helpfulness": "课件来源与引用的帮助程度",
    "diagnostic_relevance": "审核诊断题与原问题的相关性",
    "diagnostic_feedback_clarity": "诊断反馈是否容易理解",
    "mastery_map_helpfulness": "知识掌握图谱是否帮助理解课程结构",
    "navigation_naturalness": "页面导航是否自然",
    "learning_record_trust": "对掌握度与学习记录的信任程度",
    "overall_intent_to_use": "整体使用意愿",
}
FREE_TEXT_FIELDS = {
    "most_helpful": "你认为最有帮助的功能是什么？",
    "most_confusing": "哪一步最困惑、最不自然或最容易卡住？",
    "errors_encountered": "你遇到了什么错误或异常？",
    "improvement_request": "你最希望增加或改进什么？",
    "other": "其他补充",
}
_PAYLOAD_FIELDS = {
    "schema_version",
    "pilot_name",
    "pilot_release",
    "tester_code",
    "completed_task_ids",
    "ratings",
    "free_text_feedback",
    "generated_at_utc",
}
_TESTER_CODE = re.compile(r"^[A-Za-z0-9_-]{2,32}$")
_MAX_FREE_TEXT_LENGTH = 2000
_FORBIDDEN_KEYS = frozenset(
    {
        "learner",
        "learner_id",
        "learner_uuid",
        "learner_url",
        "mastery",
        "recommendation",
        "evidence",
        "evidence_events",
        "exposure",
        "exposure_history",
        "question",
        "answer",
        "student_answer",
        "model_answer",
        "prompt",
        "chunk",
        "course_chunk",
        "diagnostic_question",
        "choice",
        "choices",
        "hint",
        "reveal",
        "api_key",
        "authorization",
        "database_path",
        "user_agent",
        "ip_address",
        "local_path",
        "github_token",
        "remote_url",
    }
)


class PilotFeedbackError(ValueError):
    """Raised when internal-pilot feedback cannot safely be exported."""


def build_feedback_payload(
    *,
    tasks_data: dict[str, Any],
    tester_code: str | None,
    completed_task_ids: list[str],
    ratings: dict[str, Any],
    free_text_feedback: dict[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build and validate one minimal download payload without persistence."""
    task_ids = {item["task_id"] for item in ordered_tasks(tasks_data)}
    payload = {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "pilot_name": PILOT_NAME,
        "pilot_release": PILOT_RELEASE,
        "tester_code": _normalize_tester_code(tester_code),
        "completed_task_ids": _completed_ids(completed_task_ids, task_ids),
        "ratings": _ratings(ratings),
        "free_text_feedback": _free_text(free_text_feedback or {}),
        "generated_at_utc": generated_at_utc or _utc_now(),
    }
    validate_feedback_payload(payload, valid_task_ids=task_ids)
    return payload


def validate_feedback_payload(payload: Any, *, valid_task_ids: set[str]) -> None:
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS:
        raise PilotFeedbackError("feedback payload has an invalid schema.")
    _reject_forbidden_keys(payload)
    if payload["schema_version"] != FEEDBACK_SCHEMA_VERSION:
        raise PilotFeedbackError("feedback payload has an unsupported schema_version.")
    if payload["pilot_name"] != PILOT_NAME:
        raise PilotFeedbackError("feedback payload has an invalid pilot identity.")
    if payload["pilot_release"] not in SUPPORTED_PILOT_RELEASES:
        raise PilotFeedbackError("feedback payload has an unsupported pilot_release.")
    _normalize_tester_code(payload["tester_code"])
    _completed_ids(payload["completed_task_ids"], valid_task_ids)
    _ratings(payload["ratings"])
    _free_text(payload["free_text_feedback"])
    _timestamp(payload["generated_at_utc"])


def payload_json(payload: dict[str, Any], *, valid_task_ids: set[str]) -> bytes:
    """Return deterministic UTF-8 JSON with one final newline."""
    validate_feedback_payload(payload, valid_task_ids=valid_task_ids)
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")


def feedback_filename(payload: dict[str, Any]) -> str:
    """Create a readable filename without deriving identity from learner state."""
    code = payload.get("tester_code") or "anonymous"
    timestamp = _timestamp(payload.get("generated_at_utc")).replace("-", "").replace(":", "").replace("+00:00", "Z")
    timestamp = timestamp.replace(".", "").replace("Z", "Z")
    return f"introai_pilot_feedback_{code}_{timestamp}.json"


def _normalize_tester_code(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PilotFeedbackError("测试编号只能使用字母、数字、短横线或下划线。")
    normalized = value.strip()
    if not normalized:
        return None
    if not _TESTER_CODE.fullmatch(normalized):
        raise PilotFeedbackError("测试编号应为 2–32 位字母、数字、短横线或下划线。")
    return normalized


def _completed_ids(value: Any, valid_task_ids: set[str]) -> list[str]:
    if not isinstance(value, list):
        raise PilotFeedbackError("completed_task_ids must be a list.")
    if len(value) != len(set(value)):
        raise PilotFeedbackError("completed_task_ids must not contain duplicates.")
    result: list[str] = []
    for task_id in value:
        if not isinstance(task_id, str) or task_id not in valid_task_ids:
            raise PilotFeedbackError("completed_task_ids contains an unknown task.")
        result.append(task_id)
    return result


def _ratings(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != set(RATING_FIELDS):
        raise PilotFeedbackError("ratings must contain exactly the pilot rating fields.")
    result: dict[str, int] = {}
    for field, score in value.items():
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            raise PilotFeedbackError("每项评分必须是 1 至 5 的整数。")
        result[field] = score
    return result


def _free_text(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(FREE_TEXT_FIELDS):
        raise PilotFeedbackError("free_text_feedback must contain exactly the pilot feedback fields.")
    result: dict[str, str] = {}
    for field, text in value.items():
        if not isinstance(text, str):
            raise PilotFeedbackError("开放反馈必须是文本。")
        normalized = text.strip()
        if len(normalized) > _MAX_FREE_TEXT_LENGTH:
            raise PilotFeedbackError("开放反馈超过允许长度。")
        result[field] = normalized
    return result


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PilotFeedbackError("generated_at_utc must be a UTC timestamp.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PilotFeedbackError("generated_at_utc must be a UTC timestamp.") from None
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PilotFeedbackError("feedback payload keys must be strings.")
            normalized = key.casefold()
            if normalized in _FORBIDDEN_KEYS:
                raise PilotFeedbackError("feedback payload contains a forbidden field.")
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)
    elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise PilotFeedbackError("feedback payload must not contain non-finite values.")
