"""Validate P7 research-only external-assessment candidates offline.

The production diagnostic registry, selector, scorer and learner-state services
do not import this module.  It validates only a pending-owner-review research
artifact and never creates learner evidence or writes a database.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.knowledge import load_knowledge_points  # noqa: E402
from introai_tutor.template_selection import load_diagnostic_templates  # noqa: E402
from tools.verification_benchmark import build_manifest  # noqa: E402


CANDIDATE_PATH = ROOT / "data" / "evaluation" / "p7_external_assessment_candidates.json"
_ITEM_KEYS = {
    "assessment_item_id",
    "concept_id",
    "capability_slice",
    "question_type",
    "stem",
    "choices",
    "expected_answer",
    "source_refs",
    "production_overlap_analysis",
    "difficulty_rationale",
    "measures",
    "does_not_measure",
    "second_reasonable_answer_audit",
    "independence_rationale",
    "human_review_status",
}
_TOP_LEVEL_KEYS = {"schema_version", "assessment_status", "study_scope", "items"}
_ID_PATTERN = re.compile(r"^p7_ext_[a-z0-9_]+$")


class P7CandidateValidationError(ValueError):
    """Raised when a research-only candidate document is malformed."""


def load_p7_candidate_document(path: str | Path = CANDIDATE_PATH) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise P7CandidateValidationError("P7 external candidate document is missing.") from error
    except json.JSONDecodeError as error:
        raise P7CandidateValidationError("P7 external candidate document is invalid JSON.") from error
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        raise P7CandidateValidationError("P7 external candidate document has an invalid top-level schema.")
    return document


def build_production_capability_map(root: Path = ROOT) -> list[dict[str, Any]]:
    """Derive a compact capability map from the real reviewed bank and registry."""
    root = Path(root)
    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
    manifest = build_manifest(root=root)
    by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest["production"]:
        by_concept[row["primary_concept"]].append(row)
    result = []
    for point in knowledge["knowledge_points"]:
        concept_id = point["id"]
        entries = by_concept.get(concept_id, [])
        if not entries:
            feasibility = "DO_NOT_USE"
            reason = "No direct primary production evidence opportunity exists, so estimator alignment cannot be studied cleanly."
        elif len(entries) >= 2:
            feasibility = "HIGH_FEASIBILITY"
            reason = "Multiple reviewed production capability opportunities exist."
        else:
            feasibility = "MEDIUM_FEASIBILITY"
            reason = "One reviewed production capability opportunity exists; a parallel external form needs heightened owner review."
        result.append(
            {
                "concept_id": concept_id,
                "production_template_count": len(entries),
                "production_capability_slices": [entry["capability_boundary"] for entry in entries],
                "source_evidence": [entry["source_expectations"] for entry in entries],
                "current_mastery_evidence_type": "reviewed_completed_unassisted_formal_signal" if entries else "none",
                "possible_external_assessment_construct": "independent course-grounded closed parallel/complementary item" if entries else "EXTERNAL_CRITERION_BLOCKED",
                "circularity_risk": "requires parallel-form audit" if entries else "not_applicable_without_primary_evidence",
                "external_assessment_feasibility": feasibility,
                "feasibility_reason": reason,
            }
        )
    return result


def validate_p7_candidate_document(
    *, root: Path = ROOT, path: str | Path = CANDIDATE_PATH
) -> dict[str, Any]:
    """Return deterministic errors and a derived capability-map summary."""
    root = Path(root)
    document = load_p7_candidate_document(path)
    errors: list[str] = []
    if document["schema_version"] != 1:
        errors.append("schema_version must be 1")
    if document["assessment_status"] != "pending_owner_review":
        errors.append("assessment_status must remain pending_owner_review")
    scope = document["study_scope"]
    required_scope = {
        "study_id", "purpose", "selected_concept_ids", "policy_comparison", "external_item_visibility"
    }
    if not isinstance(scope, dict) or set(scope) != required_scope:
        errors.append("study_scope has an invalid schema")
        scope = {}
    if scope.get("purpose") != "RESEARCH_ASSESSMENT_ONLY":
        errors.append("study_scope must be RESEARCH_ASSESSMENT_ONLY")
    if scope.get("external_item_visibility") != "not_registered_in_production":
        errors.append("external candidate visibility must remain outside production")

    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
    concept_ids = {point["id"] for point in knowledge["knowledge_points"]}
    templates = load_diagnostic_templates(
        root / "data" / "diagnostic_templates.json", valid_concept_ids=concept_ids
    )["templates"]
    production_ids = {item["id"] for item in templates}
    production_stems = {item["prompt"].strip() for item in templates}
    production_choice_text_sets = {
        frozenset(choice["text"].strip() for choice in item["choices"])
        for item in templates
    }
    chunks = {
        item["id"]: item
        for item in json.loads((root / "data" / "course_chunks.json").read_text(encoding="utf-8"))["chunks"]
    }

    selected = scope.get("selected_concept_ids", [])
    if not isinstance(selected, list) or len(selected) < 5 or len(selected) > 8:
        errors.append("study_scope.selected_concept_ids must contain 5 to 8 concepts")
    elif len(selected) != len(set(selected)) or any(value not in concept_ids for value in selected):
        errors.append("study_scope.selected_concept_ids contains unknown or duplicate concepts")
    if scope.get("policy_comparison") != [
        "CURRENT_FIXED_STEP", "PRIOR_REGULARIZED_BERNOULLI", "COUNT_DECAYED_STEP"
    ]:
        errors.append("policy_comparison must freeze P0, P2 and P3 in this order")

    items = document["items"]
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        items = []
    ids: set[str] = set()
    per_concept: dict[str, int] = defaultdict(int)
    independent_count = 0
    too_similar_count = 0
    for index, item in enumerate(items):
        label = f"items[{index}]"
        if not isinstance(item, dict) or set(item) != _ITEM_KEYS:
            errors.append(f"{label} has an invalid schema")
            continue
        item_id = item["assessment_item_id"]
        if not isinstance(item_id, str) or not _ID_PATTERN.fullmatch(item_id):
            errors.append(f"{label}.assessment_item_id is invalid")
        if isinstance(item_id, str) and (item_id in ids or item_id in production_ids):
            errors.append(f"{label}.assessment_item_id collides or duplicates")
        ids.add(item_id)
        concept_id = item["concept_id"]
        if concept_id not in selected:
            errors.append(f"{label}.concept_id is outside selected study scope")
        per_concept[concept_id] += 1
        if item["question_type"] != "single_choice":
            errors.append(f"{label}.question_type must be deterministic single_choice")
        if not isinstance(item["stem"], str) or not item["stem"].strip():
            errors.append(f"{label}.stem must be non-empty")
        elif item["stem"].strip() in production_stems:
            errors.append(f"{label}.stem duplicates a production prompt")
        choices = item["choices"]
        if not isinstance(choices, list) or len(choices) < 3:
            errors.append(f"{label}.choices must contain at least three choices")
            choice_ids: set[str] = set()
        else:
            choice_ids = set()
            for choice in choices:
                if not isinstance(choice, dict) or set(choice) != {"id", "text"} or not isinstance(choice["id"], str) or not choice["id"].strip() or not isinstance(choice["text"], str) or not choice["text"].strip():
                    errors.append(f"{label}.choices has an invalid choice")
                    continue
                if choice["id"] in choice_ids:
                    errors.append(f"{label}.choices has duplicate IDs")
                choice_ids.add(choice["id"])
        expected = item["expected_answer"]
        if not isinstance(expected, dict) or set(expected) != {"choice_id"} or expected.get("choice_id") not in choice_ids:
            errors.append(f"{label}.expected_answer must select one declared choice")
        elif frozenset(choice["text"].strip() for choice in choices) in production_choice_text_sets:
            errors.append(f"{label}.choices duplicates a production option set")
        overlap = item["production_overlap_analysis"]
        if not isinstance(overlap, dict) or set(overlap) != {"production_template_ids", "classification", "risk", "rationale"}:
            errors.append(f"{label}.production_overlap_analysis is invalid")
        else:
            template_ids = overlap["production_template_ids"]
            if not isinstance(template_ids, list) or not template_ids or any(value not in production_ids for value in template_ids):
                errors.append(f"{label}.production overlap must name known production templates")
            classification = overlap["classification"]
            if classification not in {"INDEPENDENT_CAPABILITY_SAMPLE", "COMPLEMENTARY_CAPABILITY", "TOO_SIMILAR", "CIRCULAR"}:
                errors.append(f"{label}.overlap classification is invalid")
            elif classification in {"TOO_SIMILAR", "CIRCULAR"}:
                too_similar_count += 1
            else:
                independent_count += 1
        refs = item["source_refs"]
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}.source_refs must be non-empty")
        else:
            for ref in refs:
                if not isinstance(ref, dict) or set(ref) != {"chunk_id", "source_file", "page_start", "page_end"}:
                    errors.append(f"{label}.source_refs has invalid schema")
                    continue
                chunk = chunks.get(ref["chunk_id"])
                if chunk is None:
                    errors.append(f"{label}.source_refs contains unknown chunk")
                    continue
                if (
                    chunk["source_file"] != ref["source_file"]
                    or not isinstance(ref["page_start"], int)
                    or not isinstance(ref["page_end"], int)
                    or ref["page_start"] > ref["page_end"]
                    or ref["page_start"] < chunk["page_start"]
                    or ref["page_end"] > chunk["page_end"]
                ):
                    errors.append(f"{label}.source_refs does not match its course chunk")
        for text_key in (
            "capability_slice", "difficulty_rationale", "measures", "does_not_measure",
            "second_reasonable_answer_audit", "independence_rationale",
        ):
            if not isinstance(item[text_key], str) or not item[text_key].strip():
                errors.append(f"{label}.{text_key} must be non-empty")
        if item["human_review_status"] != "pending_owner_review":
            errors.append(f"{label}.human_review_status must remain pending_owner_review")
    if set(per_concept) != set(selected) or any(per_concept[concept] < 1 for concept in selected if concept in per_concept):
        errors.append("each selected concept requires at least one external candidate item")

    capability_map = build_production_capability_map(root)
    return {
        "valid": not errors,
        "errors": errors,
        "summary": {
            "item_count": len(items),
            "selected_concept_count": len(selected) if isinstance(selected, list) else 0,
            "independent_or_complementary_item_count": independent_count,
            "too_similar_or_circular_item_count": too_similar_count,
            "external_criterion_blocked_concept_count": sum(
                row["external_assessment_feasibility"] == "DO_NOT_USE" for row in capability_map
            ),
            "production_template_id_collisions": sorted(ids & production_ids),
        },
        "capability_map": capability_map,
    }


if __name__ == "__main__":
    report = validate_p7_candidate_document()
    print(json.dumps({"valid": report["valid"], "errors": report["errors"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)
