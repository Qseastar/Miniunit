"""Data-driven AppTest coverage for every reviewed production template.

The tests use the real Streamlit script and real production templates.  They
only inject the already-supported offline service composition, never a fake
question renderer or network client.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from introai_tutor.app_services import (
    build_dual_track_diagnostic_workflow,
    load_initial_learner_state,
)
from tests.verification_benchmark_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]


def _template_by_id(template_id: str) -> dict:
    templates = json.loads(
        (ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8")
    )["templates"]
    return next(item for item in templates if item["id"] == template_id)


def _new_app(template_id: str, concept_id: str, intent: str) -> AppTest:
    workflow = build_dual_track_diagnostic_workflow(root=ROOT)
    result = workflow.start_quick_verification(
        concept_ids=[concept_id], intent=intent, template_ids=[template_id]
    )
    app = AppTest.from_file(ROOT / "app.py", default_timeout=10)
    app.session_state["introai_learner_state"] = load_initial_learner_state(ROOT)
    app.session_state["introai_dual_track_diagnostic_workflow"] = workflow
    app.session_state["introai_diagnostic_mode"] = "quick"
    app.session_state["introai_dual_track_result"] = result
    app.session_state["introai_dual_track_session"] = deepcopy(result["session"])
    app.run()
    assert not app.exception
    return app


def _question_and_key(app: AppTest) -> tuple[dict, str]:
    workflow = app.session_state["introai_dual_track_diagnostic_workflow"]
    session = app.session_state["introai_dual_track_session"]
    question = workflow.current_verification_question(session=session)
    key = (
        f"introai_verification_{session['track_id']}_{session['phase']}_"
        f"{question['step_number']}_{question['attempt_number']}_{question['template_id']}"
    )
    return question, key


def _submit(app: AppTest, question: dict, key: str, answer):
    submit_key = f"FormSubmitter:introai_verification_form_{key}-提交验证答案"
    choice_text = {item["id"]: item["text"] for item in question["choices"]}
    if question["question_type"] == "single_choice":
        app.radio(key=key).set_value(choice_text[answer])
    else:
        app.multiselect(key=key).set_value([choice_text[item] for item in answer])
    app.button(key=submit_key).click()
    app.run()
    assert not app.exception


PRODUCTION_ENTRIES = build_manifest(root=ROOT)["production"]


@pytest.mark.parametrize("entry", PRODUCTION_ENTRIES, ids=lambda entry: entry["template_id"])
def test_every_production_template_renders_in_real_app_and_correct_id_completes(entry):
    template = _template_by_id(entry["template_id"])
    app = _new_app(
        template["id"], entry["primary_concept"], entry["eligible_intents"][0]
    )
    question, key = _question_and_key(app)
    assert question["template_id"] == template["id"]
    assert question["prompt"] == template["prompt"]
    assert [item["id"] for item in question["choices"]] == [
        item["id"] for item in template["choices"]
    ]
    if question["question_type"] == "single_choice":
        widget = app.radio(key=key)
    else:
        widget = app.multiselect(key=key)
    assert list(widget.options) == [item["text"] for item in template["choices"]]
    _submit(app, question, key, deepcopy(entry["known_correct"]))
    result = app.session_state["introai_dual_track_result"]
    assert result["phase"] == "completed"
    summary = result["verification"]["summary"]
    assert set(summary["concept_observations"]) == set(template["concept_ids"])
    assert entry["primary_concept"] in summary["concept_observations"]
    history = result["verification"]["session"]["history"][0]
    if template["question_type"] == "single_choice":
        assert history["selected_choice_id"] == template["expected_answer"]["choice_id"]
    else:
        assert history["submitted_answer"] == template["expected_answer"]["choice_ids"]


@pytest.mark.parametrize(
    "template_id,concept_id,intent",
    [
        ("verify_bfs_frontier_choice_v1", "breadth_first_search", "diagnostic_request"),
        ("verify_dfs_frontier_choice_v1", "depth_first_search", "algorithm_trace"),
    ],
)
def test_real_ui_rerun_keeps_choice_order_for_two_reviewed_templates(template_id, concept_id, intent):
    app = _new_app(template_id, concept_id, intent)
    first, _ = _question_and_key(app)
    app.run()
    second, _ = _question_and_key(app)
    assert first["template_id"] == second["template_id"]
    assert first["choices"] == second["choices"]


@pytest.mark.parametrize("template_id,concept_id,intent", [
    ("verify_ucs_min_g_choice_v1", "uniform_cost_search", "definition"),
    ("verify_astar_min_f_choice_v1", "a_star_search", "algorithm_trace"),
])
def test_real_ui_wrong_first_displayed_choice_does_not_complete(template_id, concept_id, intent):
    app = _new_app(template_id, concept_id, intent)
    question, key = _question_and_key(app)
    first_choice = question["choices"][0]["id"]
    assert first_choice != _template_by_id(template_id)["expected_answer"]["choice_id"]
    _submit(app, question, key, first_choice)
    result = app.session_state["introai_dual_track_result"]
    assert result["phase"] == "verification"
    assert result["verification"]["evaluation"]["passed"] is False
