from copy import deepcopy
from pathlib import Path

import pytest

from introai_tutor.pilot_tasks import PilotTaskError, load_pilot_tasks, ordered_tasks, validate_pilot_tasks


ROOT = Path(__file__).resolve().parents[1]


def test_real_pilot_tasks_are_six_public_stably_ordered_tasks():
    data = load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")

    tasks = ordered_tasks(data)

    assert data["schema_version"] == 1
    assert len(tasks) == 6
    assert [task["order"] for task in tasks] == [1, 2, 3, 4, 5, 6]
    assert len({task["task_id"] for task in tasks}) == 6
    assert all(task["title_zh"].strip() for task in tasks)
    assert not any("verify_" in str(task) or "expected_answer" in str(task) for task in tasks)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["tasks"][0].pop("title_zh"),
        lambda data: data["tasks"][0].__setitem__("unexpected", True),
        lambda data: data["tasks"][1].__setitem__("task_id", data["tasks"][0]["task_id"]),
        lambda data: data.__setitem__("schema_version", 2),
        lambda data: data["tasks"][0].__setitem__("title_zh", " "),
    ],
)
def test_invalid_task_schema_fails_closed(mutate):
    data = load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")
    mutate(data)

    with pytest.raises(PilotTaskError):
        validate_pilot_tasks(data)
