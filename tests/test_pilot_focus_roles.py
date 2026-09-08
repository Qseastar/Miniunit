from copy import deepcopy
import json
from pathlib import Path

import pytest

from introai_tutor.pilot_focus_roles import (
    PilotFocusRoleError,
    load_focus_roles,
    ordered_focus_roles,
    validate_focus_roles,
)
from introai_tutor.pilot_tasks import load_pilot_tasks


ROOT = Path(__file__).resolve().parents[1]


def _data():
    tasks = load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")
    roles = load_focus_roles(ROOT / "data" / "internal_pilot_focus_roles.json", tasks_data=tasks)
    return tasks, roles


def test_six_focus_roles_require_all_six_core_tasks_and_have_stable_order():
    tasks, roles = _data()
    task_ids = {item["task_id"] for item in tasks["tasks"]}
    ordered = ordered_focus_roles(roles, tasks_data=tasks)
    assert [item["role_id"] for item in ordered] == [f"role_{letter}" for letter in "abcdef"]
    assert len(ordered) == 6
    assert all(set(item["required_core_task_ids"]) == task_ids for item in ordered)


def test_focus_role_loader_returns_copy_and_rejects_unknown_fields():
    tasks, roles = _data()
    roles["roles"][0]["title_zh"] = "changed"
    reloaded = load_focus_roles(ROOT / "data" / "internal_pilot_focus_roles.json", tasks_data=tasks)
    assert reloaded["roles"][0]["title_zh"] != "changed"
    broken = deepcopy(reloaded)
    broken["roles"][0]["unexpected"] = True
    with pytest.raises(PilotFocusRoleError):
        validate_focus_roles(broken, tasks_data=tasks)


def test_focus_roles_reject_internal_or_sensitive_public_values():
    tasks, roles = _data()
    for value in ("learner UUID", "verify_hidden_answer", "Authorization header"):
        broken = deepcopy(roles)
        broken["roles"][0]["focus"] = value
        with pytest.raises(PilotFocusRoleError):
            validate_focus_roles(broken, tasks_data=tasks)


def test_focus_role_document_is_json_without_identity_or_template_answers():
    document = json.loads((ROOT / "data" / "internal_pilot_focus_roles.json").read_text(encoding="utf-8"))
    encoded = json.dumps(document, ensure_ascii=False).casefold()
    assert "learner_uuid" not in encoded
    assert "expected_answer" not in encoded
    assert "api_key" not in encoded
