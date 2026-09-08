#!/usr/bin/env python3
"""Aggregate downloaded IntroAI Tutor pilot feedback without network access."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from introai_tutor.pilot_feedback_aggregation import (  # noqa: E402
    PilotFeedbackAggregationError,
    aggregate_feedback_directory,
    write_aggregation_outputs,
)
from introai_tutor.pilot_tasks import PilotTaskError, load_pilot_tasks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="汇总下载式 IntroAI 内测反馈 JSON。")
    parser.add_argument("feedback_dir", type=Path, help="反馈 JSON 所在目录")
    parser.add_argument("--output-dir", required=True, type=Path, help="汇总输出目录")
    args = parser.parse_args(argv)
    if args.feedback_dir.resolve() == args.output_dir.resolve():
        parser.error("--output-dir 必须不同于反馈输入目录。")
    try:
        tasks = load_pilot_tasks(ROOT / "data" / "pilot_search_algorithms_tasks.json")
        summary = aggregate_feedback_directory(args.feedback_dir, tasks_data=tasks)
        paths = write_aggregation_outputs(summary, output_dir=args.output_dir)
    except (PilotTaskError, PilotFeedbackAggregationError) as error:
        print(f"汇总失败：{error}", file=sys.stderr)
        return 2
    print(f"有效反馈：{summary['valid_feedback_count']}")
    print(f"拒绝文件：{len(summary['rejected_files'])}")
    print(f"重复文件：{len(summary['duplicate_files'])}")
    for path in paths:
        print(path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
