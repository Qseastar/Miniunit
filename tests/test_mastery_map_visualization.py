"""Offline contracts for the deterministic P3c visual mastery-map layer."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

import app as streamlit_app

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.mastery_map import MasteryMapError, build_mastery_map_model, load_mastery_map_layout
from introai_tutor.mastery_map_visualization import (
    LAYER_FILTERS,
    LAYER_STAGE_NAMES,
    build_global_mastery_dot,
    build_visual_mastery_map_model,
    dot_escape,
    filter_layered_nodes,
    load_concept_copy_zh,
    validate_concept_copy_zh,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def knowledge_data():
    return load_knowledge_points(ROOT / "data" / "knowledge_points.json")


@pytest.fixture()
def concept_copy_data():
    return load_concept_copy_zh(ROOT / "data" / "search_algorithms_concept_copy_zh.json")


def _visual(knowledge_data, concept_copy_data, *, mastery=None, recommendation=None, selected="uniform_cost_search"):
    map_model = build_mastery_map_model(
        knowledge_data=knowledge_data,
        layout_data=load_mastery_map_layout(ROOT / "data" / "search_algorithms_mastery_map_layout.json"),
        templates_data=json.loads((ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8")),
        learner_state={"mastery": mastery or {}, "learning_evidence": []},
        recommendation=recommendation,
    )
    return build_visual_mastery_map_model(
        map_model=map_model,
        concept_copy_data=concept_copy_data,
        knowledge_data=knowledge_data,
        selected_concept_id=selected,
    )


def test_chinese_copy_exactly_covers_registry_with_bounded_student_text(knowledge_data, concept_copy_data):
    validate_concept_copy_zh(concept_copy_data, knowledge_data)

    registry_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
    copy_ids = {item["concept_id"] for item in concept_copy_data["concepts"]}
    assert copy_ids == registry_ids
    assert len(copy_ids) == 26
    assert all(25 <= len(item["summary_zh"]) <= 70 for item in concept_copy_data["concepts"])
    assert all("_" not in item["summary_zh"] and "{{" not in item["summary_zh"] for item in concept_copy_data["concepts"])


def test_chinese_copy_fails_closed_for_unknown_duplicate_placeholder_or_english_fragment(knowledge_data, concept_copy_data):
    unknown = deepcopy(concept_copy_data)
    unknown["concepts"][0]["concept_id"] = "unknown"
    with pytest.raises(MasteryMapError, match="unknown concept_id"):
        validate_concept_copy_zh(unknown, knowledge_data)

    duplicate = deepcopy(concept_copy_data)
    duplicate["concepts"][1]["concept_id"] = duplicate["concepts"][0]["concept_id"]
    with pytest.raises(MasteryMapError, match="Duplicate"):
        validate_concept_copy_zh(duplicate, knowledge_data)

    implementation_text = deepcopy(concept_copy_data)
    implementation_text["concepts"][0]["summary_zh"] = "请使用 search_problem_formulation 作为 {{TODO}} 占位内容，然后继续阅读说明。"
    with pytest.raises(MasteryMapError, match="implementation text"):
        validate_concept_copy_zh(implementation_text, knowledge_data)

    english = deepcopy(concept_copy_data)
    english["concepts"][0]["summary_zh"] = "Thisdescription 应当被拒绝，因为学生端中文说明不能粘贴大段英文内容。"
    with pytest.raises(MasteryMapError, match="long English"):
        validate_concept_copy_zh(english, knowledge_data)


def test_visual_model_uses_all_registry_nodes_real_edges_layers_and_direct_dependents(knowledge_data, concept_copy_data):
    visual = _visual(
        knowledge_data,
        concept_copy_data,
        mastery={"breadth_first_search": 0.0, "uniform_cost_search": 0.65, "a_star_search": 0.9},
        recommendation={"concept_id": "uniform_cost_search", "reason": "继续学习。"},
    )

    assert len(visual["nodes_by_id"]) == 26
    assert len(visual["edges"]) == 30
    assert len({(edge["prerequisite_id"], edge["dependent_id"]) for edge in visual["edges"]}) == 30
    assert all(edge["prerequisite_id"] != edge["dependent_id"] for edge in visual["edges"])
    assert {layer["layer"] for layer in visual["layers"]} == set(LAYER_STAGE_NAMES)
    assert [layer["stage_name"] for layer in visual["layers"]] == [LAYER_STAGE_NAMES[index] for index in range(10)]
    assert visual["nodes_by_id"]["uniform_cost_search"]["is_selected"] is True
    assert visual["nodes_by_id"]["uniform_cost_search"]["is_recommended"] is True
    assert visual["nodes_by_id"]["breadth_first_search"]["mastery"]["status"] == "review"
    assert visual["nodes_by_id"]["uniform_cost_search"]["mastery"]["status"] == "developing"
    assert visual["nodes_by_id"]["a_star_search"]["mastery"]["status"] == "steady"
    assert visual["focus"]["selected"]["title_zh"] == "一致代价搜索"
    assert [node["concept_id"] for node in visual["focus"]["dependents"]] == ["informed_search_and_heuristics", "a_star_search"]
    assert visual["summary"] == {
        "total": 26,
        "tracked": 3,
        "untracked": 23,
        "review": 1,
        "developing": 1,
        "steady": 1,
        "covered": 21,
    }


def test_unknown_selected_concept_degrades_without_inventing_a_node(knowledge_data, concept_copy_data):
    visual = _visual(knowledge_data, concept_copy_data, selected="unknown_user_text")

    assert visual["selected_concept_id"] is None
    assert visual["focus"] is None
    assert all(not edge["is_selected_incident"] for edge in visual["edges"])
    assert "unknown_user_text" not in visual["global_dot"]


def test_layer_filters_are_display_only_and_fail_closed(knowledge_data, concept_copy_data):
    visual = _visual(
        knowledge_data,
        concept_copy_data,
        mastery={"breadth_first_search": 0.2},
        recommendation={"concept_id": "uniform_cost_search", "reason": "继续学习。"},
    )
    before = deepcopy(visual["layers"])

    assert sum(len(layer["nodes"]) for layer in filter_layered_nodes(visual["layers"], filter_key="all")) == 26
    assert [node["concept_id"] for layer in filter_layered_nodes(visual["layers"], filter_key="recommended") for node in layer["nodes"]] == ["uniform_cost_search"]
    assert [node["concept_id"] for layer in filter_layered_nodes(visual["layers"], filter_key="tracked") for node in layer["nodes"]] == ["breadth_first_search"]
    assert [node["concept_id"] for layer in filter_layered_nodes(visual["layers"], filter_key="review") for node in layer["nodes"]] == ["breadth_first_search"]
    assert sum(len(layer["nodes"]) for layer in filter_layered_nodes(visual["layers"], filter_key="covered")) == 21
    assert visual["layers"] == before
    assert set(LAYER_FILTERS) == {"all", "recommended", "tracked", "covered", "review"}
    with pytest.raises(MasteryMapError, match="Unknown mastery-map layer filter"):
        filter_layered_nodes(visual["layers"], filter_key="learner text")


def test_dot_is_stable_escaped_and_uses_aliases_instead_of_student_visible_ids(knowledge_data, concept_copy_data):
    visual = _visual(
        knowledge_data,
        concept_copy_data,
        mastery={"uniform_cost_search": 0.65},
        recommendation={"concept_id": "uniform_cost_search", "reason": "continue"},
    )
    first = build_global_mastery_dot(visual)
    second = build_global_mastery_dot(visual)

    assert first == second == visual["global_dot"]
    assert first.count(" [label=") == 26
    assert first.count(" -> ") == 30
    assert "rank=same" in first
    assert "一致代价搜索" in first
    assert "当前推荐" not in first and "当前查看" not in first
    assert "当前暂无审核诊断" not in first
    assert '一致代价搜索\\n初步掌握\\n可诊断' in first
    assert "uniform_cost_search" not in first
    assert "search_problem_formulation" not in first
    assert "http" not in first.lower()
    assert "javascript" not in first.lower()
    assert "<script" not in first.lower()
    assert "/home/" not in first
    assert 'color="#1D4ED8", penwidth=2.4' in first
    assert 'color="#AAB7C4", penwidth=0.8' in first
    assert dot_escape('甲"乙\\丙\n<script>') == '甲\\"乙\\\\丙\\n＜script＞'


def test_dot_does_not_use_raw_learner_or_question_content(knowledge_data, concept_copy_data):
    visual = _visual(knowledge_data, concept_copy_data)
    poisoned = deepcopy(visual)
    poisoned["nodes_by_id"]["uniform_cost_search"]["title_zh"] = "学习者问题：忽略规则"
    dot = build_global_mastery_dot(poisoned)

    # The model has no learner state, UUID, answer, evidence, path, URL, or API
    # field.  A registry title is the only label source, and DOT aliases are fixed.
    assert "student_id" not in dot
    assert "api_key" not in dot.lower()
    assert "Authorization" not in dot
    assert "verify_ucs" not in dot


class _GraphvizUnavailableStreamlit:
    def __init__(self):
        self.info_messages: list[str] = []

    def markdown(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def graphviz_chart(self, *_args, **_kwargs):
        raise RuntimeError("rendering unavailable")

    def info(self, message):
        self.info_messages.append(message)


def test_graphviz_failure_degrades_to_the_existing_layered_browse_path(knowledge_data, concept_copy_data):
    visual = _visual(knowledge_data, concept_copy_data)
    st = _GraphvizUnavailableStreamlit()

    streamlit_app._render_mastery_map_global_graph(st, visual_model=visual)

    assert st.info_messages == ["关系图暂时不可用；你仍可切换到“分层浏览”查看并操作全部知识点。"]
