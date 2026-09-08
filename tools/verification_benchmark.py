"""Build the single, derived benchmark view for reviewed verification banks.

The production template loader, scorer, and selector remain authoritative.
This module joins those data with the existing acceptance contracts so offline
quality tooling does not maintain a second bank of question content.
"""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from typing import Any

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import load_diagnostic_templates, validate_diagnostic_templates


BLOCKED_SLOTS = (
    {
        "proposed_template_id": "verify_ucs_frontier_update_v1",
        "concept": "uniform_cost_search",
        "blocked_reason": "The reviewed project subset does not directly support a safe frontier lower-cost-update item.",
        "missing_evidence": "A source page that explicitly specifies replacement or decrease-key behavior for a lower-cost duplicate frontier path.",
        "source_pages_reviewed": ["ai_lec2_uninformed_search.pdf:60-63"],
        "prohibited_fallback_knowledge": "Do not infer implementation-specific UCS frontier-update behavior from general textbook knowledge.",
    },
)

_KNOWN_INTENTS = (
    "definition", "explanation", "comparison", "algorithm_trace", "property", "diagnostic_request",
)


class BenchmarkInputError(ValueError):
    """Raised when a benchmark source cannot be loaded or reconciled."""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _acceptance_cases(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "tests" / "template_acceptance_cases.py"
    spec = importlib.util.spec_from_file_location("p2g_acceptance_cases", path)
    if spec is None or spec.loader is None:
        raise BenchmarkInputError("Cannot load production acceptance contracts.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = getattr(module, "PRODUCTION_TEMPLATE_ACCEPTANCE_CASES", None)
    if not isinstance(cases, dict):
        raise BenchmarkInputError("Production acceptance contracts are invalid.")
    return deepcopy(cases)


def _concept_ids(root: Path) -> set[str]:
    document = load_knowledge_points(root / "data" / "knowledge_points.json")
    return {point["id"] for point in document["knowledge_points"]}


def load_candidate_document(path: str | Path, *, root: Path | None = None) -> dict[str, Any]:
    """Load only a staging document and validate its template payload strictly."""
    root = repository_root() if root is None else Path(root)
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise BenchmarkInputError(f"Candidate file is missing: {Path(path)}") from error
    except json.JSONDecodeError as error:
        raise BenchmarkInputError("Candidate file is not valid JSON.") from error
    required = {"schema_version", "candidate_batch_id", "candidate_status", "templates", "acceptance_cases"}
    if not isinstance(document, dict) or set(document) != required:
        raise BenchmarkInputError("Candidate document has an invalid top-level schema.")
    if document["schema_version"] != 1:
        raise BenchmarkInputError("Unsupported candidate schema_version.")
    status = document["candidate_status"]
    if status == "promoted_to_production":
        if document["templates"] != [] or document["acceptance_cases"] != {}:
            raise BenchmarkInputError("Promoted candidate staging must be empty.")
        return deepcopy(document)
    if status != "pending_human_review":
        raise BenchmarkInputError("Candidate document has an unsupported status.")
    template_document = {"schema_version": document["schema_version"], "templates": document["templates"]}
    try:
        validate_diagnostic_templates(
            template_document,
            valid_concept_ids=_concept_ids(root),
            allowed_review_statuses={"candidate_draft"},
        )
    except ValueError as error:
        raise BenchmarkInputError(f"Candidate template validation failed: {error}") from None
    if not isinstance(document["acceptance_cases"], dict):
        raise BenchmarkInputError("Candidate acceptance_cases must be an object.")
    template_ids = {template["id"] for template in document["templates"]}
    if set(document["acceptance_cases"]) != template_ids:
        raise BenchmarkInputError("Candidate acceptance cases do not match candidate templates.")
    return deepcopy(document)


def _negative_intent(eligible: list[str]) -> str:
    return next((intent for intent in _KNOWN_INTENTS if intent not in eligible), "out_of_scope")


def _answer_position(template: dict[str, Any]) -> int | None:
    if template["deterministic_scorer"] != "single_choice_v1":
        return None
    choice_ids = [choice["id"] for choice in template["choices"]]
    return choice_ids.index(template["expected_answer"]["choice_id"]) + 1


def _entry(
    template: dict[str, Any],
    *,
    bank_type: str,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    correct = deepcopy(acceptance["correct_answer"])
    wrong = [deepcopy(acceptance["wrong_answer"])]
    wrong.extend(deepcopy(acceptance.get("additional_wrong_answers", [])))
    malformed = [deepcopy(acceptance.get("malformed_answer"))]
    malformed = [value for value in malformed if value not in (None, [])]
    return {
        "template_id": template["id"],
        "bank_type": bank_type,
        "review_status": template["review_status"],
        "primary_concept": acceptance["primary_concept_id"],
        # Every template ``concept_ids`` member is an evidence target.  A
        # supporting topic is a QA-role concept, not a second template target;
        # keeping this empty prevents the audit from mislabeling validated
        # multi-concept evidence as supporting-only routing.
        "supporting_topics": [],
        "question_type": template["question_type"],
        "scorer": template["deterministic_scorer"],
        "known_correct": correct,
        "known_wrong": wrong,
        "malformed": malformed,
        "source_expectations": deepcopy(acceptance["source_refs"]),
        "source_review_note": acceptance.get("source_review_note", ""),
        "evidence_strength": acceptance.get("evidence_strength"),
        "expected_answer_position": _answer_position(template),
        "eligible_intents": list(template["eligible_intents"]),
        "explicit_negative_intents": [_negative_intent(template["eligible_intents"])],
        "evidence_expectation": "evidence_eligible" if bank_type == "production" else "candidate_not_eligible",
        "ui_availability": template["question_type"] in {"single_choice", "multiple_choice"},
        "capability_boundary": acceptance.get(
            "capability_boundary", template["teaching_support"]["explanation"]
        ),
    }


def build_manifest(
    *,
    root: Path | None = None,
    production_path: str | Path | None = None,
    candidate_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a stable derived manifest for the current P2g bank inventory."""
    root = repository_root() if root is None else Path(root)
    production_path = root / "data" / "diagnostic_templates.json" if production_path is None else Path(production_path)
    candidate_path = root / "data" / "candidate_templates" / "search_algorithms_p5b_candidates.json" if candidate_path is None else Path(candidate_path)
    concepts = _concept_ids(root)
    production = load_diagnostic_templates(production_path, valid_concept_ids=concepts)
    candidates = load_candidate_document(candidate_path, root=root)
    production_cases = _acceptance_cases(root)
    production_ids = {template["id"] for template in production["templates"]}
    if set(production_cases) != production_ids:
        raise BenchmarkInputError("Production acceptance cases do not match production templates.")
    candidate_ids = {template["id"] for template in candidates["templates"]}
    if production_ids & candidate_ids:
        raise BenchmarkInputError("Candidate template IDs collide with production templates.")
    return {
        "schema_version": 1,
        "manifest_source": "derived_from_production_loader_and_existing_acceptance_contracts",
        "production": [
            _entry(template, bank_type="production", acceptance=production_cases[template["id"]])
            for template in production["templates"]
        ],
        "candidates": [
            _entry(template, bank_type="candidate", acceptance=candidates["acceptance_cases"][template["id"]])
            for template in candidates["templates"]
        ],
        "blocked_slots": deepcopy(list(BLOCKED_SLOTS)),
    }
