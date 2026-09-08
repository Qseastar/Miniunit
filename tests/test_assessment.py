import copy
import json
from pathlib import Path

import pytest

from introai_tutor.assessment import (
    VALID_RESULTS,
    add_misconception,
    assess_answer,
    assess_structured_answer,
    evaluate_answer,
    _normalize_structured_text,
    record_learning_evidence,
    update_mastery,
    validate_structured_assessment,
)
from introai_tutor.diagnostic_semantics import DiagnosticSemanticAdjudicationError
from introai_tutor.deepseek_adapter import DeepSeekRequestError
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.learner import load_learner_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
LEARNER_STATE_FILE = PROJECT_ROOT / "data" / "demo_student_state.json"


def _load_demo():
    """Shared helper: return (knowledge_data, learner_state)."""
    kd = load_knowledge_points(KNOWLEDGE_FILE)
    ls = load_learner_state(LEARNER_STATE_FILE, kd)
    return kd, ls


def _structured_rubric():
    return {
        "required_groups": [
            {
                "id": "layer_order",
                "label": "按层扩展",
                "terms": ["逐层", "按层", "level by level"],
            },
            {
                "id": "path_cost",
                "label": "累计路径代价 g(n)",
                "terms": ["累计路径代价", "g(n)", "path cost"],
            },
        ],
        "optional_groups": [
            {
                "id": "fifo_queue",
                "label": "FIFO 队列",
                "terms": ["FIFO", "先进先出", "queue"],
            }
        ],
        "blocking_misconceptions": [
            {
                "id": "bfs_is_depth_first",
                "patterns": ["使用栈", "depth first"],
                "feedback": "BFS 不是深度优先。",
            }
        ],
        "pass_threshold": 1.0,
    }


def _canonical_assessment(question_id):
    questions = json.loads(
        (PROJECT_ROOT / "data" / "diagnostic_questions.json").read_text(encoding="utf-8")
    )["diagnostic_questions"]
    return next(question["assessment"] for question in questions if question["id"] == question_id)


class _RecordingSemanticAdjudicator:
    def __init__(self, judgments):
        self.judgments = judgments
        self.calls = []

    def adjudicate(self, *, answer, criteria, question_context=None):
        self.calls.append(
            {
                "answer": answer,
                "criteria": copy.deepcopy(criteria),
                "question_context": question_context,
            }
        )
        return {"judgments": copy.deepcopy(self.judgments), "confidence": 0.9}


class _UnavailableSemanticAdjudicator:
    def __init__(self):
        self.calls = 0

    def adjudicate(self, *, answer, criteria, question_context=None):
        self.calls += 1
        raise DeepSeekRequestError("offline test transport failure")


