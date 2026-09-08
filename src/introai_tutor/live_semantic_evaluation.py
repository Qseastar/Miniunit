"""Controlled, report-only evaluation of the production semantic adjudicator.

This module intentionally delegates scoring to :func:`assess_structured_answer`.
It neither duplicates rubric logic nor creates an adapter: the command-line
entrypoint supplies the already configured production adapter/adjudicator.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import time
from typing import Any

from introai_tutor.assessment import assess_structured_answer
from introai_tutor.deepseek_adapter import DeepSeekRequestError, DeepSeekResponseError
from introai_tutor.diagnostic_benchmark import (
    run_diagnostic_scoring_benchmark,
)
from introai_tutor.diagnostic_semantics import DiagnosticSemanticAdjudicationError


class LiveSemanticEvaluationError(ValueError):
    """Raised for invalid, non-network evaluator inputs."""


class _RecordingAdjudicator:
    """Capture only safe request metadata while preserving production errors."""

    def __init__(self, adjudicator: Any) -> None:
        if not callable(getattr(adjudicator, "adjudicate", None)):
            raise LiveSemanticEvaluationError(
                "semantic_adjudicator must provide a callable adjudicate method."
            )
        self._adjudicator = adjudicator
        self.call_count = 0
        self.elapsed_seconds = 0.0
        self.errors: list[str] = []

    def adjudicate(
        self,
        *,
        answer: str,
        criteria: list[dict[str, str]],
        question_context: str | None = None,
    ) -> dict[str, Any]:
        self.call_count += 1
        started = time.monotonic()
        try:
            return self._adjudicator.adjudicate(
                answer=answer,
                criteria=criteria,
                question_context=question_context,
            )
        except Exception as error:
            self.errors.append(_safe_error_kind(error))
            raise
        finally:
            self.elapsed_seconds += time.monotonic() - started


def select_live_semantic_cases(
    benchmark_data: dict[str, Any],
    *,
    case_ids: list[str] | tuple[str, ...] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Select explicit cases, or the human-marked semantic boundary by default."""
    cases = _validated_cases(benchmark_data)
    if case_ids is not None:
        if not isinstance(case_ids, (list, tuple)) or not case_ids or not all(
            isinstance(case_id, str) and case_id.strip() for case_id in case_ids
        ):
            raise LiveSemanticEvaluationError("case_ids must be non-empty strings.")
        requested = list(case_ids)
        if len(requested) != len(set(requested)):
            raise LiveSemanticEvaluationError("case_ids must be unique.")
        available = {case["case_id"] for case in cases}
        unknown = sorted(set(requested) - available)
        if unknown:
            raise LiveSemanticEvaluationError("Unknown benchmark case_id: " + ", ".join(unknown))
        selected = [case for case in cases if case["case_id"] in set(requested)]
    else:
        selected = [case for case in cases if case["expected_semantic_trigger"]]
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise LiveSemanticEvaluationError("limit must be a positive integer.")
        selected = selected[:limit]
    return deepcopy(selected)


