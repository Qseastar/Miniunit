import copy
import json
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import (
    DiagnosticTemplateError,
    TemplateSelectionService,
    load_diagnostic_templates,
)


ROOT = Path(__file__).resolve().parents[1]
MISCONCEPTIONS = {
    "bfs_is_depth_first",
    "bfs_always_cost_optimal",
    "ucs_uses_depth_or_step_count",
}


def _concepts():
    return {
        point["id"]
        for point in load_knowledge_points(ROOT / "data" / "knowledge_points.json")["knowledge_points"]
    }


def _templates():
    return load_diagnostic_templates(
        ROOT / "data" / "diagnostic_templates.json",
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )


def test_real_template_bank_is_human_reviewed_and_stably_selected():
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )
    selected = service.select(
        concept_ids=[
            "breadth_first_search",
            "completeness_optimality_complexity",
            "uniform_cost_search",
        ],
        intent="diagnostic_request",
    )

    assert [item["id"] for item in selected] == [
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_search_algorithm_properties_v1",
        "verify_ucs_min_g_choice_v1",
    ]
    assert selected == service.select(
        concept_ids=[
            "breadth_first_search",
            "completeness_optimality_complexity",
            "uniform_cost_search",
        ],
        intent="diagnostic_request",
    )


def test_template_loader_rejects_unknown_concept_and_duplicate_id(tmp_path):
    invalid = copy.deepcopy(_templates())
    invalid["templates"][0]["concept_ids"] = ["unknown_concept"]
    path = tmp_path / "templates.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(DiagnosticTemplateError, match="unknown concept"):
        load_diagnostic_templates(path, valid_concept_ids=_concepts())

    invalid = copy.deepcopy(_templates())
    invalid["templates"][1]["id"] = invalid["templates"][0]["id"]
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(DiagnosticTemplateError, match="Duplicate"):
        load_diagnostic_templates(path, valid_concept_ids=_concepts())


def test_selection_rejects_unknown_concept_instead_of_silently_ignoring_it():
    service = TemplateSelectionService(templates_data=_templates(), valid_concept_ids=_concepts())
    with pytest.raises(DiagnosticTemplateError, match="Unknown concept"):
        service.select(concept_ids=["not_a_concept"], intent="diagnostic_request")


def test_selection_returns_empty_for_valid_concept_without_reviewed_template():
    service = TemplateSelectionService(templates_data=_templates(), valid_concept_ids=_concepts())

    assert service.select(
        # P5b promotes Local Search; this concept remains intentionally
        # unsupported by the reviewed verification bank.
        concept_ids=["llm_search_and_test_time_scaling"], intent="diagnostic_request"
    ) == []


def test_definition_intent_is_enabled_only_for_reviewed_mechanism_templates():
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    assert [
        template["id"]
        for template in service.select(
            concept_ids=["uniform_cost_search"], intent="definition"
        )
    ] == ["verify_ucs_min_g_choice_v1"]
    assert service.select(
        concept_ids=["breadth_first_search"], intent="definition"
    ) == []
    assert [
        template["id"]
        for template in service.select(
            concept_ids=["a_star_search"], intent="definition"
        )
    ] == ["verify_astar_min_f_choice_v1", "verify_astar_f_value_v1"]


@pytest.mark.parametrize(
    ("concept_id", "template_id"),
    [
        (
            "search_problem_formulation",
            "verify_search_problem_components_v1",
        ),
        (
            "state_space_and_operators",
            "verify_successor_operator_v1",
        ),
        (
            "frontier_and_explored_set",
            "verify_frontier_explored_membership_v1",
        ),
    ],
)
def test_promoted_templates_are_stably_selected_only_for_primary_concept(
    concept_id, template_id
):
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    selected = service.select(concept_ids=[concept_id], intent="definition")

    expected = [template_id]
    if concept_id == "search_problem_formulation":
        expected.append("verify_path_cost_accumulation_v1")
    assert [template["id"] for template in selected] == expected
    assert selected == service.select(
        concept_ids=[concept_id], intent="definition"
    )


@pytest.mark.parametrize(
    ("concept_id", "template_id"),
    [
        (
            "tree_search_vs_graph_search",
            "verify_graph_search_repeated_state_handling_v1",
        ),
        ("depth_first_search", "verify_dfs_frontier_choice_v1"),
        (
            "iterative_deepening_search",
            "verify_iddfs_depth_limit_schedule_v1",
        ),
    ],
)
def test_p2d_promoted_templates_are_stably_selected_only_for_primary_concept(
    concept_id, template_id
):
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    first = service.select(concept_ids=[concept_id], intent="definition")
    second = service.select(concept_ids=[concept_id], intent="definition")

    expected = [template_id]
    if concept_id == "tree_search_vs_graph_search":
        expected.append("verify_search_node_state_distinction_v1")
    assert [template["id"] for template in first] == expected
    assert first == second
    assert first[0]["concept_ids"] == [concept_id]


def test_p2d_promotion_preserves_existing_selection_order():
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    assert [
        template["id"]
        for template in service.select(
            concept_ids=["breadth_first_search"], intent="explanation"
        )
    ] == [
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
    ]
    assert [
        template["id"]
        for template in service.select(
            concept_ids=["uniform_cost_search"], intent="definition"
        )
    ] == ["verify_ucs_min_g_choice_v1"]
    assert [
        template["id"]
        for template in service.select(
            concept_ids=["a_star_search"], intent="explanation"
        )
    ] == ["verify_astar_min_f_choice_v1", "verify_astar_f_value_v1"]


@pytest.mark.parametrize(
    ("concept_id", "intent", "template_id"),
    [
        (
            "informed_search_and_heuristics",
            "comparison",
            "verify_informed_search_g_h_roles_v1",
        ),
        (
            "greedy_best_first_search",
            "algorithm_trace",
            "verify_greedy_min_h_choice_v1",
        ),
        ("a_star_search", "algorithm_trace", "verify_astar_min_f_choice_v1"),
        (
            "admissibility_and_consistency",
            "definition",
            "verify_admissibility_no_overestimate_v1",
        ),
    ],
)
def test_p2e_promoted_templates_use_approved_eligible_intents(
    concept_id, intent, template_id
):
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    selected = service.select(concept_ids=[concept_id], intent=intent)

    expected = [template_id]
    if concept_id == "a_star_search":
        expected.append("verify_astar_f_value_v1")
    if concept_id == "admissibility_and_consistency":
        expected.append("verify_consistency_edge_check_v1")
    assert [template["id"] for template in selected] == expected
    assert selected[0]["concept_ids"] == [concept_id]


def test_dfs_algorithm_trace_selects_only_the_reviewed_frontier_template():
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    selected = service.select(
        concept_ids=["depth_first_search"], intent="algorithm_trace"
    )

    assert [template["id"] for template in selected] == [
        "verify_dfs_frontier_choice_v1"
    ]
    assert selected[0]["eligible_intents"] == [
        "diagnostic_request",
        "definition",
        "explanation",
        "algorithm_trace",
    ]


def test_algorithm_trace_eligibility_was_not_globally_enabled():
    service = TemplateSelectionService(
        templates_data=_templates(),
        valid_concept_ids=_concepts(),
        valid_misconception_ids=MISCONCEPTIONS,
    )

    assert service.select(
        concept_ids=["tree_search_vs_graph_search"], intent="algorithm_trace"
    ) == []
    assert service.select(
        concept_ids=["iterative_deepening_search"], intent="algorithm_trace"
    ) == []
