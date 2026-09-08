"""Offline regression benchmark for the bounded diagnostic scorer.

The data records human-reviewed semantic expectations.  The runner never
loads configuration, creates an adapter, or accesses a network; callers may
inject a fake adjudicator to exercise the same bounded semantic boundary used
by production.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
from typing import Any
import json

from introai_tutor.assessment import assess_structured_answer


class DiagnosticBenchmarkError(ValueError):
    """Raised when a diagnostic scoring benchmark is malformed."""


_CASE_FIELDS = {
    "question_id",
    "case_id",
    "category",
    "answer",
    "expected_required_criteria",
    "expected_missing_criteria",
    "expected_misconception_ids",
    "expected_passed",
    "expected_mastery_score",
    "expected_semantic_trigger",
    "review_status",
}
_OPTIONAL_CASE_FIELDS = {
    "fake_semantic_judgments",
    "fake_semantic_confidence",
    "expected_authoritative_outcome",
    "expected_assistance_level",
}
_AUTHORITATIVE_OUTCOMES = {"pass", "clarify", "fail", "unresolved"}
_ASSISTANCE_LEVELS = {"none", "hint", "scaffold", "clarification", "reveal"}


def load_diagnostic_scoring_benchmark(path: str | Path) -> dict[str, Any]:
    """Load and validate a human-reviewed benchmark document."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise DiagnosticBenchmarkError(f"Unable to load benchmark: {error}") from None
    return _validate_benchmark(raw)


def run_diagnostic_scoring_benchmark(
    *,
    questions_data: dict[str, Any],
    benchmark_data: dict[str, Any],
    semantic_adjudicator: Any | None = None,
) -> dict[str, Any]:
    """Run all benchmark cases and return case-level diffs plus aggregates."""
    benchmark = _validate_benchmark(benchmark_data)
    questions = _question_index(questions_data)
    records: list[dict[str, Any]] = []
    for case in benchmark["cases"]:
        try:
            question = questions[case["question_id"]]
        except KeyError as error:
            raise DiagnosticBenchmarkError(
                f"benchmark references unknown question_id: {case['question_id']}"
            ) from error
        assessment = question.get("assessment")
        if not isinstance(assessment, dict):
            raise DiagnosticBenchmarkError(
                f"benchmark question has no structured assessment: {case['question_id']}"
            )
        _validate_case_against_assessment(case, assessment)
        actual = assess_structured_answer(
            case["answer"],
            assessment,
            semantic_adjudicator=semantic_adjudicator,
            question_context=question.get("question_text"),
        )
        differences = _differences(case, actual)
        records.append(
            {
                "case_id": case["case_id"],
                "question_id": case["question_id"],
                "category": case["category"],
                "expected": _public_expected(case),
                "actual": _public_actual(actual),
                "differences": differences,
                "matched": not differences,
            }
        )
    return {
        "benchmark_id": benchmark["benchmark_id"],
        "cases": records,
        "summary": _summarize(records),
    }


class BenchmarkFakeSemanticAdjudicator:
    """Fixture-grade injected adjudicator backed solely by benchmark metadata."""

    def __init__(self, *, benchmark_data: dict[str, Any]) -> None:
        benchmark = _validate_benchmark(benchmark_data)
        self._responses = {
            case["answer"]: {
                "judgments": deepcopy(case.get("fake_semantic_judgments", [])),
                "confidence": float(case.get("fake_semantic_confidence", 0.9)),
            }
            for case in benchmark["cases"]
        }
        self.calls: list[dict[str, Any]] = []

    def adjudicate(
        self,
        *,
        answer: str,
        criteria: list[dict[str, str]],
        question_context: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "answer": answer,
                "criteria": deepcopy(criteria),
                "question_context": question_context,
            }
        )
        try:
            return deepcopy(self._responses[answer])
        except KeyError as error:
            raise DiagnosticBenchmarkError("fake semantic response is missing for answer") from error


