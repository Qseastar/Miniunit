import json
from pathlib import Path
import subprocess
import sys

import pytest

from introai_tutor.pilot_feedback import FREE_TEXT_FIELDS, RATING_FIELDS, build_feedback_payload, payload_json
from introai_tutor.pilot_feedback_aggregation import (
    PilotFeedbackAggregationError,
    aggregate_feedback_directory,
    write_aggregation_outputs,
)
from introai_tutor.pilot_tasks import load_pilot_tasks
from introai_tutor.pilot_feedback_ui import generate_anonymous_tester_code


ROOT = Path(__file__).resolve().parents[1]


def _tasks():
    return load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")


def _payload(code, score, *, completed=None, feedback=""):
    tasks = _tasks()
    return build_feedback_payload(
        tasks_data=tasks,
        tester_code=code,
        completed_task_ids=completed or ["course_question_answering"],
        ratings={key: score for key in RATING_FIELDS},
        free_text_feedback={key: feedback if key == "other" else "" for key in FREE_TEXT_FIELDS},
        generated_at_utc=f"2026-08-04T12:00:0{score}Z",
    )


def _write(path, payload):
    task_ids = {task["task_id"] for task in _tasks()["tasks"]}
    path.write_bytes(payload_json(payload, valid_task_ids=task_ids))


def test_aggregation_reports_valid_invalid_duplicate_and_non_json_files(tmp_path):
    first = _payload("G01", 2, feedback="中文意见")
    duplicate = dict(first)
    duplicate["generated_at_utc"] = "2026-08-04T12:05:00Z"
    _write(tmp_path / "first.json", first)
    _write(tmp_path / "duplicate.json", duplicate)
    _write(tmp_path / "second.json", _payload("G02", 4, completed=["mastery_map"]))
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "array.json").write_text("[]", encoding="utf-8")
    (tmp_path / "schema.json").write_text('{"schema_version": 999}', encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    summary = aggregate_feedback_directory(tmp_path, tasks_data=_tasks())

    assert summary["valid_feedback_count"] == 2
    assert summary["rejected_files"] == [
        {"filename": "array.json", "reason": "invalid_feedback_payload"},
        {"filename": "broken.json", "reason": "invalid_feedback_payload"},
        {"filename": "schema.json", "reason": "invalid_feedback_payload"},
    ]
    assert summary["duplicate_files"] == [{"filename": "first.json", "duplicate_of": "duplicate.json"}]
    assert summary["ignored_non_json_files"] == ["notes.txt"]
    assert summary["ratings"]["qa_clarity"] == {
        "count": 2,
        "mean": 3,
        "median": 3.0,
        "min": 2,
        "max": 4,
        "distribution": {"1": 0, "2": 1, "3": 0, "4": 1, "5": 0},
    }
    assert summary["task_completion"]["course_question_answering"]["count"] == 1
    assert summary["free_text_feedback"][0]["free_text_feedback"]["other"] == "中文意见"


def test_empty_directory_is_a_controlled_zero_feedback_summary(tmp_path):
    summary = aggregate_feedback_directory(tmp_path, tasks_data=_tasks())

    assert summary["valid_feedback_count"] == 0
    assert summary["ratings"]["qa_clarity"]["mean"] is None
    assert summary["task_completion"]["mastery_map"]["rate"] is None


def test_aggregation_rejects_missing_directory_and_writes_three_output_formats(tmp_path):
    with pytest.raises(PilotFeedbackAggregationError):
        aggregate_feedback_directory(tmp_path / "missing", tasks_data=_tasks())

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "one.json", _payload(None, 5))
    summary = aggregate_feedback_directory(input_dir, tasks_data=_tasks())
    outputs = write_aggregation_outputs(summary, output_dir=tmp_path / "out")

    assert [path.name for path in outputs] == [
        "pilot_feedback_summary.json",
        "pilot_feedback_ratings.csv",
        "pilot_feedback_summary.md",
    ]
    assert json.loads(outputs[0].read_text(encoding="utf-8"))["valid_feedback_count"] == 1
    assert "qa_clarity" in outputs[1].read_text(encoding="utf-8")
    assert "IntroAI Tutor 内测反馈汇总" in outputs[2].read_text(encoding="utf-8")


def test_offline_summary_cli_writes_outputs_without_touching_input(tmp_path):
    input_dir = tmp_path / "downloads"
    input_dir.mkdir()
    _write(input_dir / "one.json", _payload("G01", 4))
    output_dir = tmp_path / "summary"

    result = subprocess.run(
        [
            sys.executable,
            "tools/summarize_pilot_feedback.py",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "有效反馈：1" in result.stdout
    assert (output_dir / "pilot_feedback_summary.json").is_file()
    assert sorted(path.name for path in input_dir.iterdir()) == ["one.json"]


def test_aggregation_accepts_new_automatic_and_legacy_anonymous_codes(tmp_path):
    automatic = generate_anonymous_tester_code(chooser=lambda _: "A")
    _write(tmp_path / "automatic.json", _payload(automatic, 5, feedback="中文"))
    _write(tmp_path / "legacy.json", _payload(None, 4))

    summary = aggregate_feedback_directory(tmp_path, tasks_data=_tasks())

    assert summary["valid_feedback_count"] == 2
    assert summary["ratings"]["qa_clarity"]["mean"] == 4.5


def test_aggregation_preserves_historical_and_current_pilot_release_counts(tmp_path):
    historical = _payload("G01", 4)
    historical["pilot_release"] = "p4a"
    current = _payload("G02", 5)
    _write(tmp_path / "historical.json", historical)
    _write(tmp_path / "current.json", current)

    summary = aggregate_feedback_directory(tmp_path, tasks_data=_tasks())
    outputs = write_aggregation_outputs(summary, output_dir=tmp_path / "summary")

    assert summary["valid_feedback_count"] == 2
    assert summary["pilot_release"] == "mixed"
    assert summary["pilot_releases"] == {"p4a": 1, "p4d": 1}
    assert "p4a × 1，p4d × 1" in outputs[2].read_text(encoding="utf-8")