def evaluate_live_semantics(
    *,
    questions_data: dict[str, Any],
    benchmark_data: dict[str, Any],
    semantic_adjudicator: Any,
    case_ids: list[str] | tuple[str, ...] | None = None,
    limit: int | None = None,
    repeat: int = 1,
) -> dict[str, Any]:
    """Evaluate selected assessments with an injected production adjudicator.

    ``repeat`` is deliberately one by default.  Values above one are explicit
    operator choices and each repeat still makes at most one adjudicator call
    for its individual assessment.
    """
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat <= 0:
        raise LiveSemanticEvaluationError("repeat must be a positive integer.")
    benchmark = deepcopy(benchmark_data)
    # The established offline runner validates the document and gives us the
    # production trigger signal for all 36 cases without creating an adapter.
    baseline_report = run_diagnostic_scoring_benchmark(
        questions_data=questions_data, benchmark_data=benchmark
    )
    baseline_by_id = {record["case_id"]: record for record in baseline_report["cases"]}
    selected = select_live_semantic_cases(benchmark, case_ids=case_ids, limit=limit)
    questions = _question_index(questions_data)
    records: list[dict[str, Any]] = []
    for case in selected:
        question = questions[case["question_id"]]
        assessment = question.get("assessment")
        if not isinstance(assessment, dict):
            raise LiveSemanticEvaluationError(
                f"Benchmark question has no structured assessment: {case['question_id']}"
            )
        for repeat_index in range(repeat):
            records.append(
                _evaluate_one(
                    case=case,
                    question=question,
                    assessment=assessment,
                    semantic_adjudicator=semantic_adjudicator,
                    repeat_index=repeat_index + 1,
                    deterministic_actual=baseline_by_id[case["case_id"]]["actual"],
                )
            )
    return {
        "report_schema_version": 2,
        "benchmark_id": baseline_report["benchmark_id"],
        "selection": {
            "case_ids": [case["case_id"] for case in selected],
            "repeat": repeat,
            "default_semantic_boundary_selection": case_ids is None,
        },
        "trigger_metrics": _trigger_metrics(baseline_report["cases"]),
        "records": records,
        "summary": _summary(records),
    }


def write_live_semantic_report(report: dict[str, Any], path: str | Path) -> Path:
    """Write a local JSON report without including prompts or adapter headers."""
    destination = Path(path)
    if not destination.parent.is_dir():
        raise LiveSemanticEvaluationError("report directory does not exist.")
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return destination


def _evaluate_one(
    *,
    case: dict[str, Any],
    question: dict[str, Any],
    assessment: dict[str, Any],
    semantic_adjudicator: Any,
    repeat_index: int,
    deterministic_actual: dict[str, Any],
) -> dict[str, Any]:
    recorder = _RecordingAdjudicator(semantic_adjudicator)
    started = time.monotonic()
    final = assess_structured_answer(
        case["answer"],
        assessment,
        semantic_adjudicator=recorder,
        question_context=question.get("question_text"),
    )
    elapsed = time.monotonic() - started
    actual = _public_final(final)
    semantic_expected = _semantic_expected(case)
    authoritative_expected = _authoritative_expected(case)
    actual_outcome = _authoritative_outcome(final)
    actual_advisory = final["semantic_status"] == "advisory"
    differences = _authoritative_differences(
        expected=authoritative_expected,
        actual_outcome=actual_outcome,
        actual_advisory=actual_advisory,
    )
    rejection = final["semantic_rejection_reason"]
    supported_ids = list(final["semantic_supported_group_ids"])
    unsupported_advice = [
        criterion_id
        for criterion_id in supported_ids
        if criterion_id not in semantic_expected["matched_criteria"]
    ]
    deterministic_passed = deterministic_actual["passed"]
    deterministic_mastery = deterministic_actual["mastery_score"]
    semantic_changed_pass = actual["passed"] is not deterministic_passed
    semantic_changed_mastery = not math.isclose(
        actual["mastery_score"], deterministic_mastery, abs_tol=1e-9
    )
    return {
        "case_id": case["case_id"],
        "question_id": case["question_id"],
        "category": case["category"],
        "student_answer": case["answer"],
        "repeat_index": repeat_index,
        "expected_semantic_trigger": case["expected_semantic_trigger"],
        "actual_semantic_trigger": (
            final["semantic_trigger_eligible"]
        ),
        "trigger_reason": (
            final["semantic_trigger_reason"]
        ),
        "deterministic": {
            "matched_criteria": list(deterministic_actual["required_criteria"]),
            "missing_criteria": list(deterministic_actual["missing_criteria"]),
        },
        "semantic": {
            "judgments": list(final["semantic_judgments"]),
            "confidence": final["semantic_confidence"],
            "used": final["semantic_used"],
            "applied": final["semantic_applied"],
            "status": final["semantic_status"],
            "supported_criteria": supported_ids,
            "abstained": final["semantic_abstained"],
            "abstain_reason": final["semantic_abstain_reason"],
            "rejection_reason": rejection,
        },
        "merged": actual,
        "semantic_expectation": semantic_expected,
        "authoritative_expectation": authoritative_expected,
        "authoritative_actual": {
            "outcome": actual_outcome,
            "advisory": actual_advisory,
        },
        "differences": differences,
        "request_elapsed_seconds": elapsed,
        "semantic_request_elapsed_seconds": recorder.elapsed_seconds,
        "semantic_call_count": recorder.call_count,
        "errors": list(recorder.errors),
        "rejection": rejection,
        "semantic_changed_pass": semantic_changed_pass,
        "semantic_changed_mastery": semantic_changed_mastery,
        "unsupported_semantic_advice": unsupported_advice,
    }