def _validate_benchmark(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "benchmark_id",
        "cases",
    }:
        raise DiagnosticBenchmarkError("benchmark has an invalid schema.")
    if value["schema_version"] != 1:
        raise DiagnosticBenchmarkError("benchmark schema_version must be 1.")
    if not isinstance(value["benchmark_id"], str) or not value["benchmark_id"].strip():
        raise DiagnosticBenchmarkError("benchmark_id must be a non-empty string.")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise DiagnosticBenchmarkError("benchmark cases must be a non-empty list.")
    normalized: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not _CASE_FIELDS <= set(case) or not set(case) <= (
            _CASE_FIELDS | _OPTIONAL_CASE_FIELDS
        ):
            raise DiagnosticBenchmarkError(f"benchmark case {index} has an invalid schema.")
        for field in ("question_id", "case_id", "category", "answer"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise DiagnosticBenchmarkError(f"benchmark case {index}.{field} must be non-empty.")
        if case["case_id"] in case_ids:
            raise DiagnosticBenchmarkError("benchmark case_id values must be unique.")
        case_ids.add(case["case_id"])
        for field in (
            "expected_required_criteria",
            "expected_missing_criteria",
            "expected_misconception_ids",
        ):
            _validate_string_ids(case[field], f"benchmark case {index}.{field}")
        if isinstance(case["expected_passed"], bool) is False:
            raise DiagnosticBenchmarkError(f"benchmark case {index}.expected_passed must be bool.")
        score = case["expected_mastery_score"]
        if isinstance(score, bool) or not isinstance(score, int | float):
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.expected_mastery_score must be a number."
            )
        if not math.isfinite(float(score)) or not 0.0 <= float(score) <= 1.0:
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.expected_mastery_score must be between 0 and 1."
            )
        if not isinstance(case["expected_semantic_trigger"], bool):
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.expected_semantic_trigger must be bool."
            )
        authoritative_outcome = case.get("expected_authoritative_outcome")
        if authoritative_outcome is not None and authoritative_outcome not in _AUTHORITATIVE_OUTCOMES:
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.expected_authoritative_outcome is invalid."
            )
        assistance_level = case.get("expected_assistance_level")
        if assistance_level is not None and assistance_level not in _ASSISTANCE_LEVELS:
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.expected_assistance_level is invalid."
            )
        if case["review_status"] != "human_verified":
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.review_status must be human_verified."
            )
        judgments = case.get("fake_semantic_judgments")
        if judgments is not None:
            if not isinstance(judgments, list):
                raise DiagnosticBenchmarkError(
                    f"benchmark case {index}.fake_semantic_judgments must be a list."
                )
            for judgment in judgments:
                if not isinstance(judgment, dict) or set(judgment) != {
                    "criterion_id",
                    "status",
                } or not isinstance(judgment["criterion_id"], str) or judgment[
                    "status"
                ] not in {"entailed", "contradicted", "not_mentioned"}:
                    raise DiagnosticBenchmarkError(
                        f"benchmark case {index}.fake_semantic_judgments is invalid."
                    )
        confidence = case.get("fake_semantic_confidence", 0.9)
        if isinstance(confidence, bool) or not isinstance(confidence, int | float):
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.fake_semantic_confidence must be numeric."
            )
        if not math.isfinite(float(confidence)) or not 0.0 <= float(confidence) <= 1.0:
            raise DiagnosticBenchmarkError(
                f"benchmark case {index}.fake_semantic_confidence must be between 0 and 1."
            )
        normalized.append(deepcopy(case))
    return {
        "schema_version": 1,
        "benchmark_id": value["benchmark_id"].strip(),
        "cases": normalized,
    }


def _validate_string_ids(value: Any, name: str) -> None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ) or len(value) != len(set(value)):
        raise DiagnosticBenchmarkError(f"{name} must be a unique string list.")


