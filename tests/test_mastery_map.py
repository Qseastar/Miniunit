"""Offline contracts for the fixed Search Algorithms mastery-map view model."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

import app as streamlit_app
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.ui_formatting import reset_session_state
from introai_tutor.ui_scroll import consume_scroll_request, scroll_script_markup
from introai_tutor.mastery_map import (
    DISPLAY_REVIEW_THRESHOLD,
    DISPLAY_STEADY_THRESHOLD,
    MasteryMapError,
    build_concept_coverage,
    build_concept_detail,
    build_mastery_map_model,
    classify_mastery_for_display,
    concept_question_prefill,
    default_selected_concept_id,
    load_mastery_map_layout,
    validate_mastery_map_layout,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def knowledge_data():
    return load_knowledge_points(ROOT / "data" / "knowledge_points.json")


@pytest.fixture()
def layout_data():
    return load_mastery_map_layout(ROOT / "data" / "search_algorithms_mastery_map_layout.json")


@pytest.fixture()
def templates_data():
    return json.loads((ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8"))


def _model(knowledge_data, layout_data, templates_data, mastery=None, recommendation=None):
    return build_mastery_map_model(
        knowledge_data=knowledge_data,
        layout_data=layout_data,
        templates_data=templates_data,
        learner_state={"mastery": mastery or {}, "learning_evidence": []},
        recommendation=recommendation,
    )


def test_layout_contains_every_registry_concept_once_and_only_presentation_fields(
    knowledge_data, layout_data
):
    validate_mastery_map_layout(layout_data, knowledge_data)

    registry_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
    assert {node["concept_id"] for node in layout_data["nodes"]} == registry_ids
    assert all(set(node) == {"concept_id", "layer", "order"} for node in layout_data["nodes"])
    assert len(layout_data["nodes"]) == len(registry_ids) == 26
    assert len({(node["layer"], node["order"]) for node in layout_data["nodes"]}) == 26


def test_layout_fails_closed_for_unknown_missing_or_bad_prerequisite_order(
    knowledge_data, layout_data
):
    unknown = deepcopy(layout_data)
    unknown["nodes"][0]["concept_id"] = "unknown_concept"
    with pytest.raises(MasteryMapError, match="unknown concept_id"):
        validate_mastery_map_layout(unknown, knowledge_data)

    missing = deepcopy(layout_data)
    missing["nodes"].pop()
    with pytest.raises(MasteryMapError, match="exactly match"):
        validate_mastery_map_layout(missing, knowledge_data)

    reversed_edge = deepcopy(layout_data)
    by_id = {node["concept_id"]: node for node in reversed_edge["nodes"]}
    by_id["breadth_first_search"]["layer"] = by_id["frontier_and_explored_set"]["layer"]
    by_id["breadth_first_search"]["order"] = 9
    with pytest.raises(MasteryMapError, match="must follow prerequisite"):
        validate_mastery_map_layout(reversed_edge, knowledge_data)


def test_layout_detects_cycle_in_authoritative_prerequisites(knowledge_data, layout_data):
    cyclic = deepcopy(knowledge_data)
    cyclic["knowledge_points"][0]["prerequisites"] = ["admissibility_and_consistency"]
    with pytest.raises(MasteryMapError, match="cycle"):
        validate_mastery_map_layout(layout_data, cyclic)


@pytest.mark.parametrize(
    ("tracked", "value", "expected"),
    [
        (False, None, "untracked"),
        (True, 0.0, "review"),
        (True, DISPLAY_REVIEW_THRESHOLD - 0.001, "review"),
        (True, DISPLAY_REVIEW_THRESHOLD, "developing"),
        (True, DISPLAY_STEADY_THRESHOLD - 0.001, "developing"),
        (True, DISPLAY_STEADY_THRESHOLD, "steady"),
        (True, 1.0, "steady"),
        (True, -0.1, "unavailable"),
        (True, 1.1, "unavailable"),
        (True, None, "unavailable"),
        (True, True, "unavailable"),
        (True, math.nan, "unavailable"),
        (True, math.inf, "unavailable"),
    ],
)
def test_mastery_display_bands_are_explicit_and_fail_safe(tracked, value, expected):
    display = classify_mastery_for_display(mastery_value=value, is_tracked=tracked)

    assert display["status"] == expected
    assert display["label"]
    assert display["css_token"].startswith("mastery-map-status-")
    assert display["is_tracked"] is tracked


def test_display_classification_does_not_mutate_a_learner_snapshot(
    knowledge_data, layout_data, templates_data
):
    learner_state = {"mastery": {"breadth_first_search": 0.0}, "learning_evidence": []}
    before = deepcopy(learner_state)

    model = build_mastery_map_model(
        knowledge_data=knowledge_data,
        layout_data=layout_data,
        templates_data=templates_data,
        learner_state=learner_state,
    )

    assert learner_state == before
    assert model["nodes_by_id"]["breadth_first_search"]["mastery"]["label"] == "建议复习"
    assert model["nodes_by_id"]["depth_first_search"]["mastery"]["label"] == "尚未追踪"


def test_coverage_uses_only_human_verified_primary_concepts(
    knowledge_data, templates_data
):
    coverage = build_concept_coverage(
        templates_data=templates_data, knowledge_data=knowledge_data
    )

    assert sum(item["template_count"] for item in coverage.values()) == 28
    assert coverage["breadth_first_search"]["template_count"] == 2
    assert coverage["completeness_optimality_complexity"]["template_count"] == 1
    assert coverage["uniform_cost_search"]["template_ids"] == ["verify_ucs_min_g_choice_v1"]
    assert coverage["local_search"]["available"] is True
    assert coverage["local_search"]["template_ids"] == ["verify_local_search_final_state_focus_v1"]

    only_supporting = {
        "schema_version": 1,
        "templates": [
            {
                "id": "reviewed_bfs_with_support",
                "review_status": "human_verified",
                "purpose": "mastery_verification",
                "concept_ids": ["breadth_first_search", "uniform_cost_search"],
                "selection_priority": 1,
            },
            {
                "id": "candidate_must_not_count",
                "review_status": "candidate_draft",
                "purpose": "mastery_verification",
                "concept_ids": ["uniform_cost_search"],
                "selection_priority": 999,
            },
        ],
    }
    support_coverage = build_concept_coverage(
        templates_data=only_supporting, knowledge_data=knowledge_data
    )
    assert support_coverage["breadth_first_search"]["template_ids"] == ["reviewed_bfs_with_support"]
    assert support_coverage["uniform_cost_search"]["template_ids"] == []


def test_coverage_fails_closed_for_unknown_primary_production_concept(
    knowledge_data, templates_data
):
    invalid = deepcopy(templates_data)
    invalid["templates"][0]["concept_ids"][0] = "unknown_concept"

    with pytest.raises(MasteryMapError, match="invalid primary"):
        build_concept_coverage(templates_data=invalid, knowledge_data=knowledge_data)


def test_model_is_stable_and_marks_only_a_valid_recommendation(
    knowledge_data, layout_data, templates_data
):
    recommendation = {"concept_id": "uniform_cost_search", "reason": "请先复习路径代价。"}
    first = _model(knowledge_data, layout_data, templates_data, recommendation=recommendation)
    second = _model(knowledge_data, layout_data, templates_data, recommendation=recommendation)

    assert first == second
    assert first["nodes_by_id"]["uniform_cost_search"]["is_recommended"] is True
    assert first["nodes_by_id"]["breadth_first_search"]["is_recommended"] is False
    assert default_selected_concept_id(map_model=first) == "uniform_cost_search"

    safe = _model(
        knowledge_data, layout_data, templates_data, recommendation={"concept_id": "unknown"}
    )
    assert safe["recommended_concept_id"] is None
    assert safe["warnings"]
    assert default_selected_concept_id(map_model=safe) == "search_problem_formulation"


def test_map_node_order_does_not_depend_on_layout_document_order(
    knowledge_data, layout_data, templates_data
):
    reordered = deepcopy(layout_data)
    reordered["nodes"].reverse()

    original = _model(knowledge_data, layout_data, templates_data)
    rebuilt = _model(knowledge_data, reordered, templates_data)

    assert rebuilt["layers"] == original["layers"]
    assert rebuilt["prerequisite_edges"] == original["prerequisite_edges"]


def test_detail_is_student_safe_and_evidence_summary_has_no_invented_timestamp(
    knowledge_data, layout_data, templates_data
):
    model = _model(
        knowledge_data,
        layout_data,
        templates_data,
        mastery={"iterative_deepening_search": 0.75},
        recommendation={"concept_id": "iterative_deepening_search", "reason": "继续巩固。"},
    )
    detail = build_concept_detail(
        map_model=model,
        concept_id="iterative_deepening_search",
        learning_evidence=[
            {"event_id": "opaque-event", "template_ids": ["verify_iddfs_depth_limit_schedule_v1"]},
            {"template_ids": ["verify_bfs_frontier_choice_v1"]},
        ],
    )

    assert detail["title_zh"] == "迭代加深深度优先搜索"
    assert detail["mastery"]["label"] == "初步掌握"
    assert detail["coverage"]["template_count"] == 1
    assert detail["prerequisites"]
    assert detail["evidence_summary"] == {
        "event_count": 1,
        "template_ids": ["verify_iddfs_depth_limit_schedule_v1"],
        "label": "已记录 1 次审核学习活动",
        "updated_at": None,
    }
    assert "student_id" not in detail
    assert concept_question_prefill(concept=detail) == "请结合课件讲解迭代加深深度优先搜索。"


def test_unknown_detail_and_untrusted_title_prefill_fail_closed(
    knowledge_data, layout_data, templates_data
):
    model = _model(knowledge_data, layout_data, templates_data)
    with pytest.raises(MasteryMapError, match="Unknown mastery-map"):
        build_concept_detail(map_model=model, concept_id="unknown")
    with pytest.raises(MasteryMapError, match="title"):
        concept_question_prefill(concept={"title_zh": "  "})


def test_profile_reset_clears_only_transient_mastery_map_selection():
    state = {
        "other_page_key": "preserved",
        "introai_mastery_map_selected_concept": "uniform_cost_search",
        "introai_mastery_map_view": "分层浏览",
        "introai_mastery_map_layer_filter": "review",
        "introai_pending_mastery_map_qa_question": "请结合课件讲解一致代价搜索。",
        "introai_mastery_map_navigation_message": "temporary",
    }

    reset_session_state(state)

    assert state == {"other_page_key": "preserved"}


class _MapActionStreamlit:
    def __init__(self, state):
        self.session_state = state


def test_node_selection_uses_new_transient_events_without_touching_learning_state():
    learner_state = {
        "mastery": {"iterative_deepening_search": 0.65},
        "learning_evidence": [{"template_ids": ["verify_iddfs_depth_limit_schedule_v1"]}],
    }
    state = {"introai_learner_state": deepcopy(learner_state)}
    st = _MapActionStreamlit(state)
    valid_ids = {"iterative_deepening_search", "a_star_search"}

    assert streamlit_app._select_mastery_map_concept(
        st, concept_id="iterative_deepening_search", valid_concept_ids=valid_ids
    )
    assert state["introai_mastery_map_selected_concept"] == "iterative_deepening_search"
    assert state["introai_mastery_map_action_revision"] == 1
    assert state["introai_scroll_request"] == {
        "target": "mastery_map_detail", "event_id": "mastery-map-action-1"
    }
    assert state["introai_learner_state"] == learner_state
    assert "introai_dual_track_session" not in state

    # A second, different selection receives a fresh event instead of relying
    # on the prior concept ID or a consumed event token.
    state.pop("introai_scroll_request")
    assert streamlit_app._select_mastery_map_concept(
        st, concept_id="a_star_search", valid_concept_ids=valid_ids
    )
    assert state["introai_mastery_map_action_revision"] == 2
    assert state["introai_scroll_request"] == {
        "target": "mastery_map_detail", "event_id": "mastery-map-action-2"
    }

    # Selecting the same node in a later explicit action is also scrollable.
    state.pop("introai_scroll_request")
    assert streamlit_app._select_mastery_map_concept(
        st, concept_id="a_star_search", valid_concept_ids=valid_ids
    )
    assert state["introai_mastery_map_action_revision"] == 3
    assert state["introai_scroll_request"]["event_id"] == "mastery-map-action-3"


def test_return_to_overview_preserves_selection_and_queues_only_the_graph_target():
    learner_state = {"mastery": {"a_star_search": 0.65}, "learning_evidence": []}
    state = {
        "introai_learner_state": deepcopy(learner_state),
        "introai_mastery_map_selected_concept": "a_star_search",
    }
    st = _MapActionStreamlit(state)

    assert streamlit_app._return_to_mastery_map_overview(st)
    assert state["introai_mastery_map_selected_concept"] == "a_star_search"
    assert state["introai_learner_state"] == learner_state
    assert consume_scroll_request(state) == {
        "target": "mastery_map_graph",
        "event_id": "mastery-map-action-1",
    }
    assert "introai_dual_track_session" not in state


def test_consecutive_and_same_concept_selection_remounts_a_unique_scroll_component():
    state = {"introai_learner_state": {"mastery": {}, "learning_evidence": []}}
    st = _MapActionStreamlit(state)
    valid_ids = {"iterative_deepening_search", "a_star_search"}
    component_payloads: list[str] = []

    for concept_id in (
        "iterative_deepening_search",
        "a_star_search",
        "a_star_search",
        "iterative_deepening_search",
    ):
        assert streamlit_app._select_mastery_map_concept(
            st, concept_id=concept_id, valid_concept_ids=valid_ids
        )
        request = consume_scroll_request(state)
        assert request is not None
        assert request["target"] == "mastery_map_detail"
        component_payloads.append(
            scroll_script_markup(
                request["target"], event_id=request["event_id"], activate_tab_index=2
            )
        )

    assert state["introai_mastery_map_selected_concept"] == "iterative_deepening_search"
    assert state["introai_mastery_map_action_revision"] == 4
    assert len(set(component_payloads)) == 4
    assert all("introai-scroll-mastery_map_detail" in item for item in component_payloads)
    assert "introai_dual_track_session" not in state
    assert state["introai_learner_state"] == {"mastery": {}, "learning_evidence": []}


def test_unknown_map_selection_fails_closed_without_creating_a_request():
    state = {"introai_learner_state": {"mastery": {}, "learning_evidence": []}}
    st = _MapActionStreamlit(state)
    before = deepcopy(state)

    with pytest.raises(MasteryMapError, match="Unknown mastery-map concept selection"):
        streamlit_app._select_mastery_map_concept(
            st, concept_id="learner-provided-text", valid_concept_ids={"a_star_search"}
        )

    assert state == before