def _validated_cases(benchmark_data: dict[str, Any]) -> list[dict[str, Any]]:
    # The offline runner owns benchmark schema validation. It receives a tiny
    # valid question fixture only to exercise the schema without side effects.
    if not isinstance(benchmark_data, dict) or not isinstance(benchmark_data.get("cases"), list):
        raise LiveSemanticEvaluationError("benchmark_data has an invalid schema.")
    return benchmark_data["cases"]


def _question_index(questions_data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(questions_data, dict) or not isinstance(
        questions_data.get("diagnostic_questions"), list
    ):
        raise LiveSemanticEvaluationError("questions_data has an invalid schema.")
    return {
        question["id"]: question
        for question in questions_data["diagnostic_questions"]
        if isinstance(question, dict) and isinstance(question.get("id"), str)
    }


def _semantic_expected(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "matched_criteria": list(case["expected_required_criteria"]),
        "missing_criteria": list(case["expected_missing_criteria"]),
        "misconception_ids": list(case["expected_misconception_ids"]),
        "passed": case["expected_passed"],
        "mastery_score": case["expected_mastery_score"],
    }


def _authoritative_expected(case: dict[str, Any]) -> dict[str, Any]:
    """Return the human-reviewed production expectation, not semantic truth.

    Semantic truth may say that a low-overlap response entails a criterion,
    while the current advisory-only product must still ask for clarification.
    This explicit separation prevents an evaluator from mislabeling that safe
    containment as a production pass/fail defect.
    """
    outcome = case.get("expected_authoritative_outcome")
    if outcome is None:
        if case["expected_passed"]:
            outcome = "clarify" if case["expected_semantic_trigger"] else "pass"
        else:
            outcome = "fail"
    return {
        "outcome": outcome,
        "advisory": bool(
            case["expected_semantic_trigger"] and case["expected_passed"]
        ),
        "assistance_level": case.get("expected_assistance_level"),
    }


def _authoritative_outcome(final: dict[str, Any]) -> str:
    if final["passed"]:
        return "pass"
    if final["needs_clarification"]:
        return "clarify"
    return "fail"


def _public_final(final: dict[str, Any]) -> dict[str, Any]:
    return {
        "matched_criteria": list(final["matched_required_group_ids"]),
        "missing_criteria": list(final["missing_required_group_ids"]),
        "misconception_ids": list(final["misconception_ids"]),
        "passed": final["passed"],
        "mastery_score": final["mastery_score"],
    }


def _authoritative_differences(
    *, expected: dict[str, Any], actual_outcome: str, actual_advisory: bool
) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    if actual_outcome != expected["outcome"]:
        differences["authoritative_outcome"] = True
    if actual_advisory is not expected["advisory"]:
        differences["advisory"] = True
    return differences


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [record for record in records if record["merged"] is not None]
    authoritative_outcome_correct = 0
    advisory_correct = 0
    semantic_judgment_total = 0
    semantic_judgment_correct = 0
    mismatches: list[dict[str, Any]] = []
    for record in records:
        if record["differences"]:
            mismatches.append(
                {
                    "case_id": record["case_id"],
                    "repeat_index": record["repeat_index"],
                    "reasons": sorted(record["differences"]),
                }
            )
        if record["merged"] is not None:
            authoritative_outcome_correct += int(
                "authoritative_outcome" not in record["differences"]
            )
            advisory_correct += int("advisory" not in record["differences"])
        for judgment in record["semantic"]["judgments"]:
            expected_status = _human_status_for_judgment(
                record["semantic_expectation"], judgment
            )
            if expected_status is None:
                continue
            semantic_judgment_total += 1
            semantic_judgment_correct += int(
                (judgment["status"] == "entailed") == expected_status
            )
    total = len(records)
    return {
        "case_count": total,
        "successful_case_count": len(successful),
        "actual_model_call_count": sum(record["semantic_call_count"] for record in records),
        "semantic_judgment_exact_match": _rate(
            semantic_judgment_correct, semantic_judgment_total
        ),
        "semantic_criterion_judgment_count": semantic_judgment_total,
        "authoritative_outcome_accuracy": _rate(
            authoritative_outcome_correct, len(successful)
        ),
        "advisory_accuracy": _rate(advisory_correct, len(successful)),
        "advisory_expected_count": sum(
            record["authoritative_expectation"]["advisory"] for record in records
        ),
        "advisory_actual_count": sum(
            record["authoritative_actual"]["advisory"] for record in records
        ),
        "abstain_count": sum(record["semantic"]["abstained"] for record in records),
        "abstain_rate": _rate(
            sum(record["semantic"]["abstained"] for record in records), total
        ),
        "invalid_response_count": sum(
            "semantic_schema_rejected" in record["errors"]
            or "adapter_response_error" in record["errors"]
            or record["rejection"] == "invalid_semantic_response"
            for record in records
        ),
        "adapter_error_count": sum(
            any(
                error in {"adapter_request_error", "adapter_error"}
                for error in record["errors"]
            )
            for record in records
        ),
        "advisory_useful_count": sum(
            any(
                criterion_id in record["semantic_expectation"]["matched_criteria"]
                for criterion_id in record["semantic"]["supported_criteria"]
            )
            for record in records
        ),
        "contained_false_positive_count": sum(
            bool(record["unsupported_semantic_advice"])
            and not record["semantic_changed_pass"]
            and not record["semantic_changed_mastery"]
            for record in records
        ),
        "harmful_semantic_false_positive_count": sum(
            bool(record["unsupported_semantic_advice"])
            and (
                record["semantic_changed_pass"]
                or record["semantic_changed_mastery"]
            )
            for record in records
        ),
        "semantic_changed_pass_count": sum(
            record["semantic_changed_pass"] for record in records
        ),
        "semantic_changed_mastery_count": sum(
            record["semantic_changed_mastery"] for record in records
        ),
        "containment_success": _rate(
            sum(
                bool(record["unsupported_semantic_advice"])
                and not record["semantic_changed_pass"]
                and not record["semantic_changed_mastery"]
                for record in records
            ),
            sum(bool(record["unsupported_semantic_advice"]) for record in records),
        ),
        "mismatches": mismatches,
    }


def _human_status_for_judgment(expected: dict[str, Any], judgment: dict[str, str]) -> bool | None:
    criterion_id = judgment["criterion_id"]
    if criterion_id in expected["matched_criteria"] or criterion_id in expected[
        "misconception_ids"
    ]:
        return True
    if criterion_id in expected["missing_criteria"]:
        return False
    # The benchmark deliberately does not claim a human truth value for an
    # optional group, so it is excluded from this metric.
    return None


def _trigger_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for record in records:
        expected = record["expected"]["expected_semantic_trigger"]
        actual = record["actual"]["semantic_trigger_eligible"]
        if expected and actual:
            counts["tp"] += 1
        elif not expected and actual:
            counts["fp"] += 1
        elif not expected and not actual:
            counts["tn"] += 1
        else:
            counts["fn"] += 1
    return {
        **counts,
        "precision": _rate(counts["tp"], counts["tp"] + counts["fp"]),
        "recall": _rate(counts["tp"], counts["tp"] + counts["fn"]),
        "case_count": len(records),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _safe_error_kind(error: Exception) -> str:
    if isinstance(error, DiagnosticSemanticAdjudicationError):
        return "semantic_schema_rejected"
    if isinstance(error, DeepSeekResponseError):
        return "adapter_response_error"
    if isinstance(error, DeepSeekRequestError):
        return "adapter_request_error"
    return "adapter_error"