def _question_index(questions_data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(questions_data, dict) or not isinstance(
        questions_data.get("diagnostic_questions"), list
    ):
        raise DiagnosticBenchmarkError("questions_data has an invalid schema.")
    index: dict[str, dict[str, Any]] = {}
    for question in questions_data["diagnostic_questions"]:
        if not isinstance(question, dict) or not isinstance(question.get("id"), str):
            raise DiagnosticBenchmarkError("questions_data contains an invalid question.")
        if question["id"] in index:
            raise DiagnosticBenchmarkError("questions_data contains duplicate question IDs.")
        index[question["id"]] = question
    return index


def _validate_case_against_assessment(case: dict[str, Any], assessment: dict[str, Any]) -> None:
    """Reject stale human expectations that do not name this rubric's IDs."""
    required_groups = assessment.get("required_groups")
    misconceptions = assessment.get("blocking_misconceptions")
    if not isinstance(required_groups, list) or not isinstance(misconceptions, list):
        raise DiagnosticBenchmarkError(
            f"benchmark question has an invalid assessment: {case['question_id']}"
        )
    required_ids = [group.get("id") for group in required_groups if isinstance(group, dict)]
    misconception_ids = [item.get("id") for item in misconceptions if isinstance(item, dict)]
    expected_required = case["expected_required_criteria"]
    expected_missing = case["expected_missing_criteria"]
    if set(expected_required) | set(expected_missing) != set(required_ids) or set(
        expected_required
    ) & set(expected_missing):
        raise DiagnosticBenchmarkError(
            f"benchmark criterion expectation does not cover {case['question_id']} exactly."
        )
    if expected_required != [item for item in required_ids if item in expected_required]:
        raise DiagnosticBenchmarkError(
            f"benchmark required criterion order is invalid for {case['case_id']}."
        )
    if expected_missing != [item for item in required_ids if item in expected_missing]:
        raise DiagnosticBenchmarkError(
            f"benchmark missing criterion order is invalid for {case['case_id']}."
        )
    if any(item not in misconception_ids for item in case["expected_misconception_ids"]):
        raise DiagnosticBenchmarkError(
            f"benchmark misconception expectation is invalid for {case['case_id']}."
        )


def _differences(case: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    if (
        actual["matched_required_group_ids"] != case["expected_required_criteria"]
        or actual["missing_required_group_ids"] != case["expected_missing_criteria"]
    ):
        differences["criterion_recognition"] = {
            "expected_required": list(case["expected_required_criteria"]),
            "actual_required": list(actual["matched_required_group_ids"]),
            "expected_missing": list(case["expected_missing_criteria"]),
            "actual_missing": list(actual["missing_required_group_ids"]),
        }
    if actual["misconception_ids"] != case["expected_misconception_ids"]:
        differences["misconception"] = {
            "expected": list(case["expected_misconception_ids"]),
            "actual": list(actual["misconception_ids"]),
        }
    if actual["passed"] is not case["expected_passed"]:
        differences["pass_fail"] = {
            "expected": case["expected_passed"],
            "actual": actual["passed"],
        }
    if not math.isclose(
        actual["mastery_score"], case["expected_mastery_score"], abs_tol=1e-9
    ):
        differences["mastery_evidence"] = {
            "expected": case["expected_mastery_score"],
            "actual": actual["mastery_score"],
        }
    if actual["semantic_trigger_eligible"] is not case["expected_semantic_trigger"]:
        differences["semantic_trigger"] = {
            "expected": case["expected_semantic_trigger"],
            "actual": actual["semantic_trigger_eligible"],
            "reason": actual["semantic_eligibility_reason"],
        }
    return differences


def _public_expected(case: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: deepcopy(case[key])
        for key in (
            "expected_required_criteria",
            "expected_missing_criteria",
            "expected_misconception_ids",
            "expected_passed",
            "expected_mastery_score",
            "expected_semantic_trigger",
        )
    }
    for key in ("expected_authoritative_outcome", "expected_assistance_level"):
        if key in case:
            public[key] = deepcopy(case[key])
    return public


def _public_actual(actual: dict[str, Any]) -> dict[str, Any]:
    return {
        "required_criteria": list(actual["matched_required_group_ids"]),
        "missing_criteria": list(actual["missing_required_group_ids"]),
        "misconception_ids": list(actual["misconception_ids"]),
        "passed": actual["passed"],
        "mastery_score": actual["mastery_score"],
        "semantic_trigger_eligible": actual["semantic_trigger_eligible"],
        "semantic_eligibility_reason": actual["semantic_eligibility_reason"],
        "semantic_trigger_reason": actual["semantic_trigger_reason"],
        "semantic_used": actual["semantic_used"],
        "semantic_applied": actual["semantic_applied"],
        "semantic_abstain_reason": actual["semantic_abstain_reason"],
    }


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_question: dict[str, dict[str, int]] = {}
    by_category: dict[str, dict[str, int]] = {}
    error_counts = {
        "criterion_recognition": 0,
        "misconception": 0,
        "pass_fail": 0,
        "mastery_evidence": 0,
        "semantic_trigger": 0,
    }
    for record in records:
        for bucket, key in ((by_question, record["question_id"]), (by_category, record["category"])):
            stats = bucket.setdefault(key, {"cases": 0, "matched": 0})
            stats["cases"] += 1
            stats["matched"] += int(record["matched"])
        for name in error_counts:
            error_counts[name] += int(name in record["differences"])
    return {
        "case_count": len(records),
        "matched_case_count": sum(record["matched"] for record in records),
        "by_question": by_question,
        "by_category": by_category,
        "error_counts": error_counts,
    }
