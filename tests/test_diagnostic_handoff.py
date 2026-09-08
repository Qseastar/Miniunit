from copy import deepcopy
from pathlib import Path

import pytest

from introai_tutor.diagnostic_handoff import (
    DEFAULT_INTENT,
    DiagnosticHandoffError,
    DiagnosticHandoffService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import (
    TemplateSelectionService,
    load_diagnostic_templates,
)


ROOT = Path(__file__).resolve().parents[1]
MISCONCEPTIONS = {
    "bfs_is_depth_first",
    "bfs_always_cost_optimal",
    "ucs_uses_depth_or_step_count",
}


def _concept_ids():
    return {
        point["id"]
        for point in load_knowledge_points(
            ROOT / "data" / "knowledge_points.json"
        )["knowledge_points"]
    }


def _service() -> DiagnosticHandoffService:
    templates = load_diagnostic_templates(
        ROOT / "data" / "diagnostic_templates.json",
        valid_concept_ids=_concept_ids(),
        valid_misconception_ids=MISCONCEPTIONS,
    )
    return DiagnosticHandoffService(
        template_selection_service=TemplateSelectionService(
            templates_data=templates,
            valid_concept_ids=_concept_ids(),
            valid_misconception_ids=MISCONCEPTIONS,
        )
    )


def test_bfs_and_optimality_prioritize_equal_cost_template_by_match_count():
    plan = _service().plan(
        topic_ids=["breadth_first_search", "completeness_optimality_complexity"],
        intent="comparison",
    )

    assert plan["available"] is True
    assert plan["template_ids"] == [
        "verify_bfs_equal_cost_condition_v1",
        "verify_search_algorithm_properties_v1",
    ]
    assert plan["matched_concept_ids"] == {
        "verify_bfs_equal_cost_condition_v1": [
            "breadth_first_search",
            "completeness_optimality_complexity",
        ],
        "verify_search_algorithm_properties_v1": [
            "completeness_optimality_complexity"
        ],
    }
    assert plan["uncovered_topic_ids"] == []
    assert plan["evidence_eligible"] is False
    assert plan["evidence_policy"] == "mastery_verification_only"


def test_bfs_only_uses_related_templates_and_prefers_full_template_coverage():
    plan = _service().plan(topic_ids=["breadth_first_search"], intent="explanation")

    assert plan["template_ids"] == ["verify_bfs_frontier_choice_v1"]
    assert "verify_ucs_min_g_choice_v1" not in plan["template_ids"]


def test_ucs_topic_selects_only_reviewed_ucs_template():
    plan = _service().plan(topic_ids=["uniform_cost_search"], intent="comparison")

    assert plan["available"] is True
    assert plan["template_ids"] == ["verify_ucs_min_g_choice_v1"]
    assert plan["matched_concept_ids"] == {
        "verify_ucs_min_g_choice_v1": ["uniform_cost_search"]
    }


def test_valid_concept_without_reviewed_template_is_a_safe_unavailable_result():
    # P5b promotes a reviewed Local Search template.  Keep this regression on
    # a valid concept that intentionally remains outside the reviewed bank.
    topics = ["llm_search_and_test_time_scaling"]
    original = deepcopy(topics)

    plan = _service().plan(topic_ids=topics, intent="explanation")

    assert topics == original
    assert plan["available"] is False
    assert plan["template_ids"] == []
    assert plan["uncovered_topic_ids"] == ["llm_search_and_test_time_scaling"]
    assert plan["message"] == "当前没有与本问题对应的审核验证题，本次仅提供课程回答。"


def test_unknown_concept_is_rejected_and_duplicate_topics_are_safely_deduplicated():
    service = _service()
    topics = ["breadth_first_search", "breadth_first_search"]
    original = deepcopy(topics)

    plan = service.plan(topic_ids=topics, intent=None)

    assert topics == original
    assert plan["topic_ids"] == ["breadth_first_search"]
    assert plan["intent"] == DEFAULT_INTENT
    with pytest.raises(DiagnosticHandoffError, match="Unknown concept"):
        service.plan(topic_ids=["not_a_concept"], intent="explanation")


def test_identical_input_and_limit_produce_identical_order_and_respect_limit():
    service = _service()
    first = service.plan(
        topic_ids=["breadth_first_search", "completeness_optimality_complexity"],
        intent="comparison",
        max_templates=1,
    )
    second = service.plan(
        topic_ids=["breadth_first_search", "completeness_optimality_complexity"],
        intent="comparison",
        max_templates=1,
    )

    assert first == second
    assert first["template_ids"] == ["verify_bfs_equal_cost_condition_v1"]
    assert first["uncovered_topic_ids"] == []


@pytest.mark.parametrize("value", [0, 11, True, "3"])
def test_max_templates_requires_a_bounded_positive_integer(value):
    with pytest.raises(DiagnosticHandoffError, match="max_templates"):
        _service().plan(
            topic_ids=["breadth_first_search"],
            intent="explanation",
            max_templates=value,
        )


class _UntrustedSelector:
    def __init__(self, templates):
        self.templates = templates
        self.calls = []

    def select(self, *, concept_ids, intent):
        self.calls.append((list(concept_ids), intent))
        return deepcopy(self.templates)


def _template(template_id, **overrides):
    value = {
        "id": template_id,
        "review_status": "human_verified",
        "purpose": "mastery_verification",
        "concept_ids": ["breadth_first_search"],
        "deterministic_scorer": "single_choice_v1",
        "selection_priority": 1,
    }
    value.update(overrides)
    return value


def test_only_human_reviewed_deterministic_mastery_templates_can_enter_plan():
    selector = _UntrustedSelector([
        _template("eligible"),
        _template("unreviewed", review_status="codex_draft"),
        _template("formative", purpose="formative"),
        _template("unknown_scorer", deterministic_scorer="llm_score_v1"),
        _template("unrelated", concept_ids=["uniform_cost_search"]),
    ])
    plan = DiagnosticHandoffService(template_selection_service=selector).plan(
        topic_ids=["breadth_first_search"], intent="explanation"
    )

    assert selector.calls == [(["breadth_first_search"], "explanation")]
    assert plan["template_ids"] == ["eligible"]


def test_plan_from_real_tutor_service_shape_uses_nested_validated_topics_without_mutation():
    service = _service()
    qa_result = {
        "question": "BFS 和总代价最优有什么关系？",
        "understanding": {
            "in_scope": True,
            "intent": "comparison",
            "topic_ids": [
                "breadth_first_search",
                "completeness_optimality_complexity",
                "uniform_cost_search",
            ],
            "diagnostic_topic_ids": [
                "breadth_first_search",
                "completeness_optimality_complexity",
            ],
            "supporting_topic_ids": ["uniform_cost_search"],
            "search_terms": ["BFS", "path cost"],
            "needs_clarification": False,
            "clarifying_question": None,
            "confidence": 0.9,
        },
        "response": {"status": "answered"},
    }
    original = deepcopy(qa_result)

    plan = service.plan_from_qa_result(qa_result=qa_result)

    assert qa_result == original
    assert plan["topic_ids"] == [
        "breadth_first_search",
        "completeness_optimality_complexity",
    ]
    assert plan["planning_topic_ids"] == plan["topic_ids"]
    assert plan["all_topic_ids"] == qa_result["understanding"]["topic_ids"]
    assert plan["supporting_topic_ids"] == ["uniform_cost_search"]
    assert plan["planning_source"] == "diagnostic_topic_ids"
    assert plan["template_ids"] == [
        "verify_bfs_equal_cost_condition_v1",
        "verify_search_algorithm_properties_v1",
    ]
    assert "verify_ucs_min_g_choice_v1" not in plan["template_ids"]


def test_plan_from_direct_question_understanding_shape_is_also_supported():
    understanding = {
        "in_scope": True,
        "intent": "definition",
        "topic_ids": ["uniform_cost_search", "frontier_and_explored_set"],
        "diagnostic_topic_ids": ["uniform_cost_search"],
        "supporting_topic_ids": ["frontier_and_explored_set"],
        "search_terms": ["UCS"],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.9,
    }
    original = deepcopy(understanding)

    plan = _service().plan_from_qa_result(qa_result=understanding)

    assert understanding == original
    assert plan["template_ids"] == ["verify_ucs_min_g_choice_v1"]
    assert plan["planning_topic_ids"] == ["uniform_cost_search"]
    assert plan["all_topic_ids"] == [
        "uniform_cost_search",
        "frontier_and_explored_set",
    ]
    assert plan["supporting_topic_ids"] == ["frontier_and_explored_set"]
    assert plan["planning_source"] == "diagnostic_topic_ids"


def test_iddfs_property_handoff_is_bounded_and_does_not_pull_in_bfs():
    question = (
        "请解释迭代加深深度优先搜索（IDDFS）是否完备，以及它在什么条件下是最优的。"
        "我想做一道相关的诊断题。"
    )
    plan = _service().plan_from_qa_result(
        qa_result={
            "question": question,
            "understanding": {
                "in_scope": True,
                "intent": "diagnostic_request",
                "topic_ids": [
                    "iterative_deepening_search",
                    "completeness_optimality_complexity",
                    "breadth_first_search",
                ],
                "diagnostic_topic_ids": [
                    "iterative_deepening_search",
                    "completeness_optimality_complexity",
                ],
                "supporting_topic_ids": ["breadth_first_search"],
                "search_terms": ["IDDFS", "完备", "最优"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            },
        }
    )

    assert plan["template_ids"] == [
        "verify_iddfs_depth_limit_schedule_v1",
        "verify_search_algorithm_properties_v1",
    ]
    assert len(plan["template_ids"]) <= 2
    assert "verify_bfs_equal_cost_condition_v1" not in plan["template_ids"]


def test_same_primary_concept_uses_question_relevance_to_choose_one_template():
    plan = _service().plan_from_qa_result(
        qa_result={
            "question": "在 A* 搜索中，g(N)=4、h(N)=3 时，f(N) 等于多少？请用一道诊断题测试我。",
            "understanding": {
                "in_scope": True,
                "intent": "diagnostic_request",
                "topic_ids": ["a_star_search"],
                "diagnostic_topic_ids": ["a_star_search"],
                "supporting_topic_ids": [],
                "search_terms": ["A*", "g(n)", "h(n)", "f(n)"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            },
        }
    )

    assert plan["template_ids"] == ["verify_astar_f_value_v1"]


@pytest.mark.parametrize(
    ("question", "primary_concept", "template_id"),
    [
        (
            "搜索问题由哪些部分组成？",
            "search_problem_formulation",
            "verify_search_problem_components_v1",
        ),
        (
            "八数码中的一次合法操作会怎样产生后继状态？",
            "state_space_and_operators",
            "verify_successor_operator_v1",
        ),
        (
            "frontier 和 explored set 分别保存什么？",
            "frontier_and_explored_set",
            "verify_frontier_explored_membership_v1",
        ),
    ],
)
def test_promoted_template_handoff_uses_only_diagnostic_primary_topic(
    question, primary_concept, template_id
):
    understanding = {
        "in_scope": True,
        "intent": "definition",
        "topic_ids": [primary_concept, "uniform_cost_search"],
        "diagnostic_topic_ids": [primary_concept],
        "supporting_topic_ids": ["uniform_cost_search"],
        "search_terms": [question],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.95,
    }
    original = deepcopy(understanding)

    plan = _service().plan_from_qa_result(
        qa_result={"question": question, "understanding": understanding}
    )

    assert understanding == original
    assert plan["available"] is True
    assert plan["template_ids"] == [template_id]
    assert plan["planning_topic_ids"] == [primary_concept]
    assert plan["supporting_topic_ids"] == ["uniform_cost_search"]
    assert "verify_ucs_min_g_choice_v1" not in plan["template_ids"]


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("question", "primary_concept", "template_id"),
    [
        (
            "graph search 怎样处理重复状态？",
            "tree_search_vs_graph_search",
            "verify_graph_search_repeated_state_handling_v1",
        ),
        (
            "DFS 使用 stack 时下一步扩展哪个节点？",
            "depth_first_search",
            "verify_dfs_frontier_choice_v1",
        ),
        (
            "IDDFS 怎样逐步增加深度限制？",
            "iterative_deepening_search",
            "verify_iddfs_depth_limit_schedule_v1",
        ),
    ],
)
def test_p2d_handoff_uses_only_diagnostic_primary_topic_and_is_stable(
    question, primary_concept, template_id
):
    understanding = {
        "in_scope": True,
        "intent": "definition",
        "topic_ids": [primary_concept, "frontier_and_explored_set"],
        "diagnostic_topic_ids": [primary_concept],
        "supporting_topic_ids": ["frontier_and_explored_set"],
        "search_terms": [question],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.95,
    }
    qa_result = {"question": question, "understanding": understanding}
    original = deepcopy(qa_result)

    first = _service().plan_from_qa_result(qa_result=qa_result)
    second = _service().plan_from_qa_result(qa_result=qa_result)

    assert qa_result == original
    assert first == second
    assert first["available"] is True
    assert first["template_ids"] == [template_id]
    assert first["planning_topic_ids"] == [primary_concept]
    assert first["supporting_topic_ids"] == ["frontier_and_explored_set"]
    assert first["matched_concept_ids"] == {template_id: [primary_concept]}


@pytest.mark.smoke
def test_real_dfs_algorithm_trace_handoff_uses_primary_topic_only():
    understanding = {
        "in_scope": True,
        "intent": "algorithm_trace",
        "topic_ids": ["depth_first_search", "frontier_and_explored_set"],
        "diagnostic_topic_ids": ["depth_first_search"],
        "supporting_topic_ids": ["frontier_and_explored_set"],
        "search_terms": ["DFS", "stack", "frontier", "next node"],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.95,
    }
    original = deepcopy(understanding)

    plan = _service().plan_from_qa_result(
        qa_result={
            "question": "DFS 使用 stack 管理 frontier 时，下一步应该扩展哪个节点？",
            "understanding": understanding,
        }
    )

    assert understanding == original
    assert plan["available"] is True
    assert plan["intent"] == "algorithm_trace"
    assert plan["template_ids"] == ["verify_dfs_frontier_choice_v1"]
    assert plan["matched_concept_ids"] == {
        "verify_dfs_frontier_choice_v1": ["depth_first_search"]
    }
    assert plan["planning_topic_ids"] == ["depth_first_search"]
    assert plan["supporting_topic_ids"] == ["frontier_and_explored_set"]
    assert plan["uncovered_topic_ids"] == []


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("intent", "primary_concept", "template_id"),
    [
        (
            "definition",
            "informed_search_and_heuristics",
            "verify_informed_search_g_h_roles_v1",
        ),
        (
            "algorithm_trace",
            "greedy_best_first_search",
            "verify_greedy_min_h_choice_v1",
        ),
        (
            "algorithm_trace",
            "a_star_search",
            "verify_astar_min_f_choice_v1",
        ),
        (
            "definition",
            "admissibility_and_consistency",
            "verify_admissibility_no_overestimate_v1",
        ),
    ],
)
def test_p2e_handoff_uses_only_diagnostic_primary_topic_and_is_stable(
    intent, primary_concept, template_id
):
    understanding = {
        "in_scope": True,
        "intent": intent,
        "topic_ids": [primary_concept, "frontier_and_explored_set"],
        "diagnostic_topic_ids": [primary_concept],
        "supporting_topic_ids": ["frontier_and_explored_set"],
        "search_terms": [primary_concept],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.9,
    }
    original = deepcopy(understanding)

    first = _service().plan_from_qa_result(qa_result=understanding)
    second = _service().plan_from_qa_result(qa_result=understanding)

    assert understanding == original
    assert first == second
    assert first["available"] is True
    assert first["template_ids"] == [template_id]
    assert first["planning_source"] == "diagnostic_topic_ids"
    assert first["planning_topic_ids"] == [primary_concept]
    assert first["supporting_topic_ids"] == ["frontier_and_explored_set"]


def test_property_intent_selects_only_reviewed_property_template():
    understanding = {
        "in_scope": True,
        "intent": "property",
        "topic_ids": ["a_star_search", "admissibility_and_consistency"],
        "diagnostic_topic_ids": [
            "a_star_search",
            "admissibility_and_consistency",
        ],
        "supporting_topic_ids": [],
        "search_terms": ["A*", "admissible heuristic"],
        "needs_clarification": False,
        "clarifying_question": None,
        "confidence": 0.9,
    }

    plan = _service().plan_from_qa_result(qa_result=understanding)

    assert plan["available"] is True
    assert plan["template_ids"] == ["verify_consistency_edge_check_v1"]
    assert plan["planning_topic_ids"] == understanding["diagnostic_topic_ids"]
    assert plan["all_topic_ids"] == understanding["topic_ids"]
    assert plan["planning_source"] == "diagnostic_topic_ids"


def test_explicit_empty_diagnostic_topics_do_not_fall_back_to_supporting_topics():
    understanding = {
        "in_scope": True,
        "intent": "comparison",
        "topic_ids": ["uniform_cost_search"],
        "diagnostic_topic_ids": [],
        "supporting_topic_ids": ["uniform_cost_search"],
        "needs_clarification": False,
    }

    plan = _service().plan_from_qa_result(qa_result=understanding)

    assert plan["available"] is False
    assert plan["template_ids"] == []
    assert plan["planning_topic_ids"] == []
    assert plan["all_topic_ids"] == ["uniform_cost_search"]
    assert plan["supporting_topic_ids"] == ["uniform_cost_search"]
    assert plan["planning_source"] == "diagnostic_topic_ids"


def test_legacy_understanding_without_role_fields_falls_back_to_all_topics():
    understanding = {
        "in_scope": True,
        "intent": "comparison",
        "topic_ids": ["uniform_cost_search"],
        "needs_clarification": False,
    }
    original = deepcopy(understanding)

    plan = _service().plan_from_qa_result(qa_result=understanding)

    assert understanding == original
    assert plan["template_ids"] == ["verify_ucs_min_g_choice_v1"]
    assert plan["planning_topic_ids"] == ["uniform_cost_search"]
    assert plan["all_topic_ids"] == ["uniform_cost_search"]
    assert plan["supporting_topic_ids"] == []
    assert plan["planning_source"] == "legacy_topic_ids_fallback"


@pytest.mark.parametrize(
    "understanding, message",
    [
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": ["breadth_first_search"],
            },
            "must be provided together",
        ),
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": "breadth_first_search",
                "supporting_topic_ids": [],
            },
            "must be a list",
        ),
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": [1],
                "supporting_topic_ids": [],
            },
            "non-empty string",
        ),
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": [" "],
                "supporting_topic_ids": ["breadth_first_search"],
            },
            "non-empty string",
        ),
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": [
                    "breadth_first_search",
                    "breadth_first_search",
                ],
                "supporting_topic_ids": [],
            },
            "duplicates",
        ),
        (
            {
                "topic_ids": ["breadth_first_search", "invented_concept"],
                "diagnostic_topic_ids": ["breadth_first_search"],
                "supporting_topic_ids": ["invented_concept"],
            },
            "Unknown concept",
        ),
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": ["uniform_cost_search"],
                "supporting_topic_ids": [],
            },
            "subset of topic_ids",
        ),
        (
            {
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": ["breadth_first_search"],
                "supporting_topic_ids": ["breadth_first_search"],
            },
            "must not overlap",
        ),
        (
            {
                "topic_ids": ["breadth_first_search", "uniform_cost_search"],
                "diagnostic_topic_ids": ["breadth_first_search"],
                "supporting_topic_ids": [],
            },
            "must cover topic_ids",
        ),
        (
            {
                "in_scope": False,
                "intent": "out_of_scope",
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": ["breadth_first_search"],
                "supporting_topic_ids": [],
            },
            "out-of-scope",
        ),
        (
            {
                "in_scope": True,
                "intent": "comparison",
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": ["breadth_first_search"],
                "supporting_topic_ids": [],
                "needs_clarification": True,
            },
            "clarification",
        ),
    ],
)
def test_role_aware_handoff_rejects_invalid_topic_contract(understanding, message):
    understanding.setdefault("in_scope", True)
    understanding.setdefault("intent", "explanation")
    understanding.setdefault("needs_clarification", False)

    with pytest.raises(DiagnosticHandoffError, match=message):
        _service().plan_from_qa_result(qa_result={"understanding": understanding})


