#!/usr/bin/env python3
"""Run the deterministic, offline verification-bank quality gate.

The gate is intentionally read-only: it derives inventory from the reviewed
bank and its existing acceptance contracts, then calls the production scorer
and validator.  It never creates a learner state, starts an API client, or
promotes candidates.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.template_selection import (  # noqa: E402
    DiagnosticTemplateError,
    load_diagnostic_templates,
)
from introai_tutor.verification_diagnostics import (  # noqa: E402
    VerificationDiagnosticError,
    score_verification_answer,
)
from tools.verification_benchmark import (  # noqa: E402
    BenchmarkInputError,
    build_manifest,
    load_candidate_document,
    repository_root,
)
from tools.course_material_manifest import (  # noqa: E402
    CourseMaterialManifestError,
    load_course_material_manifest,
    material_index,
    validate_chunk_material_coverage,
    validate_source_material,
)

EXIT_OK = 0
EXIT_QUALITY_FAILURE = 1
EXIT_INPUT_ERROR = 2
EXIT_INTERNAL_ERROR = 3
EXIT_STRICT_WARNING = 4
KNOWN_DIAGNOSTIC_INTENTS = {
    "definition", "explanation", "comparison", "algorithm_trace", "property", "diagnostic_request",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise BenchmarkInputError(f"File is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise BenchmarkInputError(f"Invalid JSON file: {path}") from error


def _concept_ids(root: Path) -> set[str]:
    document = _read_json(root / "data" / "knowledge_points.json")
    try:
        return {item["id"] for item in document["knowledge_points"]}
    except (KeyError, TypeError) as error:
        raise BenchmarkInputError("Knowledge point data is invalid.") from error


def _template_data(
    *, root: Path, production_path: Path, candidate_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    concepts = _concept_ids(root)
    try:
        production = load_diagnostic_templates(
            production_path, valid_concept_ids=concepts
        )["templates"]
    except (DiagnosticTemplateError, OSError, json.JSONDecodeError) as error:
        raise BenchmarkInputError(f"Production templates are invalid: {error}") from None
    candidates = load_candidate_document(candidate_path, root=root)["templates"]
    return production, candidates


_SOURCE_REF_KEYS = {"chunk_id", "source_file", "page_start", "page_end"}
_SOURCE_REF_OPTIONAL_KEYS = {"context_only", "primary_evidence"}


def validate_source_roles(
    entry: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
    materials: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> list[str]:
    """Fail closed on candidate/manifest source-role metadata.

    ``context_only`` pages remain fully validated metadata, but can never be
    counted as primary-concept evidence.  This helper is shared by the gate,
    candidate lint, and source-role inventory rather than maintaining parallel
    source validators.
    """
    issues: list[str] = []
    refs = entry.get("source_expectations")
    if not isinstance(refs, list) or not refs:
        return ["SOURCE_REFS_MISSING"]
    if (
        entry.get("bank_type") == "candidate"
        and (not isinstance(entry.get("source_review_note"), str) or not entry["source_review_note"].strip())
    ):
        issues.append("SOURCE_REVIEW_NOTE_MISSING")

    evidence_count = 0
    primary_evidence_count = 0
    declared_primary_anchor_count = 0
    declares_primary_anchor = False
    context_count = 0
    seen_refs: set[tuple[str, str, int, int, bool]] = set()
    for index, source in enumerate(refs):
        label = f"source[{index}]"
        if not isinstance(source, dict):
            issues.append(f"SOURCE_REF_SCHEMA_INVALID: {label}")
            continue
        keys = set(source)
        if not _SOURCE_REF_KEYS <= keys or keys - (_SOURCE_REF_KEYS | _SOURCE_REF_OPTIONAL_KEYS):
            issues.append(f"SOURCE_REF_SCHEMA_INVALID: {label}")
            continue
        if "context_only" in source and type(source["context_only"]) is not bool:
            issues.append(f"SOURCE_CONTEXT_ONLY_TYPE_INVALID: {label}")
            continue
        if "primary_evidence" in source and type(source["primary_evidence"]) is not bool:
            issues.append(f"SOURCE_PRIMARY_EVIDENCE_TYPE_INVALID: {label}")
            continue
        context_only = source.get("context_only", False)
        primary_anchor = source.get("primary_evidence", False)
        declares_primary_anchor = declares_primary_anchor or primary_anchor
        chunk_id = source.get("chunk_id")
        source_file = source.get("source_file")
        start, end = source.get("page_start"), source.get("page_end")
        if not isinstance(chunk_id, str) or not chunk_id or not isinstance(source_file, str) or not source_file:
            issues.append(f"SOURCE_REF_SCHEMA_INVALID: {label}")
            continue
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            issues.append(f"SOURCE_PAGE_RANGE_INVALID: {label}")
            continue
        identity = (chunk_id, source_file, start, end, context_only)
        if identity in seen_refs:
            issues.append(f"SOURCE_REF_DUPLICATE: {chunk_id}")
        seen_refs.add(identity)
        chunk = chunks.get(chunk_id)
        if chunk is None:
            issues.append(f"SOURCE_CHUNK_UNKNOWN: {chunk_id}")
            continue
        if chunk["source_file"] != source_file:
            issues.append(f"SOURCE_FILENAME_MISMATCH: {chunk_id}")
        if start < chunk["page_start"] or end > chunk["page_end"]:
            issues.append(f"SOURCE_PAGE_OUTSIDE_CHUNK: {chunk_id}")
        if materials is not None:
            issues.extend(
                validate_source_material(
                    chunk=chunk,
                    source_file=source_file,
                    page_start=start,
                    page_end=end,
                    materials=materials,
                )
            )
        if context_only:
            context_count += 1
            if primary_anchor:
                issues.append(f"SOURCE_PRIMARY_EVIDENCE_CONTEXT_ONLY: {label}")
            continue
        evidence_count += 1
        if entry["primary_concept"] not in chunk["topic_ids"]:
            issues.append(f"SOURCE_PRIMARY_TOPIC_MISMATCH: {chunk_id}")
        else:
            primary_evidence_count += 1
            if primary_anchor:
                declared_primary_anchor_count += 1

    if evidence_count == 0:
        issues.append("SOURCE_CONTEXT_ONLY_WITHOUT_EVIDENCE")
    elif primary_evidence_count == 0:
        issues.append("SOURCE_NO_PRIMARY_EVIDENCE")
    if declares_primary_anchor and declared_primary_anchor_count == 0:
        issues.append("SOURCE_PRIMARY_EVIDENCE_ANCHOR_MISSING")
    return issues


def _source_status(
    entry: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
    materials: dict[tuple[str, str], dict[str, Any]],
) -> tuple[str, list[str]]:
    issues = validate_source_roles(entry, chunks, materials)
    return ("pass" if not issues else "fail"), issues


def _material_validation(
    *, root: Path, chunks: dict[str, dict[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    try:
        materials = material_index(
            load_course_material_manifest(root / "data" / "course_material_manifest.json")
        )
    except CourseMaterialManifestError as error:
        raise BenchmarkInputError(f"Course material manifest is invalid: {error}") from None
    return materials, validate_chunk_material_coverage(chunks, materials)


def _general_malformed(entry: dict[str, Any]) -> list[Any]:
    if entry["scorer"] == "single_choice_v1":
        # A/B/C/D are historical *stable IDs* for two reviewed templates;
        # a letter is malformed only when it is not an ID in that template.
        return [None, "", " ", [], {}, True, 1, 1.0, "display_letter_not_a_stable_id"]
    if entry["scorer"] == "multiple_choice_v1":
        return [None, "", [], (), {}, True, ["unknown"], ["duplicate", "duplicate"]]
    return [None, "", [], {}, True]


def _run_scoring(template: dict[str, Any], entry: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    try:
        correct = score_verification_answer(template=template, answer=deepcopy(entry["known_correct"]))
        correct_result = {"score": correct["score"], "passed": correct["passed"]}
        if correct_result != {"score": 1.0, "passed": True}:
            failures.append("known_correct did not pass")
    except VerificationDiagnosticError as error:
        correct_result = {"error": str(error)}
        failures.append("known_correct was rejected")
    wrong_count = 0
    for answer in entry["known_wrong"]:
        try:
            result = score_verification_answer(template=template, answer=deepcopy(answer))
            if result["score"] != 0.0 or result["passed"]:
                failures.append("known_wrong passed")
            wrong_count += 1
        except VerificationDiagnosticError:
            failures.append("known_wrong was rejected instead of scored")
    malformed_count = 0
    for answer in [*entry["malformed"], *_general_malformed(entry)]:
        try:
            score_verification_answer(template=template, answer=deepcopy(answer))
        except VerificationDiagnosticError:
            malformed_count += 1
        else:
            failures.append("malformed answer was accepted")
    return {
        "correct_result": correct_result,
        "wrong_result_count": wrong_count,
        "malformed_result_count": malformed_count,
    }, failures


def lint_candidate_document(*, root: Path, candidate_path: Path, production_path: Path) -> dict[str, list[str]]:
    """Perform structural candidate checks without granting production status."""
    errors: list[str] = []
    warnings: list[str] = []
    manual_checks = ["human source/content review", "owner approval", "independent promotion change"]
    try:
        raw = _read_json(candidate_path)
        candidate = load_candidate_document(candidate_path, root=root)
        production_ids = {item["id"] for item in _read_json(production_path)["templates"]}
        chunks = {item["id"]: item for item in _read_json(root / "data" / "course_chunks.json")["chunks"]}
        materials, material_issues = _material_validation(root=root, chunks=chunks)
    except (BenchmarkInputError, OSError, json.JSONDecodeError) as error:
        return {"errors": [str(error)], "warnings": warnings, "manual_checks": manual_checks}
    except (KeyError, TypeError) as error:
        return {"errors": [f"candidate document is invalid: {type(error).__name__}"], "warnings": warnings, "manual_checks": manual_checks}
    if raw.get("candidate_status") == "promoted_to_production":
        if raw.get("templates") or raw.get("acceptance_cases"):
            errors.append("promoted candidate staging must be empty")
        errors.extend(material_issues)
        return {"errors": errors, "warnings": warnings, "manual_checks": manual_checks}
    if raw.get("candidate_status") != "pending_human_review":
        errors.append("candidate_status must be pending_human_review or promoted_to_production")
    for template in candidate["templates"]:
        template_id = template["id"]
        acceptance = candidate["acceptance_cases"].get(template_id, {})
        if template_id in production_ids:
            errors.append(f"{template_id}: collides with production")
        if template["review_status"] != "candidate_draft":
            errors.append(f"{template_id}: candidate must be candidate_draft")
        if len(template["concept_ids"]) != 1:
            errors.append(f"{template_id}: candidate must have one primary concept")
        unknown_intents = sorted(set(template["eligible_intents"]) - KNOWN_DIAGNOSTIC_INTENTS)
        if unknown_intents:
            errors.append(f"{template_id}: unknown eligible intent")
        if template["selection_priority"] < 0:
            errors.append(f"{template_id}: selection_priority must be non-negative")
        required = {"primary_concept_id", "verification_goal", "capability_boundary", "evidence_strength", "source_review_note", "source_refs", "question_type", "deterministic_scorer", "expected_answer_position", "correct_answer", "wrong_answer", "malformed_answer"}
        if not isinstance(acceptance, dict) or not required <= set(acceptance):
            errors.append(f"{template_id}: acceptance case is incomplete")
            continue
        if acceptance["primary_concept_id"] != template["concept_ids"][0]:
            errors.append(f"{template_id}: acceptance primary concept differs")
        if acceptance["question_type"] != template["question_type"] or acceptance["deterministic_scorer"] != template["deterministic_scorer"]:
            errors.append(f"{template_id}: acceptance scorer/type differs")
        if acceptance["correct_answer"] != (template["expected_answer"].get("choice_id") if template["deterministic_scorer"] == "single_choice_v1" else template["expected_answer"].get("choice_ids")):
            errors.append(f"{template_id}: acceptance correct answer differs")
        if not isinstance(acceptance["capability_boundary"], str) or not acceptance["capability_boundary"].strip():
            errors.append(f"{template_id}: capability boundary is missing")
        if acceptance["evidence_strength"] not in {"direct", "supported_inference", "direct_plus_closed_instance"}:
            errors.append(f"{template_id}: evidence strength is invalid")
        source_entry = {
            "bank_type": "candidate",
            "primary_concept": template["concept_ids"][0],
            "source_expectations": acceptance["source_refs"],
            "source_review_note": acceptance["source_review_note"],
        }
        errors.extend(
            f"{template_id}: {issue}"
            for issue in validate_source_roles(source_entry, chunks, materials)
        )
        if template["deterministic_scorer"] == "single_choice_v1":
            ids = [choice["id"] for choice in template["choices"]]
            actual = ids.index(template["expected_answer"]["choice_id"]) + 1
            if acceptance["expected_answer_position"] != actual:
                errors.append(f"{template_id}: answer position metadata differs")
    return {"errors": errors, "warnings": warnings, "manual_checks": manual_checks}


def run_quality_gate(
    *,
    root: Path | None = None,
    production_path: str | Path | None = None,
    candidate_path: str | Path | None = None,
    production_only: bool = False,
    lint_candidate: bool = False,
    promotion_readiness: bool = False,
) -> dict[str, Any]:
    """Run stable read-only checks and return a JSON-safe report dictionary."""
    root = repository_root() if root is None else Path(root)
    production_path = root / "data" / "diagnostic_templates.json" if production_path is None else Path(production_path)
    candidate_path = root / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json" if candidate_path is None else Path(candidate_path)
    manifest = build_manifest(root=root, production_path=production_path, candidate_path=candidate_path)
    production, candidates = _template_data(root=root, production_path=production_path, candidate_path=candidate_path)
    chunks = {item["id"]: item for item in _read_json(root / "data" / "course_chunks.json")["chunks"]}
    materials, material_issues = _material_validation(root=root, chunks=chunks)
    templates = {item["id"]: item for item in production}
    if not production_only:
        templates.update({item["id"]: item for item in candidates})
    entries = list(manifest["production"])
    if not production_only:
        entries.extend(manifest["candidates"])
    report_entries: list[dict[str, Any]] = []
    failures: list[str] = list(material_issues)
    warnings: list[str] = []
    for entry in entries:
        source_status, source_issues = _source_status(entry, chunks, materials)
        scoring, score_failures = _run_scoring(templates[entry["template_id"]], entry)
        item_failures = [*source_issues, *score_failures]
        failures.extend(f"{entry['template_id']}: {item}" for item in item_failures)
        report_entries.append({
            "template_id": entry["template_id"],
            "bank_type": entry["bank_type"],
            "concept": entry["primary_concept"],
            "review_status": entry["review_status"],
            "scorer": entry["scorer"],
            "question_type": entry["question_type"],
            "correct_result": scoring["correct_result"],
            "wrong_result_count": scoring["wrong_result_count"],
            "malformed_result_count": scoring["malformed_result_count"],
            "source_status": source_status,
            "answer_position": entry["expected_answer_position"],
            "eligible_intents": entry["eligible_intents"],
            "capability_boundary": entry["capability_boundary"],
            "status": "pass" if not item_failures else "fail",
            "warnings": [],
            "failures": item_failures,
        })
    production_ids = {item["id"] for item in production}
    candidate_ids = {item["id"] for item in candidates}
    if production_ids & candidate_ids:
        failures.append("Candidate and production IDs collide.")
    candidate_lint = None
    if lint_candidate:
        candidate_lint = lint_candidate_document(root=root, candidate_path=candidate_path, production_path=production_path)
        failures.extend(f"candidate lint: {item}" for item in candidate_lint["errors"])
        warnings.extend(candidate_lint["warnings"])
    positions = [item["expected_answer_position"] for item in manifest["production"] if item["expected_answer_position"]]
    promotion_summary = None
    if promotion_readiness:
        promotion_summary = {
            "source_gate_ready": not bool(candidate_lint and candidate_lint["errors"]),
            "owner_approval_pending": True,
            "promotion_pending": True,
            "automatic_promotion": False,
        }
    return {
        "schema_version": 1,
        "run_metadata": {"mode": "offline", "network": "disabled", "env": "not_read"},
        "production_template_count": len(production),
        "active_candidate_count": 0 if production_only else len(candidates),
        "blocked_slot_count": len(manifest["blocked_slots"]),
        "overall_status": "pass" if not failures else "fail",
        "template_inventory": report_entries,
        "concept_inventory": sorted({item["concept"] for item in report_entries}),
        "scorer_inventory": sorted({item["scorer"] for item in report_entries}),
        "question_type_inventory": sorted({item["question_type"] for item in report_entries}),
        "source_summary": {"pass": sum(item["source_status"] == "pass" for item in report_entries), "fail": sum(item["source_status"] != "pass" for item in report_entries)},
        "material_manifest_summary": {
            "material_count": len(materials),
            "chunk_coverage_issues": material_issues,
        },
        "answer_position_summary": {"positions": positions},
        "eligibility_summary": {"candidate_registered_in_production": bool(production_ids & candidate_ids)},
        "positive_case_summary": {"checked": len(report_entries)},
        "wrong_case_summary": {"checked": sum(item["wrong_result_count"] for item in report_entries)},
        "malformed_case_summary": {"rejected": sum(item["malformed_result_count"] for item in report_entries)},
        "candidate_isolation_summary": {"candidate_ids_visible_to_production": sorted(production_ids & candidate_ids)},
        "candidate_lint": candidate_lint,
        "promotion_readiness": promotion_summary,
        "warnings": warnings,
        "failures": failures,
    }


def markdown_report(report: dict[str, Any]) -> str:
    """Render a compact deterministic human-readable report."""
    lines = [
        "# Verification quality gate report",
        "",
        f"- Overall status: `{report['overall_status']}`",
        f"- Production templates: {report['production_template_count']}",
        f"- Active candidates: {report['active_candidate_count']}",
        f"- Blocked slots: {report['blocked_slot_count']}",
        "",
        "| Template | Bank | Source | Correct | Wrong | Malformed | Status |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for item in report["template_inventory"]:
        result = item["correct_result"]
        correct = "pass" if result == {"score": 1.0, "passed": True} else "fail"
        lines.append(
            f"| {item['template_id']} | {item['bank_type']} | {item['source_status']} | {correct} | {item['wrong_result_count']} | {item['malformed_result_count']} | {item['status']} |"
        )
    if report["warnings"]:
        lines.extend(["", "## Warnings", *[f"- {item}" for item in report["warnings"]]])
    if report["failures"]:
        lines.extend(["", "## Failures", *[f"- {item}" for item in report["failures"]]])
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, default=ROOT / "data" / "diagnostic_templates.json")
    parser.add_argument("--candidates", type=Path, default=ROOT / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json")
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    parser.add_argument("--production-only", action="store_true")
    parser.add_argument("--lint-candidate", action="store_true")
    parser.add_argument("--promotion-readiness", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = run_quality_gate(
            root=ROOT,
            production_path=args.production,
            candidate_path=args.candidates,
            production_only=args.production_only,
            lint_candidate=args.lint_candidate or args.promotion_readiness,
            promotion_readiness=args.promotion_readiness,
        )
    except (BenchmarkInputError, OSError, json.JSONDecodeError) as error:
        print(f"quality-gate input error: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except Exception as error:  # defensive CLI boundary; no sensitive inputs are rendered
        print(f"quality-gate internal error: {type(error).__name__}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    try:
        if args.json_report:
            args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rendered = markdown_report(report)
        if args.markdown_report:
            args.markdown_report.write_text(rendered, encoding="utf-8")
    except OSError as error:
        print(f"quality-gate report error: {type(error).__name__}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    if args.promotion_readiness:
        print("promotion readiness: structural checks complete; content review and owner approval remain pending")
    else:
        print(rendered, end="")
    if report["failures"]:
        return EXIT_QUALITY_FAILURE
    if args.strict and report["warnings"] and not args.lint_candidate and not args.promotion_readiness:
        return EXIT_STRICT_WARNING
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
