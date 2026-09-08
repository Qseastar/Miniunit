#!/usr/bin/env python3
"""Generate deterministic source-traceability and capability-coverage reports."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification_benchmark import build_manifest  # noqa: E402
from tools.verification_quality_gate import validate_source_roles  # noqa: E402


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_reports(*, root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return source and capability reports from metadata, without opening PDFs."""
    manifest = build_manifest(root=root)
    chunks = {item["id"]: item for item in _read(root / "data" / "course_chunks.json")["chunks"]}
    concepts = _read(root / "data" / "knowledge_points.json")["knowledge_points"]
    entries = [*manifest["production"], *manifest["candidates"]]
    source_entries = []
    for entry in entries:
        source_issues = validate_source_roles(entry, chunks)
        sources = []
        for ref in entry["source_expectations"]:
            chunk = chunks[ref["chunk_id"]]
            sources.append({
                **ref,
                "source_role": chunk["source_role"],
                "chunk_review_status": chunk["review_status"],
                "topic_match": entry["primary_concept"] in chunk["topic_ids"],
                "context_only": ref.get("context_only", False),
                "source_evidence_role": "context_only" if ref.get("context_only", False) else "evidence",
            })
        source_entries.append({
            "template_id": entry["template_id"], "bank_type": entry["bank_type"],
            "primary_concept": entry["primary_concept"], "sources": sources,
            "source_role_issues": source_issues,
            "source_role_result": "pass" if not source_issues else "fail",
        })
    status_counts = Counter(source["chunk_review_status"] for item in source_entries for source in item["sources"])
    role_counts = Counter(source["source_role"] for item in source_entries for source in item["sources"])
    trace = {
        "schema_version": 1,
        "production_template_count": len(manifest["production"]),
        "candidate_template_count": len(manifest["candidates"]),
        "blocked_slot_count": len(manifest["blocked_slots"]),
        "course_chunk_count": len(chunks),
        "entries": source_entries,
        "chunk_review_status_distribution": dict(sorted(status_counts.items())),
        "source_role_distribution": dict(sorted(role_counts.items())),
        "blocked_slots": manifest["blocked_slots"],
    }
    by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_concept[entry["primary_concept"]].append(entry)
    blocked_by_concept = Counter(slot["concept"] for slot in manifest["blocked_slots"])
    coverage_entries = []
    for point in concepts:
        concept_id = point["id"]
        related = by_concept[concept_id]
        production = [item for item in related if item["bank_type"] == "production"]
        candidate = [item for item in related if item["bank_type"] == "candidate"]
        source_chunks = [chunk["id"] for chunk in chunks.values() if concept_id in chunk["topic_ids"]]
        status = "production" if production else "candidate" if candidate else "blocked" if blocked_by_concept[concept_id] else "none"
        coverage_entries.append({
            "concept_id": concept_id,
            "title_zh": point["title_zh"],
            "prerequisites": point["prerequisites"],
            "course_chunks": source_chunks,
            "production_evidence_count": len(production),
            "candidate_evidence_count": len(candidate),
            "blocked_count": blocked_by_concept[concept_id],
            "template_ids": [item["template_id"] for item in related],
            "ability_slices": [item["capability_boundary"] for item in related],
            "source_strength": "direct_or_reviewed_metadata" if related else "none",
            "question_types": sorted({item["question_type"] for item in related}),
            "scorers": sorted({item["scorer"] for item in related}),
            "eligible_intent_coverage": sorted({intent for item in related for intent in item["eligible_intents"]}),
            "ui_available": all(item["ui_availability"] for item in production) if production else False,
            "overclaim_risk": "narrow_slice_only" if related else "no_verified_slice",
            "remaining_gap": "No production verification template." if not production else "A template is narrow evidence, not complete concept mastery.",
            "status": status,
        })
    coverage = {
        "schema_version": 1,
        "production_template_count": len(manifest["production"]),
        "candidate_template_count": len(manifest["candidates"]),
        "blocked_slot_count": len(manifest["blocked_slots"]),
        "concepts": coverage_entries,
    }
    return trace, coverage


def _markdown_trace(report: dict[str, Any]) -> str:
    lines = ["# Verification source traceability", "", f"- Production templates: {report['production_template_count']}", f"- Candidate templates: {report['candidate_template_count']}", f"- Blocked slots: {report['blocked_slot_count']}", "", "| Template | Bank | Concept | Sources | Source-role result |", "|---|---|---|---|---|"]
    for item in report["entries"]:
        source_text = "; ".join(f"{source['source_file']}:{source['page_start']}-{source['page_end']} ({source['chunk_id']}; {source['source_evidence_role']})" for source in item["sources"])
        lines.append(f"| {item['template_id']} | {item['bank_type']} | {item['primary_concept']} | {source_text} | {item['source_role_result']} |")
    return "\n".join(lines) + "\n"


def _markdown_coverage(report: dict[str, Any]) -> str:
    lines = ["# Search Algorithms verification capability coverage", "", "A production template is narrow evidence, not a claim of complete concept mastery.", "", "| Concept | Status | Production | Candidate | Blocked | Templates |", "|---|---|---:|---:|---:|---|"]
    for item in report["concepts"]:
        lines.append(f"| {item['concept_id']} | {item['status']} | {item['production_evidence_count']} | {item['candidate_evidence_count']} | {item['blocked_count']} | {', '.join(item['template_ids']) or '—'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-json", type=Path, required=True)
    parser.add_argument("--source-markdown", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--coverage-markdown", type=Path, required=True)
    args = parser.parse_args(argv)
    trace, coverage = build_reports()
    args.source_json.write_text(json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.source_markdown.write_text(_markdown_trace(trace), encoding="utf-8")
    args.coverage_json.write_text(json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.coverage_markdown.write_text(_markdown_coverage(coverage), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
