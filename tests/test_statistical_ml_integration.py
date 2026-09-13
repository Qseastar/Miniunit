"""Integration tests for the Statistical ML module as a registered Mini Unit.

These tests exercise the real ``statistical_ml`` module package (not synthetic
fixtures) through the shared module registry, mastery-map, and diagnostic
workflow boundaries. They are offline and deterministic: they never call the
DeepSeek adapter, never read the local lecture PDF, and never touch a learner
SQLite database.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from introai_tutor.app_services import (
    build_dual_track_diagnostic_workflow,
    load_initial_learner_state,
)
from introai_tutor.course_modules import (
    load_course_module_data,
    load_course_module_registry,
    resolve_course_module,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.mastery_map import build_mastery_map_model, load_mastery_map_layout
from introai_tutor.mastery_map_visualization import (
    build_visual_mastery_map_model,
    load_concept_copy_zh,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_ID = "statistical_ml"
LEC8_SOURCE_FILE = "ai_lec8_statistical_learning.pdf"


def _module_data():
    return load_course_module_data(ROOT, MODULE_ID)


def _concept_ids(data):
    return {point["id"] for point in data["knowledge_data"]["knowledge_points"]}


# ---------------------------------------------------------------------------
# 1. Module isolation: statistical_ml diagnostics never select Search templates.
# ---------------------------------------------------------------------------


def test_statistical_ml_diagnostic_templates_are_isolated_from_search():
    ml = _module_data()
    search = load_course_module_data(ROOT, "search_algorithms")

    ml_template_ids = {t["id"] for t in ml["templates_data"]["templates"]}
    search_template_ids = {t["id"] for t in search["templates_data"]["templates"]}
    ml_concepts = _concept_ids(ml)

    assert ml_template_ids, "statistical_ml must register reviewed templates."
    assert search_template_ids, "search_algorithms must still register templates."
    assert ml_template_ids.isdisjoint(search_template_ids)

    for template in ml["templates_data"]["templates"]:
        assert set(template["concept_ids"]) <= ml_concepts
        assert template["review_status"] == "human_verified"


def test_statistical_ml_verification_session_only_uses_own_templates():
    workflow = build_dual_track_diagnostic_workflow(root=ROOT, module_id=MODULE_ID)
    result = workflow.start_quick_verification(
        concept_ids=["statistical_ml__supervised_learning"], intent="definition"
    )
    assert result["phase"] == "verification"
    question = workflow.current_verification_question(session=result["session"])
    assert question["template_id"] == "verify_statistical_ml_supervised_learning_sc_v1"
    # The question is a statistical_ml template, not a Search one.
    assert question["template_id"] not in {
        "verify_bfs_frontier_choice_v1",
        "verify_ucs_min_g_choice_v1",
    }


# ---------------------------------------------------------------------------
# 2. QA scope: statistical_ml QA is bounded to its own course chunks.
# ---------------------------------------------------------------------------


def test_statistical_ml_qa_scope_is_bounded_to_own_chunks():
    data = _module_data()
    chunks = data["course_data"]["chunks"]
    assert chunks, "statistical_ml must register course chunks."
    concept_ids = _concept_ids(data)

    for chunk in chunks:
        assert chunk["source_file"] == LEC8_SOURCE_FILE
        assert set(chunk["topic_ids"]) <= concept_ids

    source_files = {chunk["source_file"] for chunk in chunks}
    assert source_files == {LEC8_SOURCE_FILE}
    # No Search-Algorithms PDF ever appears in this module's chunk package.
    assert all("search" not in chunk["id"] for chunk in chunks)


# ---------------------------------------------------------------------------
# 3. Knowledge graph: 17 nodes across the correct 7 stages.
# ---------------------------------------------------------------------------


def test_statistical_ml_visual_mastery_map_has_17_nodes_and_7_stages():
    data = _module_data()
    registry = load_course_module_registry(ROOT)
    module = resolve_course_module(registry, MODULE_ID)
    stage_names = module["mastery_map_stage_names"]

    knowledge_data = load_knowledge_points(
        ROOT / "data" / "statistical_ml_knowledge.json"
    )
    concept_copy_data = load_concept_copy_zh(
        ROOT / "data" / "statistical_ml_concept_copy_zh.json"
    )
    layout_data = load_mastery_map_layout(
        ROOT / "data" / "statistical_ml_mastery_map_layout.json"
    )
    templates_data = json.loads(
        (ROOT / "data" / "statistical_ml_templates.json").read_text(encoding="utf-8")
    )

    map_model = build_mastery_map_model(
        knowledge_data=knowledge_data,
        layout_data=layout_data,
        templates_data=templates_data,
        learner_state={"mastery": {}, "learning_evidence": []},
        recommendation=None,
    )
    visual = build_visual_mastery_map_model(
        map_model=map_model,
        concept_copy_data=concept_copy_data,
        knowledge_data=knowledge_data,
        selected_concept_id="statistical_ml__supervised_learning",
        stage_names=stage_names,
    )

    assert len(visual["nodes_by_id"]) == 17
    assert {layer["layer"] for layer in visual["layers"]} == set(stage_names)
    assert len(visual["layers"]) == 7
    assert [layer["stage_name"] for layer in visual["layers"]] == [
        stage_names[index] for index in sorted(stage_names)
    ]


# ---------------------------------------------------------------------------
# 4. Mastery flow: completing one reviewed question updates learner state.
# ---------------------------------------------------------------------------


def test_statistical_ml_completed_verification_updates_mastery():
    workflow = build_dual_track_diagnostic_workflow(root=ROOT, module_id=MODULE_ID)
    learner_state = load_initial_learner_state(ROOT)
    assert "statistical_ml__supervised_learning" not in learner_state["mastery"]

    started = workflow.start_quick_verification(
        concept_ids=["statistical_ml__supervised_learning"], intent="definition"
    )
    question = workflow.current_verification_question(session=started["session"])

    completed = workflow.submit_verification(
        session=started["session"],
        answer="labeled",
        submitted_template_id=question["template_id"],
        learner_state=learner_state,
    )

    assert completed["phase"] == "completed"
    assert completed["evidence_eligible"] is True
    updates = completed["state_update"]["updates"]
    assert [item["concept_id"] for item in updates] == [
        "statistical_ml__supervised_learning"
    ]
    assert (
        completed["state_update"]["learner_state"]["mastery"][
            "statistical_ml__supervised_learning"
        ]
        > 0.0
    )