@pytest.mark.parametrize(
    "qa_result, message",
    [
        ({}, "当前回答未提供可用于掌握度验证的课程知识点。"),
        (
            {"understanding": {"in_scope": False, "intent": "out_of_scope"}},
            "该问题不在当前课程范围内，暂不提供掌握度验证题。",
        ),
        (
            {
                "understanding": {
                    "in_scope": True,
                    "intent": "comparison",
                    "topic_ids": ["breadth_first_search"],
                    "needs_clarification": True,
                }
            },
            "当前问题仍需澄清，暂不提供掌握度验证题。",
        ),
    ],
)
def test_missing_out_of_scope_or_clarifying_qa_result_is_safely_unavailable(
    qa_result, message
):
    plan = _service().plan_from_qa_result(qa_result=qa_result)

    assert plan["available"] is False
    assert plan["template_ids"] == []
    assert plan["evidence_eligible"] is False
    assert plan["message"] == message


def test_invalid_qa_topics_are_rejected_without_creating_any_diagnostic_session():
    with pytest.raises(DiagnosticHandoffError, match="Unknown concept"):
        _service().plan_from_qa_result(
            qa_result={
                "understanding": {
                    "in_scope": True,
                    "intent": "explanation",
                    "topic_ids": ["unknown_concept"],
                    "needs_clarification": False,
                }
            }
        )
