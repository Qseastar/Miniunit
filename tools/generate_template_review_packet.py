#!/usr/bin/env python3
"""Generate a stable, non-sensitive human review packet from the P2g manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification_benchmark import BenchmarkInputError, build_manifest  # noqa: E402


def _raw_templates(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    templates = data["templates"]
    return {item["id"]: item for item in templates}


def build_review_packet(
    *, root: Path = ROOT, production_path: Path | None = None, candidate_path: Path | None = None
) -> dict[str, Any]:
    """Create review-only data; never changes review status or promotion state."""
    production_path = root / "data" / "diagnostic_templates.json" if production_path is None else production_path
    candidate_path = root / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json" if candidate_path is None else candidate_path
    manifest = build_manifest(root=root, production_path=production_path, candidate_path=candidate_path)
    raw = {**_raw_templates(production_path), **_raw_templates(candidate_path)}
    groups: dict[str, list[dict[str, Any]]] = {"production": [], "candidate": []}
    for bank in ("production", "candidates"):
        target = "production" if bank == "production" else "candidate"
        for entry in manifest[bank]:
            template = raw[entry["template_id"]]
            groups[target].append({
                **entry,
                "prompt": template["prompt"],
                "choices": template["choices"],
                "expected_answer": template["expected_answer"],
                "hint": template["teaching_support"]["hint"],
                "explanation": template["teaching_support"]["explanation"],
                "owner_decision": "",
            })
    return {"schema_version": 1, "production": groups["production"], "candidates": groups["candidate"], "blocked_slots": manifest["blocked_slots"]}


def markdown_packet(packet: dict[str, Any]) -> str:
    lines = ["# Search Algorithms template review packet", "", "This packet records evidence and review inputs only. It does not approve or promote any candidate.", "Authoritative owner decisions are recorded in `docs/search_algorithms_p2f_candidate_review.md`; the `owner_decision` fields in this generated packet remain blank by design."]
    for title, entries in (("Production reviewed templates", packet["production"]), ("Candidate templates — human approval required", packet["candidates"])):
        lines.extend(["", f"## {title}"])
        for entry in entries:
            lines.extend(["", f"### `{entry['template_id']}`", "", f"- Bank: `{entry['bank_type']}`", f"- Review status: `{entry['review_status']}`", f"- Primary concept: `{entry['primary_concept']}`", f"- Scorer / type: `{entry['scorer']}` / `{entry['question_type']}`", f"- Eligible intents: {', '.join(entry['eligible_intents'])}", f"- Explicit negative intent: {', '.join(entry['explicit_negative_intents'])}", f"- Expected answer position: {entry['expected_answer_position']}", f"- Evidence expectation: `{entry['evidence_expectation']}`", f"- UI available: {entry['ui_availability']}", f"- Capability boundary: {entry['capability_boundary']}", "- Sources:"])
            lines.extend(f"  - `{source['source_file']}:{source['page_start']}-{source['page_end']}` / `{source['chunk_id']}`" for source in entry["source_expectations"])
            lines.extend(["", f"**Prompt:** {entry['prompt']}", "", "**Choices:**"])
            lines.extend(f"- `{choice['id']}`: {choice['text']}" for choice in entry["choices"])
            lines.extend([
                "",
                f"**Expected answer:** `{json.dumps(entry['expected_answer'], ensure_ascii=False)}`",
                "",
                f"**Hint:** {entry['hint']}",
                "",
                f"**Explanation:** {entry['explanation']}",
                "",
                "**Owner decision:**",
            ])
    lines.extend(["", "## Blocked capability slots"])
    for slot in packet["blocked_slots"]:
        lines.extend([f"- `{slot['proposed_template_id']}` ({slot['concept']}): {slot['blocked_reason']}", f"  - Missing evidence: {slot['missing_evidence']}", f"  - Prohibited fallback: {slot['prohibited_fallback_knowledge']}"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, default=ROOT / "data" / "diagnostic_templates.json")
    parser.add_argument("--candidates", type=Path, default=ROOT / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data" / "course_chunks.json")
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.chunks.is_file():
        print("review-packet input error: course chunks file is missing", file=sys.stderr)
        return 2
    try:
        packet = build_review_packet(production_path=args.production, candidate_path=args.candidates)
    except (BenchmarkInputError, OSError, json.JSONDecodeError) as error:
        print(f"review-packet input error: {error}", file=sys.stderr)
        return 2
    args.json_output.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown_packet(packet), encoding="utf-8")
    print(f"Generated {len(packet['production'])} production, {len(packet['candidates'])} candidate, and {len(packet['blocked_slots'])} blocked entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
