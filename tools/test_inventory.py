#!/usr/bin/env python3
"""Collect an offline, deterministic inventory of the pytest suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build_inventory(*, root: Path = ROOT) -> dict:
    """Use pytest collection only; no test body, network, or environment is read."""
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    completed = subprocess.run(command, cwd=root, env={**{"PYTHONPATH": "src"}}, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError("pytest collection failed")
    lines = completed.stdout.splitlines()
    total = next(
        (int(line.split()[0]) for line in reversed(lines) if " tests collected" in line),
        0,
    )
    files = sorted((root / "tests").glob("test_*.py"))
    categories = {
        "scorer": ["scorer", "verification"], "acceptance": ["acceptance"], "candidate": ["candidate"],
        "selector_handoff": ["selection", "handoff"], "ui": ["streamlit", "app"], "tooling": ["p2g", "quality"],
    }
    return {
        "schema_version": 1,
        "baseline_before_p2g": 971,
        "collected_test_count": total,
        "test_file_count": len(files),
        "category_file_counts": {name: sum(any(token in path.name for token in tokens) for path in files) for name, tokens in categories.items()},
        "collection_mode": "pytest --collect-only -q",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_inventory()
    args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Test suite inventory", "", f"- Baseline before P2g: {report['baseline_before_p2g']}", f"- Collected tests: {report['collected_test_count']}", f"- Test files: {report['test_file_count']}", "", "| Category | Test files |", "|---|---:|"]
    lines.extend(f"| {name} | {count} |" for name, count in report["category_file_counts"].items())
    args.markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
