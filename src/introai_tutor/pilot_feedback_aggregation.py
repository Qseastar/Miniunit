"""Offline aggregation of downloaded, privacy-minimal pilot feedback files."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any

from introai_tutor.pilot_feedback import (
    FREE_TEXT_FIELDS,
    PILOT_NAME,
    RATING_FIELDS,
    PilotFeedbackError,
    validate_feedback_payload,
)
from introai_tutor.pilot_tasks import ordered_tasks


SUMMARY_SCHEMA_VERSION = 1


class PilotFeedbackAggregationError(ValueError):
    """Raised for invalid aggregation inputs or unsafe output paths."""


def aggregate_feedback_directory(
    directory: str | Path, *, tasks_data: dict[str, Any]
) -> dict[str, Any]:
    """Read one directory without mutating inputs and return a stable summary."""
    root = Path(directory)
    if not root.is_dir():
        raise PilotFeedbackAggregationError("feedback input directory does not exist.")
    tasks = ordered_tasks(tasks_data)
    valid_task_ids = {task["task_id"] for task in tasks}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    ignored: list[str] = []
    duplicates: list[dict[str, str]] = []
    seen_hashes: dict[str, str] = {}
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.suffix.casefold() != ".json":
            ignored.append(path.name)
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            validate_feedback_payload(payload, valid_task_ids=valid_task_ids)
        except (OSError, json.JSONDecodeError, PilotFeedbackError, TypeError, ValueError):
            rejected.append({"filename": path.name, "reason": "invalid_feedback_payload"})
            continue
        fingerprint = _response_fingerprint(payload)
        if fingerprint in seen_hashes:
            duplicates.append({"filename": path.name, "duplicate_of": seen_hashes[fingerprint]})
            continue
        seen_hashes[fingerprint] = path.name
        accepted.append(deepcopy(payload))
    return _summary(
        tasks=tasks,
        accepted=accepted,
        rejected=rejected,
        ignored=ignored,
        duplicates=duplicates,
    )


def write_aggregation_outputs(summary: dict[str, Any], *, output_dir: str | Path) -> list[Path]:
    """Write stable JSON, CSV and Markdown output files outside the input directory."""
    _validate_summary(summary)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "pilot_feedback_summary.json"
    csv_path = destination / "pilot_feedback_ratings.csv"
    markdown_path = destination / "pilot_feedback_summary.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["rating_id", "rating_label_zh", "count", "mean", "median", "min", "max", "distribution"],
        )
        writer.writeheader()
        for rating_id, values in summary["ratings"].items():
            writer.writerow(
                {
                    "rating_id": rating_id,
                    "rating_label_zh": RATING_FIELDS[rating_id],
                    "count": values["count"],
                    "mean": values["mean"],
                    "median": values["median"],
                    "min": values["min"],
                    "max": values["max"],
                    "distribution": json.dumps(values["distribution"], ensure_ascii=False, sort_keys=True),
                }
            )
    markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")
    return [json_path, csv_path, markdown_path]


def _summary(
    *,
    tasks: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, str]],
    ignored: list[str],
    duplicates: list[dict[str, str]],
) -> dict[str, Any]:
    count = len(accepted)
    completion = {
        task["task_id"]: {
            "title_zh": task["title_zh"],
            "count": sum(task["task_id"] in item["completed_task_ids"] for item in accepted),
            "rate": (sum(task["task_id"] in item["completed_task_ids"] for item in accepted) / count if count else None),
        }
        for task in tasks
    }
    ratings: dict[str, dict[str, Any]] = {}
    for rating_id in RATING_FIELDS:
        scores = [item["ratings"][rating_id] for item in accepted if rating_id in item["ratings"]]
        distribution = {str(score): scores.count(score) for score in range(1, 6)}
        ratings[rating_id] = {
            "count": len(scores),
            "mean": round(mean(scores), 4) if scores else None,
            "median": median(scores) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "distribution": distribution,
        }
    comments = [
        {
            "tester_code": item["tester_code"],
            "free_text_feedback": item["free_text_feedback"],
        }
        for item in accepted
        if any(item["free_text_feedback"].values())
    ]
    release_counts = Counter(item["pilot_release"] for item in accepted)
    if not release_counts:
        summary_release: str | None = None
    elif len(release_counts) == 1:
        summary_release = next(iter(release_counts))
    else:
        summary_release = "mixed"
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "pilot_name": PILOT_NAME,
        # Preserve the historical single-release field for lightweight
        # consumers while exposing the actual accepted-payload distribution.
        "pilot_release": summary_release,
        "pilot_releases": dict(sorted(release_counts.items())),
        "valid_feedback_count": count,
        "rejected_files": rejected,
        "ignored_non_json_files": ignored,
        "duplicate_files": duplicates,
        "task_completion": completion,
        "ratings": ratings,
        "free_text_feedback": comments,
    }


def _response_fingerprint(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "generated_at_utc"}
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_summary(summary: Any) -> None:
    if not isinstance(summary, dict) or summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        raise PilotFeedbackAggregationError("feedback summary has an invalid schema.")
    if set(summary.get("ratings", {})) != set(RATING_FIELDS):
        raise PilotFeedbackAggregationError("feedback summary has invalid ratings.")
    release_counts = summary.get("pilot_releases")
    if not isinstance(release_counts, dict) or any(
        not isinstance(release, str)
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count < 1
        for release, count in release_counts.items()
    ):
        raise PilotFeedbackAggregationError("feedback summary has invalid pilot_releases.")


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# IntroAI Tutor 内测反馈汇总",
        "",
        f"- 有效反馈：{summary['valid_feedback_count']}",
        f"- 拒绝文件：{len(summary['rejected_files'])}",
        f"- 重复文件：{len(summary['duplicate_files'])}",
        f"- 忽略的非 JSON 文件：{len(summary['ignored_non_json_files'])}",
        "- 反馈版本分布："
        + (
            "无"
            if not summary["pilot_releases"]
            else "，".join(
                f"{release} × {count}"
                for release, count in summary["pilot_releases"].items()
            )
        ),
        "",
        "## 任务完成情况",
        "",
        "| 任务 | 完成人数 | 完成比例 |",
        "| --- | ---: | ---: |",
    ]
    for values in summary["task_completion"].values():
        rate = "—" if values["rate"] is None else f"{values['rate']:.0%}"
        lines.append(f"| {values['title_zh']} | {values['count']} | {rate} |")
    lines.extend(["", "## 量表评分", "", "| 指标 | 样本数 | 平均值 | 中位数 | 范围 |", "| --- | ---: | ---: | ---: | --- |"])
    for rating_id, values in summary["ratings"].items():
        average = "—" if values["mean"] is None else f"{values['mean']:.2f}"
        mid = "—" if values["median"] is None else str(values["median"])
        span = "—" if values["min"] is None else f"{values['min']}–{values['max']}"
        lines.append(f"| {RATING_FIELDS[rating_id]} | {values['count']} | {average} | {mid} | {span} |")
    lines.extend(["", "## 开放反馈", ""])
    if not summary["free_text_feedback"]:
        lines.append("暂无非空开放反馈。")
    else:
        for index, item in enumerate(summary["free_text_feedback"], start=1):
            label = item["tester_code"] or "anonymous"
            lines.append(f"### {index}. {label}")
            for field, text in item["free_text_feedback"].items():
                if text:
                    lines.append(f"- {FREE_TEXT_FIELDS[field]}：{text}")
            lines.append("")
    return "\n".join(lines) + "\n"