class TestStructuredAssessment:
    def test_normalization_removes_nfkc_normalized_chinese_comma(self):
        assert _normalize_structured_text("UCS，因为 UCS 考虑代价。") == "ucs 因为 ucs 考虑代价"

    def test_chinese_required_group_matches(self):
        result = assess_structured_answer("BFS 按层扩展，并看累计路径代价。", _structured_rubric())
        assert result["matched_required_group_ids"] == ["layer_order", "path_cost"]
        assert result["passed"] is True

    def test_english_required_group_matches(self):
        result = assess_structured_answer("Search level by level using path cost.", _structured_rubric())
        assert result["matched_required_group_ids"] == ["layer_order", "path_cost"]
        assert result["passed"] is True

    def test_synonyms_count_once_per_group(self):
        result = assess_structured_answer("逐层、按层、层序扩展；累计路径代价。", _structured_rubric())
        assert result["score"] == pytest.approx(1.0)
        assert result["matched_required_group_ids"] == ["layer_order", "path_cost"]

    def test_optional_group_adds_fixed_bonus(self):
        result = assess_structured_answer("逐层扩展，FIFO 队列。", _structured_rubric())
        assert result["score"] == pytest.approx(0.7)
        assert result["passed"] is False
        assert result["matched_optional_group_ids"] == ["fifo_queue"]

    def test_missing_required_group_is_reported(self):
        result = assess_structured_answer("逐层扩展。", _structured_rubric())
        assert result["missing_required_group_ids"] == ["path_cost"]
        assert result["passed"] is False

    def test_blocking_misconception_forces_failure(self):
        result = assess_structured_answer(
            "BFS 按层扩展并考虑累计路径代价，但它使用栈。", _structured_rubric()
        )
        assert result["score"] == pytest.approx(1.0)
        assert result["misconception_ids"] == ["bfs_is_depth_first"]
        assert result["passed"] is False

    def test_nfkc_case_and_punctuation_normalization_preserves_algorithm_terms(self):
        rubric = _structured_rubric()
        result = assess_structured_answer("ＢＦＳ：LEVEL BY LEVEL；Ｇ（ｎ）／ＦＩＦＯ！", rubric)
        assert result["matched_required_group_ids"] == ["layer_order", "path_cost"]
        assert result["matched_optional_group_ids"] == ["fifo_queue"]
        assert result["score"] == pytest.approx(1.0)

    def test_algorithm_tokens_bfs_ucs_fifo_and_g_n_remain_matchable(self):
        rubric = {
            "required_groups": [
                {"id": "bfs", "label": "BFS", "terms": ["BFS"]},
                {"id": "ucs", "label": "UCS", "terms": ["UCS"]},
                {"id": "fifo", "label": "FIFO", "terms": ["FIFO"]},
                {"id": "g", "label": "g(n)", "terms": ["g(n)"]},
            ],
            "optional_groups": [],
            "blocking_misconceptions": [],
            "pass_threshold": 1.0,
        }
        result = assess_structured_answer("ＢＦＳ、ucs；ＦＩＦＯ：Ｇ（ｎ）", rubric)
        assert result["matched_required_group_ids"] == ["bfs", "ucs", "fifo", "g"]

    def test_negated_blocking_phrase_is_not_a_misconception(self):
        result = assess_structured_answer(
            "BFS 不是沿一条路径一直深入，而是按层逐层扩展。",
            json.loads(json.dumps(_structured_rubric()))
            | {
                "required_groups": [
                    {
                        "id": "layer_order",
                        "label": "按层扩展",
                        "terms": ["逐层"],
                    }
                ],
                "optional_groups": [],
            },
        )
        assert result["passed"] is True
        assert result["misconception_ids"] == []

    def test_negated_bfs_cost_claim_can_pass_step_two(self):
        question = next(
            q
            for q in json.loads(
                (PROJECT_ROOT / "data" / "diagnostic_questions.json").read_text(encoding="utf-8")
            )["diagnostic_questions"]
            if q["id"] == "dq_bfs_order_001"
        )
        result = assess_structured_answer(
            "BFS 并不总能找到总代价最低路径，只有每一步代价相同时才成立。",
            question["assessment"],
        )
        assert result["passed"] is True
        assert result["misconception_ids"] == []

    def test_negated_ucs_depth_claim_can_pass_step_three(self):
        result = assess_structured_answer(
            "UCS 不是按步数或深度扩展，而是选择累计路径代价 g(n) 最小的节点。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
        )
        assert result["passed"] is True
        assert result["misconception_ids"] == []

    def test_negated_ucs_total_step_count_claim_is_not_a_misconception(self):
        result = assess_structured_answer(
            "UCS 不是按路径的总步数选择，而是按累计路径代价 g(n) 选择。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
        )
        assert result["passed"] is True
        assert result["misconception_ids"] == []

    def test_natural_cumulative_cost_phrase_matches_canonical_ucs_rubric(self):
        result = assess_structured_answer(
            "UCS 在动作代价不同时，把沿途每一步的花费加起来后选择更小的路径。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
        )
        assert result["matched_required_group_ids"] == [
            "unequal_costs",
            "cumulative_path_cost",
        ]
        assert result["passed"] is True

    def test_real_ucs_partial_answer_keeps_coverage_and_flags_step_count_error(self):
        result = assess_structured_answer(
            "UCS，因为UCS考虑每一步的代价以及路径的总步数。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
        )
        assert result["coverage_score"] > 0.0
        assert result["score"] == result["coverage_score"]
        assert result["mastery_score"] == 0.0
        assert result["matched_labels"] == ["动作或边代价不同时使用 UCS"]
        assert result["missing_labels"] == ["按累计路径代价 g(n) 选择"]
        assert result["misconception_ids"] == ["ucs_uses_depth_or_step_count"]
        assert result["misconception_feedback"] == [
            "UCS 依据累计路径代价选择，不是按深度或步数选择。"
        ]
        assert result["passed"] is False

    def test_case_a_negated_bfs_cost_claim_passes_without_semantic_adjudicator(self):
        result = assess_structured_answer(
            "BFS保证找到步数最少或边数最少的路径，但不保证在任意边权下找到路径"
            "总代价最低的路径。只有所有动作或边的代价都相同，例如都是单位代价时，"
            "步数最少才等价于路径总代价最低。",
            _canonical_assessment("dq_bfs_order_001"),
        )

        assert result["coverage_score"] == 1.0
        assert result["misconception_ids"] == []
        assert result["passed"] is True

    def test_case_b_natural_edge_count_and_equal_cost_explanation_passes_offline(self):
        result = assess_structured_answer(
            "BFS只保证经过的边比较少。只有每条边的花费都一样时，边数少才等于总成本低。",
            _canonical_assessment("dq_bfs_order_001"),
        )

        assert result["matched_required_group_ids"] == [
            "fewest_steps",
            "equal_step_cost_condition",
            "path_cost_distinction",
        ]
        assert result["coverage_score"] == 1.0
        assert result["passed"] is True

    def test_case_b_stays_correct_when_semantic_adjudicator_is_configured(self):
        adjudicator = _RecordingSemanticAdjudicator([])
        result = assess_structured_answer(
            "BFS只保证经过的边比较少。只有每条边的花费都一样时，边数少才等于总成本低。",
            _canonical_assessment("dq_bfs_order_001"),
            semantic_adjudicator=adjudicator,
            question_context="BFS 的最优性依赖什么条件？",
        )

        assert result["passed"] is True
        assert result["semantic_used"] is False
        assert adjudicator.calls == []

    def test_explicit_full_bfs_natural_language_answer_passes_deterministically(self):
        adjudicator = _RecordingSemanticAdjudicator([])
        result = assess_structured_answer(
            "BFS 会先找到路径甲，因为它按层数（步数）逐层扩展，"
            "2 步的目标会早于 4 步的目标被发现。这说明 BFS 的“最优”是指"
            "最少边数、最少步数，而不是总代价最小。只有在无权图或所有边的"
            "代价相同且非负时，最少步数才等价于最小总代价，BFS 才能保证代价最优。",
            _canonical_assessment("dq_bfs_order_001"),
            semantic_adjudicator=adjudicator,
        )

        assert result["matched_required_group_ids"] == [
            "fewest_steps",
            "equal_step_cost_condition",
            "path_cost_distinction",
        ]
        assert result["coverage_score"] == 1.0
        assert result["mastery_score"] == 1.0
        assert result["passed"] is True
        assert result["semantic_used"] is False
        assert result["needs_clarification"] is False
        assert adjudicator.calls == []

    def test_concise_conditional_bfs_distinction_passes_without_semantic(self):
        adjudicator = _RecordingSemanticAdjudicator([])
        result = assess_structured_answer(
            "BFS 会先找到路径甲，因为它优先找到步数更少的路径。"
            "只有所有边的代价相同时，步数最少才等价于路径总代价最小。",
            _canonical_assessment("dq_bfs_order_001"),
            semantic_adjudicator=adjudicator,
        )

        assert result["matched_required_group_ids"] == [
            "fewest_steps",
            "equal_step_cost_condition",
            "path_cost_distinction",
        ]
        assert result["coverage_score"] == 1.0
        assert result["mastery_score"] == 1.0
        assert result["passed"] is True
        assert result["semantic_used"] is False
        assert result["needs_clarification"] is False
        assert adjudicator.calls == []

    @pytest.mark.parametrize(
        "answer, expected_required, expected_missing",
        [
            (
                "BFS 只能保证找到边数最少的路径。",
                ["fewest_steps"],
                ["equal_step_cost_condition", "path_cost_distinction"],
            ),
            (
                "只要所有边权非负，BFS 就保证总代价最小。",
                [],
                ["fewest_steps", "equal_step_cost_condition", "path_cost_distinction"],
            ),
            (
                "BFS 找到总代价最小的路径。",
                [],
                ["fewest_steps", "equal_step_cost_condition", "path_cost_distinction"],
            ),
            (
                "步数最少，总代价也最小。",
                ["fewest_steps"],
                ["equal_step_cost_condition", "path_cost_distinction"],
            ),
            (
                "在无权图或所有边代价相同的情况下，BFS 的步数最少才可以比较总代价。",
                ["fewest_steps", "equal_step_cost_condition"],
                ["path_cost_distinction"],
            ),
        ],
    )
    def test_bfs_cost_negative_controls_do_not_turn_into_a_pass(
        self, answer, expected_required, expected_missing
    ):
        result = assess_structured_answer(answer, _canonical_assessment("dq_bfs_order_001"))

        assert result["matched_required_group_ids"] == expected_required
        assert result["missing_required_group_ids"] == expected_missing
        assert result["passed"] is False

    def test_nonnegative_weight_claim_remains_a_blocking_misconception(self):
        result = assess_structured_answer(
            "所有边权都是非负的，所以 BFS 保证总代价最小。",
            _canonical_assessment("dq_bfs_order_001"),
        )

        assert "equal_step_cost_condition" not in result["matched_required_group_ids"]
        assert result["misconception_ids"] == ["bfs_always_cost_optimal"]
        assert result["passed"] is False

    @pytest.mark.parametrize(
        "answer",
        [
            "BFS 不保证在任意边权下总代价最低；只有每一步代价相同才可以。",
            "BFS 并不保证任意边权下总代价最低；只有单位代价时才可以。",
            "BFS 并非在任意边权下都能保证总代价最低；只有单位代价时才可以。",
            "BFS 在任意边权下不保证总代价最低；只有每条边花费一样时才可以。",
            "BFS 能找到边数少的路径，但不保证任意代价下总代价最低；只有等步代价才可以。",
        ],
    )
    def test_local_negation_scope_never_confirms_bfs_cost_misconception(self, answer):
        result = assess_structured_answer(
            answer, _canonical_assessment("dq_bfs_order_001")
        )

        assert "bfs_always_cost_optimal" not in result["misconception_ids"]

    def test_case_d_cumulative_cost_explanation_has_deterministic_partial_coverage(self):
        result = assess_structured_answer(
            "它会把从起点走到每个候选节点沿途花掉的成本都累计起来，"
            "当前总花费更小的节点先扩展。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
        )

        assert result["matched_required_group_ids"] == ["cumulative_path_cost"]
        assert result["coverage_score"] > 0.0
        assert result["passed"] is False

    def test_case_d_semantic_context_is_advisory_and_requires_clarification(self):
        adjudicator = _RecordingSemanticAdjudicator(
            [{"criterion_id": "unequal_costs", "status": "entailed"}]
        )
        question_context = "当动作或边的代价不同时，应该优先使用哪种搜索？"
        result = assess_structured_answer(
            "它会把从起点走到每个候选节点沿途花掉的成本都累计起来，"
            "当前总花费更小的节点先扩展。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
            semantic_adjudicator=adjudicator,
            question_context=question_context,
        )

        assert result["semantic_used"] is True
        assert result["semantic_status"] == "advisory"
        assert result["semantic_supported_group_ids"] == ["unequal_costs"]
        assert result["matched_required_group_ids"] == ["cumulative_path_cost"]
        assert result["coverage_score"] == 0.5
        assert result["mastery_score"] == 0.5
        assert result["passed"] is False
        assert result["needs_clarification"] is True
        assert result["clarifying_question"] == (
            "请再明确：这种搜索策略叫什么，通常用于哪种动作代价情形？"
        )
        assert len(adjudicator.calls) == 1
        assert adjudicator.calls[0]["question_context"] == question_context

    def test_queue_only_false_positive_is_contained_as_clarification(self):
        adjudicator = _RecordingSemanticAdjudicator(
            [{"criterion_id": "layer_order", "status": "entailed"}]
        )
        result = assess_structured_answer(
            "BFS 使用队列保存 frontier。",
            _canonical_assessment("dq_bfs_expansion_001"),
            semantic_adjudicator=adjudicator,
            question_context="BFS 通常如何从 frontier 中选择下一个节点扩展？",
        )

        assert result["matched_required_group_ids"] == []
        assert result["matched_optional_group_ids"] == ["fifo_queue"]
        assert result["semantic_supported_group_ids"] == ["layer_order"]
        assert result["needs_clarification"] is True
        assert result["passed"] is False
        assert result["mastery_score"] == pytest.approx(0.2)
        assert result["clarifying_question"] == (
            "请进一步说明：队列的处理顺序如何使 BFS 先完成当前层，再进入下一层？"
        )

    def test_semantic_unavailability_falls_back_to_deterministic_partial_result(self):
        adjudicator = _UnavailableSemanticAdjudicator()
        result = assess_structured_answer(
            "它会把从起点走到每个候选节点沿途花掉的成本都累计起来，"
            "当前总花费更小的节点先扩展。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
            semantic_adjudicator=adjudicator,
            question_context="当动作或边的代价不同时，应该优先使用哪种搜索？",
        )

        assert result["semantic_used"] is False
        assert result["matched_required_group_ids"] == ["cumulative_path_cost"]
        assert result["passed"] is False
        assert adjudicator.calls == 1

    def test_clear_correct_or_blocking_answers_do_not_call_semantic_adjudicator(self):
        rubric = _canonical_assessment("dq_ucs_when_costs_differ_001")
        adjudicator = _RecordingSemanticAdjudicator([])

        correct = assess_structured_answer(
            "UCS 处理不同代价，按累计路径代价 g(n) 最小选择节点。",
            rubric,
            semantic_adjudicator=adjudicator,
        )
        blocking = assess_structured_answer(
            "UCS 按路径的总步数选择。",
            rubric,
            semantic_adjudicator=adjudicator,
        )

        assert correct["semantic_used"] is False
        assert blocking["semantic_used"] is False
        assert adjudicator.calls == []

    def test_semantic_adjudicator_only_advises_allowlisted_incomplete_answer(self):
        rubric = _canonical_assessment("dq_ucs_when_costs_differ_001")
        adjudicator = _RecordingSemanticAdjudicator(
            [{"criterion_id": "cumulative_path_cost", "status": "entailed"}]
        )
        answer = "UCS 面对不同开销时，要比较从起点走到节点已经花掉的全部成本。"
        before_rubric = copy.deepcopy(rubric)

        result = assess_structured_answer(
            answer, rubric, semantic_adjudicator=adjudicator
        )

        assert result["semantic_used"] is True
        assert result["semantic_supported_group_ids"] == ["cumulative_path_cost"]
        assert result["matched_required_group_ids"] == ["unequal_costs"]
        assert result["passed"] is False
        assert result["mastery_score"] == 0.5
        assert result["semantic_authority_applied"] is False
        assert adjudicator.calls[0]["answer"] == answer
        assert {item["criterion_id"] for item in adjudicator.calls[0]["criteria"]} >= {
            "unequal_costs",
            "cumulative_path_cost",
        }
        assert rubric == before_rubric

    def test_unconfigured_semantic_adjudicator_keeps_offline_deterministic_result(self):
        result = assess_structured_answer(
            "UCS 面对不同开销时，要比较从起点走到节点已经花掉的全部成本。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
        )

        assert result["semantic_used"] is False
        assert result["semantic_uncertain"] is True

    def test_invalid_semantic_response_is_rejected_without_changing_deterministic_score(self):
        adjudicator = _RecordingSemanticAdjudicator(
            [{"criterion_id": "invented", "status": "entailed"}]
        )

        result = assess_structured_answer(
            "UCS 面对不同开销时，要比较从起点走到节点已经花掉的全部成本。",
            _canonical_assessment("dq_ucs_when_costs_differ_001"),
            semantic_adjudicator=adjudicator,
        )

        assert result["semantic_status"] == "rejected"
        assert result["semantic_rejection_reason"] == "invalid_semantic_response"
        assert result["passed"] is False
        assert result["mastery_score"] == 0.5

    def test_invalid_semantic_adjudicator_interface_is_rejected_before_scoring(self):
        with pytest.raises(DiagnosticSemanticAdjudicationError, match="adjudicate"):
            assess_structured_answer(
                "UCS 处理不同代价，按累计路径代价 g(n) 选择节点。",
                _canonical_assessment("dq_ucs_when_costs_differ_001"),
                semantic_adjudicator=object(),
            )

    def test_english_negated_blocking_phrase_is_not_a_misconception(self):
        rubric = {
            "required_groups": [{"id": "layer", "label": "layer", "terms": ["level by level"]}],
            "optional_groups": [],
            "blocking_misconceptions": [
                {"id": "dfs", "patterns": ["depth first"], "feedback": "wrong"}
            ],
            "pass_threshold": 1.0,
        }
        result = assess_structured_answer("BFS isn't depth-first; it expands level by level.", rubric)
        assert result["passed"] is True
        assert result["misconception_ids"] == []

    def test_unnegated_error_still_triggers_in_contradictory_answer(self):
        question = next(
            q
            for q in json.loads(
                (PROJECT_ROOT / "data" / "diagnostic_questions.json").read_text(encoding="utf-8")
            )["diagnostic_questions"]
            if q["id"] == "dq_bfs_order_001"
        )
        result = assess_structured_answer(
            "BFS 在任意代价下总是总代价最优，不过只有等代价时才成立。",
            question["assessment"],
        )
        assert result["misconception_ids"] == ["bfs_always_cost_optimal"]
        assert result["passed"] is False

    def test_ucs_fifo_and_g_not_split_into_false_matches(self):
        rubric = _structured_rubric()
        result = assess_structured_answer("UCS 按 g(n) 选择，FIFO 不会替代优先队列。", rubric)
        assert result["matched_required_group_ids"] == ["path_cost"]
        assert result["matched_optional_group_ids"] == ["fifo_queue"]

    @pytest.mark.parametrize(
        "broken",
        [
            {},
            {"required_groups": [], "optional_groups": [], "blocking_misconceptions": [], "pass_threshold": 1},
            {"required_groups": [{"id": "x", "label": "x", "terms": []}], "optional_groups": [], "blocking_misconceptions": [], "pass_threshold": 1},
            {"required_groups": [{"id": "x", "label": "x", "terms": ["x"]}], "optional_groups": [], "blocking_misconceptions": [], "pass_threshold": True},
        ],
    )
    def test_invalid_rubric_fails_clearly(self, broken):
        with pytest.raises(ValueError):
            validate_structured_assessment(broken)

    def test_duplicate_group_and_misconception_ids_are_rejected(self):
        rubric = _structured_rubric()
        rubric["required_groups"].append(copy.deepcopy(rubric["required_groups"][0]))
        with pytest.raises(ValueError, match="group ids must be unique"):
            validate_structured_assessment(rubric)

        rubric = _structured_rubric()
        rubric["blocking_misconceptions"].append(copy.deepcopy(rubric["blocking_misconceptions"][0]))
        with pytest.raises(ValueError, match="misconception ids must be unique"):
            validate_structured_assessment(rubric)

    def test_does_not_mutate_inputs(self):
        rubric = _structured_rubric()
        answer = "BFS 按层扩展，累计路径代价。"
        before_rubric = copy.deepcopy(rubric)
        assess_structured_answer(answer, rubric)
        assert rubric == before_rubric
        assert answer == "BFS 按层扩展，累计路径代价。"


