import copy
import json
from pathlib import Path

import pytest

from introai_tutor.assessment import assess_structured_answer
from introai_tutor.diagnostic_benchmark import (
    BenchmarkFakeSemanticAdjudicator,
    DiagnosticBenchmarkError,
    load_diagnostic_scoring_benchmark,
    run_diagnostic_scoring_benchmark,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_FILE = PROJECT_ROOT / "data" / "diagnostic_scoring_benchmark.json"
QUESTIONS_FILE = PROJECT_ROOT / "data" / "diagnostic_questions.json"


def _benchmark_data():
    return load_diagnostic_scoring_benchmark(BENCHMARK_FILE)


def _questions_data():
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def _assessment(question_id):
    return next(
        question["assessment"]
        for question in _questions_data()["diagnostic_questions"]
        if question["id"] == question_id
    )


def test_human_verified_benchmark_has_all_required_categories_per_canonical_question():
    benchmark = _benchmark_data()
    required_categories = {
        "standard_correct",
        "correct_chinese_paraphrase",
        "correct_english_or_mixed",
        "partial_correct",
        "clear_misconception",
        "negated_misconception_correct",
        "contradictory",
        "keyword_rich_logic_wrong",
        "semantic_correct_low_lexical_overlap",
        "irrelevant",
        "too_short",
        "prompt_injection",
    }
    assert len(benchmark["cases"]) == 41
    for question_id in {
        "dq_bfs_expansion_001",
        "dq_bfs_order_001",
        "dq_ucs_when_costs_differ_001",
    }:
        categories = {
            case["category"]
            for case in benchmark["cases"]
            if case["question_id"] == question_id
        }
        assert required_categories <= categories
    acceptance_cases = [
        case
        for case in benchmark["cases"]
        if case["category"].startswith("human_acceptance_")
    ]
    assert {case["case_id"] for case in acceptance_cases} == {
        "cost_full_explicit_user_answer",
        "cost_concise_conditional_equivalence",
        "cost_fewest_edges_only",
        "cost_nonnegative_not_equal",
        "cost_equal_condition_variants",
    }
    assert all(
        case.get("expected_authoritative_outcome") for case in acceptance_cases
    )
    assert {case["review_status"] for case in benchmark["cases"]} == {"human_verified"}


def test_deterministic_benchmark_is_offline_and_reports_case_level_error_classes():
    report = run_diagnostic_scoring_benchmark(
        questions_data=_questions_data(), benchmark_data=_benchmark_data()
    )

    assert report["summary"]["case_count"] == 41
    assert set(report["summary"]["error_counts"]) == {
        "criterion_recognition",
        "misconception",
        "pass_fail",
        "mastery_evidence",
        "semantic_trigger",
    }
    assert set(report["summary"]["by_question"]) == {
        "dq_bfs_expansion_001",
        "dq_bfs_order_001",
        "dq_ucs_when_costs_differ_001",
    }
    assert all("actual" in case and "expected" in case for case in report["cases"])
    # The benchmark intentionally exposes cases that phrase matching alone
    # cannot resolve; the report records the mismatch rather than hiding it.
    assert any(
        case["category"] == "semantic_correct_low_lexical_overlap"
        and "criterion_recognition" in case["differences"]
        for case in report["cases"]
    )


def test_injected_fake_semantic_mode_is_advisory_and_cannot_upgrade_human_goldens():
    benchmark = _benchmark_data()
    adjudicator = BenchmarkFakeSemanticAdjudicator(benchmark_data=benchmark)
    report = run_diagnostic_scoring_benchmark(
        questions_data=_questions_data(),
        benchmark_data=benchmark,
        semantic_adjudicator=adjudicator,
    )

    assert report["summary"]["matched_case_count"] == 36
    assert report["summary"]["error_counts"] == {
        "criterion_recognition": 5,
        "misconception": 0,
        "pass_fail": 5,
        "mastery_evidence": 5,
        "semantic_trigger": 0,
    }
    assert len(adjudicator.calls) == sum(
        case["expected_semantic_trigger"] for case in benchmark["cases"]
    )


def test_low_confidence_semantic_evidence_abstains_instead_of_forcing_a_pass():
    rubric = _assessment("dq_ucs_when_costs_differ_001")

    class LowConfidenceAdjudicator:
        calls = 0

        def adjudicate(self, **_kwargs):
            self.calls += 1
            return {
                "judgments": [{"criterion_id": "unequal_costs", "status": "entailed"}],
                "confidence": 0.2,
            }

    adjudicator = LowConfidenceAdjudicator()
    answer = "它会把从起点走到每个候选节点沿途花掉的成本都累计起来，当前总花费更小的节点先扩展。"
    result = assess_structured_answer(
        answer,
        rubric,
        semantic_adjudicator=adjudicator,
        question_context="当动作或边的代价不同时，应该优先使用哪种搜索？",
    )

    assert adjudicator.calls == 1
    assert result["semantic_used"] is True
    assert result["semantic_applied"] is False
    assert result["semantic_abstained"] is True
    assert result["semantic_abstain_reason"] == "low_confidence"
    assert result["passed"] is False
    assert result["mastery_score"] == pytest.approx(0.5)
    assert "回答仍需补充说明，以确认关键条件。" in result["feedback_items"]


def test_conflicting_semantic_evidence_abstains_without_mutating_rubric_or_answer():
    rubric = _assessment("dq_bfs_expansion_001")
    before = copy.deepcopy(rubric)

    class ConflictingAdjudicator:
        def adjudicate(self, **_kwargs):
            return {
                "judgments": [{"criterion_id": "layer_order", "status": "contradicted"}],
                "confidence": 0.99,
            }

    answer = "BFS 按层逐层扩展，但还需要说明 frontier。"
    # Add an optional unmatched phrase condition so the call is eligible while
    # the deterministic evidence still contains the required proposition.
    adjusted = copy.deepcopy(rubric)
    adjusted["required_groups"].append(
        {"id": "frontier_note", "label": "frontier", "terms": ["frontier 的顺序"]}
    )
    result = assess_structured_answer(
        answer, adjusted, semantic_adjudicator=ConflictingAdjudicator()
    )

    assert result["semantic_abstain_reason"] == "conflicting_judgment"
    assert result["semantic_applied"] is False
    assert result["passed"] is False
    assert rubric == before
    assert answer == "BFS 按层逐层扩展，但还需要说明 frontier。"


def test_benchmark_rejects_non_human_verified_or_unknown_case_fields():
    malformed = _benchmark_data()
    malformed["cases"][0]["review_status"] = "draft"
    with pytest.raises(DiagnosticBenchmarkError, match="human_verified"):
        run_diagnostic_scoring_benchmark(
            questions_data=_questions_data(), benchmark_data=malformed
        )

    malformed = _benchmark_data()
    malformed["cases"][0]["unexpected"] = True
    with pytest.raises(DiagnosticBenchmarkError, match="invalid schema"):
        BenchmarkFakeSemanticAdjudicator(benchmark_data=malformed)
