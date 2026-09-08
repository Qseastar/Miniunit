import copy
import json
from pathlib import Path

import pytest

from introai_tutor.deepseek_adapter import DeepSeekRequestError
from introai_tutor.diagnostic_benchmark import load_diagnostic_scoring_benchmark
from introai_tutor.diagnostic_semantics import DiagnosticSemanticAdjudicator
from introai_tutor.live_semantic_evaluation import (
    LiveSemanticEvaluationError,
    evaluate_live_semantics,
    select_live_semantic_cases,
)


ROOT = Path(__file__).resolve().parents[1]


def _benchmark():
    return load_diagnostic_scoring_benchmark(ROOT / "data" / "diagnostic_scoring_benchmark.json")


def _questions():
    return json.loads((ROOT / "data" / "diagnostic_questions.json").read_text(encoding="utf-8"))


class _MappingAdapter:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def complete_json(self, *, system_prompt, user_prompt, max_tokens):
        payload = json.loads(user_prompt)
        answer = payload["student_answer"]
        self.calls.append(
            {"answer": answer, "criteria": payload["criteria"], "max_tokens": max_tokens}
        )
        response = self.responses[answer]
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


def _semantic_adjudicator(benchmark, *, overrides=None):
    overrides = overrides or {}
    responses = {
        case["answer"]: {
            "judgments": copy.deepcopy(case.get("fake_semantic_judgments", [])),
            "confidence": 0.9,
        }
        for case in benchmark["cases"]
        if case["expected_semantic_trigger"]
    }
    responses.update(overrides)
    adapter = _MappingAdapter(responses)
    return DiagnosticSemanticAdjudicator(adapter=adapter), adapter


def test_default_selection_is_only_human_marked_semantic_boundary_cases():
    benchmark = _benchmark()

    selected = select_live_semantic_cases(benchmark)

    assert len(selected) == 8
    assert all(case["expected_semantic_trigger"] for case in selected)


def test_case_id_and_limit_selection_are_deterministic_and_validated():
    benchmark = _benchmark()

    assert [case["case_id"] for case in select_live_semantic_cases(benchmark, limit=2)] == [
        "expansion_chinese_paraphrase",
        "expansion_partial",
    ]
    assert [
        case["case_id"]
        for case in select_live_semantic_cases(
            benchmark, case_ids=["ucs_chinese_paraphrase"]
        )
    ] == ["ucs_chinese_paraphrase"]
    with pytest.raises(LiveSemanticEvaluationError, match="Unknown"):
        select_live_semantic_cases(benchmark, case_ids=["not-a-case"])


def test_fake_production_adjudicator_evaluation_is_one_call_per_case_and_reports_metrics():
    benchmark = _benchmark()
    adjudicator, adapter = _semantic_adjudicator(benchmark)
    before = copy.deepcopy(benchmark)

    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
    )

    assert benchmark == before
    assert len(adapter.calls) == 8
    assert report["summary"]["actual_model_call_count"] == 8
    assert all(record["semantic_call_count"] == 1 for record in report["records"])
    # Human semantic truth and production authority are intentionally separate:
    # advisory-only evidence may be semantically correct while production still
    # asks the learner for clarification.
    assert report["summary"]["semantic_judgment_exact_match"] == 1.0
    assert report["summary"]["authoritative_outcome_accuracy"] == 1.0
    assert report["summary"]["advisory_accuracy"] == 1.0
    assert report["summary"]["advisory_expected_count"] == 5
    assert report["summary"]["advisory_actual_count"] == 5
    assert report["summary"]["advisory_useful_count"] == 5
    assert report["summary"]["harmful_semantic_false_positive_count"] == 0
    assert report["summary"]["semantic_changed_pass_count"] == 0
    assert report["summary"]["semantic_changed_mastery_count"] == 0
    assert report["trigger_metrics"] == {
        "tp": 8,
        "fp": 0,
        "tn": 33,
        "fn": 0,
        "precision": 1.0,
        "recall": 1.0,
        "case_count": 41,
    }


def test_explicit_repeat_creates_one_call_per_run_not_hidden_retries():
    benchmark = _benchmark()
    target = "ucs_chinese_paraphrase"
    adjudicator, adapter = _semantic_adjudicator(benchmark)

    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=[target],
        repeat=2,
    )

    assert len(adapter.calls) == 2
    assert [record["repeat_index"] for record in report["records"]] == [1, 2]
    assert all(record["semantic_call_count"] == 1 for record in report["records"])