# ── evaluate_answer ──────────────────────────────────────────────────────────


class TestEvaluateAnswer:
    def test_correct_all_keywords_matched(self):
        result = evaluate_answer(
            "BFS uses a FIFO queue and explores level by level",
            expected_keywords=["fifo", "queue", "level"],
        )
        assert result["result"] == "correct"
        assert result["matched"] == ["fifo", "queue", "level"]
        assert result["missing"] == []

    def test_incorrect_no_keywords_matched(self):
        result = evaluate_answer(
            "I don't know the answer",
            expected_keywords=["fifo", "queue"],
        )
        assert result["result"] == "incorrect"
        assert len(result["matched"]) == 0

    def test_partially_correct_some_keywords_matched(self):
        result = evaluate_answer(
            "BFS uses a queue to search",
            expected_keywords=["fifo", "queue", "level"],
        )
        assert result["result"] == "partially_correct"
        assert "queue" in result["matched"]
        assert "fifo" in result["missing"]

    def test_case_insensitive_by_default(self):
        result = evaluate_answer(
            "BFS USES A QUEUE",
            expected_keywords=["bfs", "queue"],
        )
        assert result["result"] == "correct"

    def test_case_sensitive_flag(self):
        result = evaluate_answer(
            "bfs uses a queue",
            expected_keywords=["BFS", "queue"],
            case_sensitive=True,
        )
        # "BFS" (uppercase) not found in "bfs uses a queue"
        assert result["result"] == "partially_correct"
        assert "queue" in result["matched"]
        assert "BFS" in result["missing"]

    def test_empty_keywords_returns_unknown(self):
        result = evaluate_answer("anything", expected_keywords=[])
        assert result["result"] == "unknown"

    def test_none_keywords_returns_unknown(self):
        result = evaluate_answer("anything", expected_keywords=None)
        assert result["result"] == "unknown"


