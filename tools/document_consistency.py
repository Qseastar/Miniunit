#!/usr/bin/env python3
"""Fail closed on hard-count drift in the maintained Search Algorithms docs."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification_benchmark import build_manifest  # noqa: E402


def check_documents(*, root: Path = ROOT) -> dict[str, list[str]]:
    """Return explicit errors and manual-review warnings without rewriting docs."""
    manifest = build_manifest(root=root)
    expected = {"production": len(manifest["production"]), "candidate": len(manifest["candidates"]), "blocked": len(manifest["blocked_slots"])}
    paths = [root / "docs" / name for name in ("search_algorithms_v1_scope.md", "search_algorithms_v1_implementation_plan.md", "reviewed_template_contribution_guide.md", "p2g_morning_summary.md") if (root / "docs" / name).exists()]
    errors, warnings = [], []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for label, value in expected.items():
            # Only assess unambiguous English count phrases; historical prose
            # may legitimately discuss earlier batches.
            for found in re.findall(rf"\b(\d+)\s+(?:active )?{label}s?\b", text, flags=re.I):
                if int(found) != value:
                    errors.append(f"{path.name}: {label} count {found} conflicts with {value}")
        if re.search(r"(?:complete mastery|fully mastered|完整掌握)", text, flags=re.I):
            warnings.append(f"{path.name}: review possible overclaim wording")
    return {"errors": errors, "warnings": warnings}
