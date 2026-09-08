from copy import deepcopy
from pathlib import Path

import json
import pytest

from introai_tutor.pilot_feedback import (
    FREE_TEXT_FIELDS,
    PILOT_RELEASE,
    RATING_FIELDS,
    PilotFeedbackError,
    build_feedback_payload,
    feedback_filename,
    payload_json,
    validate_feedback_payload,
)
from introai_tutor.pilot_tasks import load_pilot_tasks


ROOT = Path(__file__).resolve().parents[1]


def _payload(**changes):
    tasks = load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")
    values = {
        "tasks_data": tasks,
        "tester_code": "G01",
        "completed_task_ids": ["course_question_answering"],
        "ratings": {key: 3 for key in RATING_FIELDS},
        "free_text_feedback": {key: "中文反馈" if key == "other" else "" for key in FREE_TEXT_FIELDS},
        "generated_at_utc": "2026-08-04T12:00:00Z",
    }
    values.update(changes)
    return build_feedback_payload(**values), tasks


def test_feedback_payload_is_minimal_unicode_safe_and_stable():
    payload, tasks = _payload()
    task_ids = {task["task_id"] for task in tasks["tasks"]}

    encoded = payload_json(payload, valid_task_ids=task_ids)

    assert json.loads(encoded) == payload
    assert encoded.endswith(b"\n")
    assert "中文反馈".encode() in encoded
    assert feedback_filename(payload) == "introai_pilot_feedback_G01_20260804T120000Z.json"
    forbidden = {
        "learner", "learner_id", "learner_uuid", "mastery", "recommendation",
        "evidence", "exposure", "question", "answer", "prompt", "chunk",
        "api_key", "authorization", "database_path", "user_agent", "ip_address",
    }
    assert not forbidden.intersection(payload)


@pytest.mark.parametrize("tester_code", ["A", "name with spaces", "a@b.com", "x" * 33])
def test_invalid_tester_code_is_rejected(tester_code):
    with pytest.raises(PilotFeedbackError):
        _payload(tester_code=tester_code)


@pytest.mark.parametrize("score", [0, 6, True, 2.5])
def test_invalid_rating_is_rejected(score):
    with pytest.raises(PilotFeedbackError):
        _payload(ratings={key: score for key in RATING_FIELDS})


def test_payload_rejects_unknown_tasks_duplicates_forbidden_keys_and_nonfinite_values():
    payload, tasks = _payload()
    task_ids = {task["task_id"] for task in tasks["tasks"]}
    for mutate in (
        lambda value: value.__setitem__("completed_task_ids", ["unknown"]),
        lambda value: value.__setitem__("completed_task_ids", ["course_question_answering", "course_question_answering"]),
        lambda value: value.__setitem__("mastery", {}),
        lambda value: value.__setitem__("learner_uuid", "not-allowed"),
        lambda value: value["ratings"].__setitem__("qa_clarity", float("nan")),
    ):
        broken = deepcopy(payload)
        mutate(broken)
        with pytest.raises(PilotFeedbackError):
            validate_feedback_payload(broken, valid_task_ids=task_ids)


def test_optional_tester_code_and_free_text_are_allowed_but_bounded():
    payload, _ = _payload(tester_code="", free_text_feedback={key: "" for key in FREE_TEXT_FIELDS})
    assert payload["tester_code"] is None
    with pytest.raises(PilotFeedbackError):
        _payload(free_text_feedback={key: "x" * 2001 for key in FREE_TEXT_FIELDS})


def test_new_exports_are_p4d_while_downloaded_p4a_payloads_remain_valid_history():
    payload, tasks = _payload()
    task_ids = {task["task_id"] for task in tasks["tasks"]}

    assert PILOT_RELEASE == "p4d"
    assert payload["pilot_release"] == "p4d"
    legacy = deepcopy(payload)
    legacy["pilot_release"] = "p4a"
    validate_feedback_payload(legacy, valid_task_ids=task_ids)
    unsupported = deepcopy(payload)
    unsupported["pilot_release"] = "p3z"
    with pytest.raises(PilotFeedbackError, match="pilot_release"):
        validate_feedback_payload(unsupported, valid_task_ids=task_ids)