# ── update_mastery ───────────────────────────────────────────────────────────


class TestUpdateMastery:
    def test_correct_increases_mastery(self):
        state = {"mastery": {"bfs": 0.5}}
        new_score = update_mastery(state, "bfs", "correct")
        assert new_score > 0.5
        assert state["mastery"]["bfs"] == new_score

    def test_incorrect_decreases_mastery(self):
        state = {"mastery": {"bfs": 0.5}}
        new_score = update_mastery(state, "bfs", "incorrect")
        assert new_score < 0.5
        assert state["mastery"]["bfs"] == new_score

    def test_partially_correct_smaller_increase(self):
        state = {"mastery": {"bfs": 0.2}}
        # Compare the delta for correct vs partially_correct
        s1 = copy.deepcopy(state)
        s2 = copy.deepcopy(state)
        d_correct = update_mastery(s1, "bfs", "correct") - 0.2
        d_partial = update_mastery(s2, "bfs", "partially_correct") - 0.2
        assert d_correct > d_partial

    def test_new_concept_starts_at_zero_then_updated(self):
        state: dict = {"mastery": {}}
        new_score = update_mastery(state, "bfs", "correct")
        # Starts from 0.0, target 1.0, lr=0.15 → 0.0 + 0.15*(1.0-0.0) = 0.15
        assert new_score == pytest.approx(0.15)
        assert state["mastery"]["bfs"] == pytest.approx(0.15)

    def test_score_clamped_to_zero(self):
        state = {"mastery": {"bfs": 0.0}}
        new_score = update_mastery(state, "bfs", "incorrect")
        assert new_score == 0.0

    def test_score_clamped_to_one(self):
        state = {"mastery": {"bfs": 0.95}}
        new_score = update_mastery(state, "bfs", "correct")
        assert new_score <= 1.0

    def test_invalid_result_raises(self):
        state = {"mastery": {"bfs": 0.5}}
        with pytest.raises(ValueError, match="Invalid evaluation result"):
            update_mastery(state, "bfs", "excellent")

    def test_custom_learning_rate(self):
        state = {"mastery": {"bfs": 0.0}}
        # lr=0.5 → 0.0 + 0.5*(1.0-0.0) = 0.5
        new_score = update_mastery(state, "bfs", "correct", learning_rate=0.5)
        assert new_score == pytest.approx(0.5)

    def test_mastery_dict_created_if_missing(self):
        state: dict = {}
        new_score = update_mastery(state, "bfs", "correct")
        assert "mastery" in state
        assert state["mastery"]["bfs"] == new_score


