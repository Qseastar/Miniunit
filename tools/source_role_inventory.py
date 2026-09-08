#!/usr/bin/env python3
"""Render a reproducible source-role inventory from the derived template manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification_benchmark import build_manifest  # noqa: E402
from tools.verification_quality_gate import _read_json, validate_source_roles  # noqa: E402
from tools.course_material_manifest import load_course_material_manifest, material_index  # noqa: E402


def build_source_role_inventory(
    *,
    root: Path = ROOT,
    production_path: Path | None = None,
    candidate_path: Path | None = None,
    chunks_path: Path | None = None,
    material_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Build a report without changing template, review, or learner-state data."""
    root = Path(root)
    production_path = root / "data" / "diagnostic_templates.json" if production_path is None else Path(production_path)
    candidate_path = root / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json" if candidate_path is None else Path(candidate_path)
    chunks_path = root / "data" / "course_chunks.json" if chunks_path is None else Path(chunks_path)
    material_manifest_path = root / "data" / "course_material_manifest.json" if material_manifest_path is None else Path(material_manifest_path)
    manifest = build_manifest(root=root, production_path=production_path, candidate_path=candidate_path)
    chunks = {item["id"]: item for item in _read_json(chunks_path)["chunks"]}
    materials = material_index(load_course_material_manifest(material_manifest_path))
    rows: list[dict[str, Any]] = []
    per_template: list[dict[str, Any]] = []
    for entry in [*manifest["production"], *manifest["candidates"]]:
        issues = validate_source_roles(entry, chunks, materials)
        refs = entry["source_expectations"]
        for source in refs:
            chunk = chunks.get(source.get("chunk_id")) if isinstance(source, dict) else None
            context_only = source.get("context_only", False) if isinstance(source, dict) else None
            rows.append({
                "template_id": entry["template_id"],
                "bank": entry["bank_type"],
                "primary_concept": entry["primary_concept"],
                "source_ref": source,
                "chunk_id": source.get("chunk_id") if isinstance(source, dict) else None,
                "source_file": source.get("source_file") if isinstance(source, dict) else None,
                "page_start": source.get("page_start") if isinstance(source, dict) else None,
                "page_end": source.get("page_end") if isinstance(source, dict) else None,
                "context_only": context_only,
                "primary_evidence": source.get("primary_evidence", False) if isinstance(source, dict) else None,
                "topic_match": bool(chunk and entry["primary_concept"] in chunk["topic_ids"]),
                "role": "context_only" if context_only is True else "evidence",
                "role_valid": not issues,
                "evidence_strength": entry.get("evidence_strength"),
                "result": "pass" if not issues else "fail",
            })
        per_template.append({
            "template_id": entry["template_id"],
            "bank": entry["bank_type"],
            "primary_concept": entry["primary_concept"],
            "source_role_issues": issues,
            "result": "pass" if not issues else "fail",
        })
    duplicate_refs = sum(
        count - 1
        for count in Counter(
            (row["template_id"], row["chunk_id"], row["source_file"], row["page_start"], row["page_end"], row["context_only"])
            for row in rows
        ).values()
        if count > 1
    )
    source_issue_codes = [
        issue.split(":", 1)[0]
        for item in per_template
        for issue in item["source_role_issues"]
    ]
    return {
        "schema_version": 1,
        "run_metadata": {"mode": "offline", "network": "disabled", "env": "not_read"},
        "production_template_count": len(manifest["production"]),
        "candidate_template_count": len(manifest["candidates"]),
        "blocked_slot_count": len(manifest["blocked_slots"]),
        "rows": rows,
        "templates": per_template,
        "blocked_slots": manifest["blocked_slots"],
        "statistics": {
            "total_source_refs": len(rows),
            "production_source_refs": sum(row["bank"] == "production" for row in rows),
            "candidate_source_refs": sum(row["bank"] == "candidate" for row in rows),
            "context_only_refs": sum(row["context_only"] is True for row in rows),
            "declared_primary_evidence_refs": sum(row["primary_evidence"] is True for row in rows),
            "non_context_evidence_refs": sum(row["context_only"] is False for row in rows),
            "templates_with_zero_evidence_refs": sum(not any(row["template_id"] == item["template_id"] and row["context_only"] is False for row in rows) for item in per_template),
            "templates_with_all_refs_context_only": sum(bool([row for row in rows if row["template_id"] == item["template_id"]]) and all(row["context_only"] is True for row in rows if row["template_id"] == item["template_id"]) for item in per_template),
            "topic_mismatches": sum(row["context_only"] is False and not row["topic_match"] for row in rows),
            "invalid_pages": sum(code in {"SOURCE_PAGE_RANGE_INVALID", "SOURCE_PAGE_OUTSIDE_CHUNK"} for code in source_issue_codes),
            "filename_mismatches": source_issue_codes.count("SOURCE_FILENAME_MISMATCH"),
            "unknown_chunks": source_issue_codes.count("SOURCE_CHUNK_UNKNOWN"),
            "invalid_templates": sum(item["result"] == "fail" for item in per_template),
            "duplicate_refs": duplicate_refs,
            "evidence_strength_distribution": dict(sorted(Counter(row["evidence_strength"] for row in rows if row["evidence_strength"] is not None).items())),
        },
    }


def markdown_inventory(report: dict[str, Any]) -> str:
    lines = [
        "# Verification source-role inventory", "",
        f"- Production templates: {report['production_template_count']}",
        f"- Candidate templates: {report['candidate_template_count']}",
        f"- Blocked slots: {report['blocked_slot_count']}", "",
        "| Template | Bank | Primary concept | Source | Page | Context only | Topic match | Role | Strength | Result |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['template_id']} | {row['bank']} | {row['primary_concept']} | {row['chunk_id']} | {row['source_file']}:{row['page_start']}-{row['page_end']} | {row['context_only']} | {row['topic_match']} | {row['role']} | {row['evidence_strength'] or 'production'} | {row['result']} |"
        )
    lines.extend(["", "## Statistics"])
    lines.extend(f"- {key}: {value}" for key, value in report["statistics"].items())
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, default=ROOT / "data" / "diagnostic_templates.json")
    parser.add_argument("--candidates", type=Path, default=ROOT / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data" / "course_chunks.json")
    parser.add_argument("--material-manifest", type=Path, default=ROOT / "data" / "course_material_manifest.json")
    parser.add_argument("--json-report", type=Path, required=True)
    parser.add_argument("--markdown-report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_source_role_inventory(production_path=args.production, candidate_path=args.candidates, chunks_path=args.chunks, material_manifest_path=args.material_manifest)
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.markdown_report.write_text(markdown_inventory(report), encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"source-role inventory error: {type(error).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