def test_low_confidence_and_conflicting_semantic_responses_are_reported_as_abstentions():
    benchmark = _benchmark()
    target = next(
        case for case in benchmark["cases"] if case["case_id"] == "ucs_chinese_paraphrase"
    )
    adjudicator, _adapter = _semantic_adjudicator(
        benchmark,
        overrides={
            target["answer"]: {
                "judgments": [{"criterion_id": "unequal_costs", "status": "entailed"}],
                "confidence": 0.2,
            }
        },
    )
    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=[target["case_id"]],
    )
    record = report["records"][0]
    assert record["semantic"]["abstained"] is True
    assert record["semantic"]["abstain_reason"] == "low_confidence"
    assert record["merged"]["passed"] is False

    adjudicator, _adapter = _semantic_adjudicator(
        benchmark,
        overrides={
            target["answer"]: {
                "judgments": [
                    {"criterion_id": "cumulative_path_cost", "status": "contradicted"}
                ],
                "confidence": 0.99,
            }
        },
    )
    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=[target["case_id"]],
    )
    conflict_record = report["records"][0]
    assert conflict_record["semantic"]["abstain_reason"] == "conflicting_judgment"
    assert conflict_record["merged"]["passed"] is False
    assert conflict_record["merged"]["mastery_score"] == pytest.approx(0.5)


def test_semantic_false_positive_is_reported_as_contained_not_harmful():
    benchmark = _benchmark()
    target = next(
        case for case in benchmark["cases"] if case["case_id"] == "expansion_partial"
    )
    adjudicator, _adapter = _semantic_adjudicator(
        benchmark,
        overrides={
            target["answer"]: {
                "judgments": [{"criterion_id": "layer_order", "status": "entailed"}],
                "confidence": 1.0,
            }
        },
    )
    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=[target["case_id"]],
    )

    record = report["records"][0]
    assert record["semantic"]["supported_criteria"] == ["layer_order"]
    assert record["merged"]["passed"] is False
    assert record["merged"]["mastery_score"] == pytest.approx(0.2)
    assert record["semantic_changed_pass"] is False
    assert record["semantic_changed_mastery"] is False
    assert report["summary"]["contained_false_positive_count"] == 1
    assert report["summary"]["harmful_semantic_false_positive_count"] == 0
    assert report["summary"]["containment_success"] == 1.0


def test_evaluator_separates_semantic_truth_from_authoritative_production_outcome():
    benchmark = _benchmark()
    adjudicator, _adapter = _semantic_adjudicator(benchmark)

    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=["expansion_partial", "ucs_chinese_paraphrase"],
    )
    partial, ucs = report["records"]

    assert partial["semantic_expectation"]["matched_criteria"] == []
    assert partial["authoritative_expectation"]["outcome"] == "fail"
    assert partial["authoritative_actual"]["outcome"] == "fail"
    assert ucs["semantic_expectation"]["matched_criteria"] == [
        "unequal_costs",
        "cumulative_path_cost",
    ]
    assert ucs["semantic"]["supported_criteria"] == ["unequal_costs"]
    assert ucs["authoritative_expectation"]["outcome"] == "clarify"
    assert ucs["authoritative_actual"]["outcome"] == "clarify"


def test_invalid_schema_and_adapter_errors_are_sanitized_in_the_report():
    benchmark = _benchmark()
    target = next(
        case for case in benchmark["cases"] if case["case_id"] == "ucs_chinese_paraphrase"
    )
    secret = "test-api-key-must-not-leak"
    adjudicator, _adapter = _semantic_adjudicator(
        benchmark, overrides={target["answer"]: {"score": 1.0}}
    )
    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=[target["case_id"]],
    )
    record = report["records"][0]
    assert record["rejection"] == "invalid_semantic_response"
    assert record["semantic"]["status"] == "rejected"
    assert report["summary"]["invalid_response_count"] == 1
    serialized = json.dumps(report, ensure_ascii=False)
    assert secret not in serialized
    assert "Authorization" not in serialized
    assert "system_prompt" not in serialized

    adjudicator, _adapter = _semantic_adjudicator(
        benchmark,
        overrides={target["answer"]: DeepSeekRequestError(secret)},
    )
    report = evaluate_live_semantics(
        questions_data=_questions(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
        case_ids=[target["case_id"]],
    )
    assert report["summary"]["adapter_error_count"] == 1
    assert secret not in json.dumps(report, ensure_ascii=False)