# ── record_learning_evidence ─────────────────────────────────────────────────


class TestRecordLearningEvidence:
    def test_appends_to_existing_evidence(self):
        state = {"learning_evidence": []}
        record_learning_evidence(state, "bfs", "quiz_01", "correct", "good job")
        assert len(state["learning_evidence"]) == 1
        entry = state["learning_evidence"][0]
        assert entry["concept_id"] == "bfs"
        assert entry["activity_id"] == "quiz_01"
        assert entry["result"] == "correct"
        assert entry["note"] == "good job"

    def test_creates_evidence_list_if_missing(self):
        state: dict = {}
        record_learning_evidence(state, "bfs", "quiz_01", "incorrect")
        assert "learning_evidence" in state
        assert len(state["learning_evidence"]) == 1


# ── add_misconception ────────────────────────────────────────────────────────


class TestAddMisconception:
    def test_appends_to_existing_misconceptions(self):
        state = {"misconceptions": []}
        add_misconception(state, "bfs", "Confuses BFS with DFS")
        assert len(state["misconceptions"]) == 1
        assert state["misconceptions"][0]["concept_id"] == "bfs"
        assert "Confuses BFS with DFS" in state["misconceptions"][0]["description"]

    def test_creates_misconceptions_list_if_missing(self):
        state: dict = {}
        add_misconception(state, "bfs", "Wrong mental model")
        assert "misconceptions" in state
        assert len(state["misconceptions"]) == 1


# ── assess_answer (full pipeline) ────────────────────────────────────────────


class TestAssessAnswer:
    def test_full_pipeline_correct_answer(self):
        _, state = _load_demo()
        old = state["mastery"].get("breadth_first_search", 0.0)

        result = assess_answer(
            state,
            "breadth_first_search",
            "BFS uses a FIFO queue for level-by-level expansion",
            expected_keywords=["fifo", "queue", "level"],
            activity_id="quiz_bfs_01",
        )

        assert result["concept_id"] == "breadth_first_search"
        assert result["old_mastery"] == old
        assert result["new_mastery"] > old
        assert result["evaluation"]["result"] == "correct"

        # Evidence should be recorded
        evidence = state["learning_evidence"]
        assert evidence[-1]["concept_id"] == "breadth_first_search"
        assert evidence[-1]["activity_id"] == "quiz_bfs_01"

    def test_full_pipeline_incorrect_answer(self):
        _, state = _load_demo()
        old = state["mastery"].get("breadth_first_search", 0.0)

        result = assess_answer(
            state,
            "breadth_first_search",
            "I have no idea",
            expected_keywords=["fifo", "queue"],
            activity_id="quiz_bfs_02",
        )

        assert result["evaluation"]["result"] == "incorrect"
        assert result["new_mastery"] < old

    def test_pipeline_with_unknown_result_leaves_mastery_unchanged(self):
        """When no keywords are provided, mastery should not change."""
        _, state = _load_demo()
        old = state["mastery"].get("breadth_first_search", 0.0)

        result = assess_answer(
            state,
            "breadth_first_search",
            "Some answer",
            expected_keywords=None,
            activity_id="quiz_no_eval",
        )

        assert result["evaluation"]["result"] == "unknown"
        assert result["new_mastery"] == old

    def test_pipeline_default_activity_id(self):
        state: dict = {"mastery": {}}
        assess_answer(
            state,
            "bfs",
            "queue",
            expected_keywords=["queue"],
        )
        assert state["learning_evidence"][0]["activity_id"] == "unnamed_activity"

    def test_pipeline_with_demo_state_integration(self):
        """Integration: run several assessments and verify state coherence."""
        knowledge_data, state = _load_demo()

        # Student gets BFS questions
        assess_answer(
            state,
            "breadth_first_search",
            "FIFO queue level by level",
            expected_keywords=["fifo", "queue"],
            activity_id="ex_01",
        )

        assess_answer(
            state,
            "breadth_first_search",
            "DFS uses a stack",
            expected_keywords=["fifo", "queue"],
            activity_id="ex_02",
        )

        # Verify mastery changed
        assert "breadth_first_search" in state["mastery"]

        # Verify two evidence entries recorded
        bfs_evidence = [
            e for e in state["learning_evidence"]
            if e["concept_id"] == "breadth_first_search"
        ]
        assert len(bfs_evidence) >= 2

    def test_mastery_converges_toward_target(self):
        """After repeated correct answers, mastery should approach 1.0."""
        state = {"mastery": {"bfs": 0.0}}

        for _ in range(20):
            update_mastery(state, "bfs", "correct")

        assert state["mastery"]["bfs"] > 0.9
