import copy
import json
from pathlib import Path

import pytest

import app as streamlit_app
from introai_tutor.app_services import (
    AppServiceError,
    build_diagnostic_handoff_service,
    build_dual_track_diagnostic_workflow,
    build_diagnostic_workflow,
    build_question_answer_service,
    load_app_data,
    load_initial_learner_state,
)
from introai_tutor.ui_formatting import reset_session_state
from introai_tutor.ui_state import (
    QA_DIAGNOSTIC_PLAN_KEY,
    store_qa_result_with_diagnostic_plan,
)
from introai_tutor.diagnostic_semantics import DiagnosticSemanticAdjudicator
from introai_tutor.dual_track_diagnostics import DualTrackDiagnosticError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeAdapter:
    def complete_json(self, **_kwargs):
        return {}


class OfflineQuestionAnswerAdapter:
    """Return valid non-network model-shaped responses for the QA path."""

    def __init__(self):
        self.calls = 0

    def complete_json(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "in_scope": True,
                "intent": "explanation",
                "topic_ids": ["breadth_first_search"],
                "diagnostic_topic_ids": ["breadth_first_search"],
                "supporting_topic_ids": [],
                "search_terms": ["BFS"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.9,
            }
        return {
            "status": "insufficient_evidence",
            "answer_blocks": [],
            "limitations": ["offline test response"],
            "confidence": 0.0,
        }


class IddfsQuestionAnswerAdapter:
    """Offline shape-compatible adapter for the real IDDFS QA composition."""

    def __init__(self):
        self.calls = []

    def complete_json(self, *, system_prompt, user_prompt, max_tokens):
        self.calls.append((system_prompt, user_prompt, max_tokens))
        if len(self.calls) == 1:
            return {
                "in_scope": True,
                "intent": "property",
                "topic_ids": [
                    "iterative_deepening_search",
                    "completeness_optimality_complexity",
                ],
                "diagnostic_topic_ids": [
                    "iterative_deepening_search",
                    "completeness_optimality_complexity",
                ],
                "supporting_topic_ids": [],
                "search_terms": ["IDDFS", "完备", "最优"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        return {
            "status": "insufficient_evidence",
            "answer_blocks": [],
            "limitations": ["offline fixture"],
            "confidence": 0.0,
        }


class AstarDiagnosticRequestAdapter:
    """Offline classifier response for the real A* calculation handoff."""

    def __init__(self):
        self.calls = []

    def complete_json(self, *, system_prompt, user_prompt, max_tokens):
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return {
            "in_scope": True,
            "intent": "diagnostic_request",
            "topic_ids": ["a_star_search"],
            "diagnostic_topic_ids": ["a_star_search"],
            "supporting_topic_ids": [],
            "search_terms": ["A*", "g(n)", "h(n)", "f(n)"],
            "needs_clarification": False,
            "clarifying_question": None,
            "confidence": 0.95,
        }


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}


class _HandoffStreamlit:
    def __init__(self, session_state=None, *, button_result=False):
        self.session_state = session_state or {}
        self.successes = []
        self.warnings = []
        self.errors = []
        self.subheaders = []
        self.infos = []
        self.writes = []
        self.captions = []
        self.markdowns = []
        self.buttons = []
        self.button_result = button_result

    def success(self, message):
        self.successes.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def error(self, message):
        self.errors.append(message)

    def subheader(self, message):
        self.subheaders.append(message)

    def info(self, message):
        self.infos.append(message)

    def write(self, message):
        self.writes.append(message)

    def caption(self, message):
        self.captions.append(message)

    def markdown(self, message, **kwargs):
        self.markdowns.append((message, kwargs))

    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs))
        return self.button_result


class _HandoffWorkflow:
    def __init__(self):
        self.calls = []

    def start_quick_verification(self, *, concept_ids, intent, template_ids):
        self.calls.append((list(concept_ids), intent, list(template_ids)))
        return {
            "phase": "verification",
            "verification": {
                "question": {
                    "step_number": 1,
                    "total_steps": len(template_ids),
                    "template_id": template_ids[0],
                }
            },
            "session": {
                "phase": "verification",
                "track_id": "quick_verification",
                "formative_session": {},
                "verification_session": {"template_ids": list(template_ids)},
            },
        }


def test_streamlit_diagnostic_composition_injects_shared_adapter_as_semantic_adjudicator(
    monkeypatch,
):
    st = _FakeStreamlit()
    adapter = FakeAdapter()
    captured = {}
    workflow = object()

    monkeypatch.setattr(
        streamlit_app,
        "_get_shared_adapter",
        lambda _st, *, required: adapter,
    )

    def build(*, root, semantic_adjudicator):
        captured["root"] = root
        captured["semantic_adjudicator"] = semantic_adjudicator
        return workflow

    monkeypatch.setattr(streamlit_app, "build_diagnostic_workflow", build)

    assert streamlit_app._get_diagnostic_workflow(st) is workflow
    assert isinstance(captured["semantic_adjudicator"], DiagnosticSemanticAdjudicator)
    assert captured["semantic_adjudicator"]._adapter is adapter


def test_qa_handoff_click_creates_one_targeted_session_without_mutating_qa_result(monkeypatch):
    qa_result = {
        "understanding": {
            "topic_ids": ["uniform_cost_search"],
            "intent": "comparison",
        }
    }
    plan = {
        "available": True,
        "topic_ids": ["uniform_cost_search"],
        "intent": "comparison",
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    st = _HandoffStreamlit({"introai_last_qa_result": copy.deepcopy(qa_result)})
    workflow = _HandoffWorkflow()
    monkeypatch.setattr(
        streamlit_app, "_get_dual_track_diagnostic_workflow", lambda _st: workflow
    )

    streamlit_app._start_qa_handoff_diagnostic(st, plan)

    assert workflow.calls == [(
        ["uniform_cost_search"], "comparison", ["verify_ucs_min_g_choice_v1"]
    )]
    assert st.session_state["introai_diagnostic_origin"] == "qa_handoff"
    assert st.session_state["introai_pending_diagnostic_plan"] == plan
    assert st.session_state["introai_dual_track_session"]["verification_session"]["template_ids"] == [
        "verify_ucs_min_g_choice_v1"
    ]
    assert qa_result == {
        "understanding": {
            "topic_ids": ["uniform_cost_search"],
            "intent": "comparison",
        }
    }
    assert st.session_state["introai_last_qa_result"]["understanding"] == qa_result[
        "understanding"
    ]
    assert st.session_state["introai_last_qa_result"]["diagnostic_plan"] == plan
    assert st.successes == ["针对性快速诊断已准备好，请点击上方‘诊断学习’继续。"]

    streamlit_app._start_qa_handoff_diagnostic(st, plan)

    assert len(workflow.calls) == 1
    assert st.warnings == ["当前已有未完成的诊断，请先完成或重新开始。"]


def test_bfs_handoff_card_shows_only_planning_topics_and_two_questions(monkeypatch):
    plan = {
        "available": True,
        "topic_ids": [
            "breadth_first_search",
            "completeness_optimality_complexity",
        ],
        "planning_topic_ids": [
            "breadth_first_search",
            "completeness_optimality_complexity",
        ],
        "all_topic_ids": [
            "breadth_first_search",
            "completeness_optimality_complexity",
            "uniform_cost_search",
        ],
        "supporting_topic_ids": ["uniform_cost_search"],
        "planning_source": "diagnostic_topic_ids",
        "intent": "comparison",
        "template_ids": [
            "verify_bfs_equal_cost_condition_v1",
            "verify_bfs_frontier_choice_v1",
        ],
    }
    st = _HandoffStreamlit({"introai_qa_diagnostic_plan": plan})
    titles_by_id = {
        "breadth_first_search": "广度优先搜索",
        "completeness_optimality_complexity": "完备性、最优性与复杂度",
        "uniform_cost_search": "一致代价搜索",
    }
    monkeypatch.setattr(
        streamlit_app,
        "_topic_titles",
        lambda _st, topic_ids: [titles_by_id[topic_id] for topic_id in topic_ids],
    )

    streamlit_app._render_qa_diagnostic_plan(st)

    rendered = "\n".join(st.writes + st.captions)
    assert "已找到 2 道与本题相关的人工审核诊断题，完成后可更新学习记录。" in st.infos
    assert "可用题目：2 题" in rendered
    assert "广度优先搜索" in rendered
    assert "完备性、最优性与复杂度" in rendered
    assert "一致代价搜索" not in rendered
    assert st.buttons[0][0] == "开始审核诊断（2题）"
    assert all(
        internal not in rendered
        for internal in (
            "breadth_first_search",
            "diagnostic_topic_ids",
            "supporting_topic_ids",
            "planning_source",
        )
    )


def test_ucs_handoff_card_shows_one_question_and_ucs_title(monkeypatch):
    plan = {
        "available": True,
        "topic_ids": ["uniform_cost_search"],
        "planning_topic_ids": ["uniform_cost_search"],
        "all_topic_ids": ["uniform_cost_search"],
        "supporting_topic_ids": [],
        "planning_source": "diagnostic_topic_ids",
        "intent": "comparison",
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    state = {}
    bound_result = store_qa_result_with_diagnostic_plan(
        state,
        qa_result={"question": "UCS 如何选择下一个节点？"},
        diagnostic_plan=plan,
    )
    state[QA_DIAGNOSTIC_PLAN_KEY] = {
        "available": False,
        "message": "stale unavailable plan",
        "template_ids": [],
    }
    st = _HandoffStreamlit(state)
    monkeypatch.setattr(
        streamlit_app,
        "_topic_titles",
        lambda _st, _topic_ids: ["一致代价搜索"],
    )

    current_plan = streamlit_app.resolve_qa_diagnostic_plan(
        qa_result=bound_result,
        cached_plan=st.session_state[QA_DIAGNOSTIC_PLAN_KEY],
    )
    streamlit_app._render_qa_diagnostic_plan(st, plan=current_plan)

    rendered = "\n".join(st.writes + st.captions)
    assert "已找到 1 道与本题相关的人工审核诊断题，完成后可更新学习记录。" in st.infos
    assert "可用题目：1 题" in rendered
    assert "匹配知识点：一致代价搜索" in rendered
    assert st.buttons[0][0] == "开始审核诊断（1题）"
    assert "stale unavailable plan" not in rendered


def test_available_single_ucs_plan_starts_exactly_one_targeted_question(monkeypatch):
    plan = {
        "available": True,
        "topic_ids": ["uniform_cost_search"],
        "planning_topic_ids": ["uniform_cost_search"],
        "all_topic_ids": ["uniform_cost_search", "frontier_and_explored_set"],
        "supporting_topic_ids": ["frontier_and_explored_set"],
        "planning_source": "diagnostic_topic_ids",
        "intent": "explanation",
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    state = {}
    store_qa_result_with_diagnostic_plan(
        state,
        qa_result={"question": "UCS", "understanding": {}},
        diagnostic_plan=plan,
    )
    st = _HandoffStreamlit(state, button_result=True)
    workflow = _HandoffWorkflow()
    monkeypatch.setattr(
        streamlit_app, "_get_dual_track_diagnostic_workflow", lambda _st: workflow
    )
    monkeypatch.setattr(
        streamlit_app,
        "_topic_titles",
        lambda _st, _topic_ids: ["一致代价搜索"],
    )

    streamlit_app._render_qa_diagnostic_plan(
        st,
        plan=st.session_state["introai_last_qa_result"]["diagnostic_plan"],
    )

    assert workflow.calls == [(
        ["uniform_cost_search"],
        "explanation",
        ["verify_ucs_min_g_choice_v1"],
    )]
    assert st.session_state["introai_diagnostic_origin"] == "qa_handoff"
    assert st.session_state["introai_dual_track_session"]["verification_session"][
        "template_ids"
    ] == ["verify_ucs_min_g_choice_v1"]
    assert st.session_state["introai_scroll_request"] == {
        "target": "diagnostic_question",
        "event_id": "diagnostic-verification-1-verify_ucs_min_g_choice_v1",
    }
    assert st.session_state["introai_last_qa_result"]["diagnostic_plan"] == plan


def test_new_qa_plan_is_visible_but_cannot_replace_an_active_diagnostic(monkeypatch):
    plan = {
        "available": True,
        "planning_topic_ids": ["uniform_cost_search"],
        "intent": "explanation",
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    state = {
        "introai_dual_track_result": {"phase": "verification"},
        "introai_dual_track_session": {
            "verification_session": {
                "template_ids": ["verify_bfs_frontier_choice_v1"]
            }
        },
    }
    store_qa_result_with_diagnostic_plan(
        state, qa_result={"question": "UCS"}, diagnostic_plan=plan
    )
    original_session = copy.deepcopy(state["introai_dual_track_session"])
    st = _HandoffStreamlit(state, button_result=True)
    workflow = _HandoffWorkflow()
    monkeypatch.setattr(
        streamlit_app, "_get_dual_track_diagnostic_workflow", lambda _st: workflow
    )
    monkeypatch.setattr(
        streamlit_app,
        "_topic_titles",
        lambda _st, _topic_ids: ["一致代价搜索"],
    )

    streamlit_app._render_qa_diagnostic_plan(
        st, plan=state["introai_last_qa_result"]["diagnostic_plan"]
    )

    assert "可用题目：1 题" in st.captions
    assert st.warnings == ["当前已有未完成的诊断，请先完成或重新开始。"]
    assert st.buttons == []
    assert workflow.calls == []
    assert state["introai_dual_track_session"] == original_session


def test_unavailable_a_star_handoff_card_has_no_start_button():
    st = _HandoffStreamlit(
        {
            "introai_qa_diagnostic_plan": {
                "available": False,
                "message": "当前没有与本问题对应的审核验证题，本次仅提供课程回答。",
                "planning_topic_ids": [
                    "a_star_search",
                    "admissibility_and_consistency",
                ],
                "template_ids": [],
            }
        }
    )

    streamlit_app._render_qa_diagnostic_plan(st)

    assert st.infos == ["当前没有与本问题对应的审核验证题，本次仅提供课程回答。"]
    assert st.buttons == []


def test_streamlit_diagnostic_composition_remains_offline_when_adapter_is_unavailable(
    monkeypatch,
):
    st = _FakeStreamlit()
    captured = {}

    monkeypatch.setattr(
        streamlit_app,
        "_get_shared_adapter",
        lambda _st, *, required: None,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_diagnostic_workflow",
        lambda *, root, semantic_adjudicator: captured.setdefault(
            "semantic_adjudicator", semantic_adjudicator
        ) or object(),
    )

    streamlit_app._get_diagnostic_workflow(st)

    assert captured["semantic_adjudicator"] is None


def test_streamlit_reuses_one_adapter_for_qa_and_semantic_diagnostic_paths(monkeypatch):
    st = _FakeStreamlit()
    adapter = FakeAdapter()
    captured = {}

    monkeypatch.setattr(
        streamlit_app,
        "_get_shared_adapter",
        lambda _st, *, required: adapter,
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_diagnostic_workflow",
        lambda *, root, semantic_adjudicator: captured.setdefault(
            "semantic_adapter", semantic_adjudicator._adapter
        ) or object(),
    )
    monkeypatch.setattr(
        streamlit_app,
        "build_question_answer_service",
        lambda *, root, adapter: captured.setdefault("qa_adapter", adapter) or object(),
    )

    streamlit_app._get_diagnostic_workflow(st)
    streamlit_app._get_qa_service(st)

    assert captured["semantic_adapter"] is adapter
    assert captured["qa_adapter"] is adapter


def test_load_app_data_uses_real_course_and_diagnostic_inputs():
    data = load_app_data(PROJECT_ROOT)

    assert set(data) == {
        "knowledge_data",
        "course_data",
        "questions_data",
        "tracks_data",
    }
    assert len(data["knowledge_data"]["knowledge_points"]) == 26
    assert data["course_data"]["chunks"]
    assert len(data["questions_data"]["diagnostic_questions"]) == 27
    assert data["tracks_data"]["tracks"][0]["id"] == "bfs_equal_cost_ucs"


def test_load_app_data_returns_independent_objects():
    first = load_app_data(PROJECT_ROOT)
    first["knowledge_data"]["knowledge_points"].clear()
    first["course_data"]["chunks"].clear()
    second = load_app_data(PROJECT_ROOT)

    assert len(second["knowledge_data"]["knowledge_points"]) == 26
    assert second["course_data"]["chunks"]


def test_build_diagnostic_workflow_is_offline_and_does_not_need_api_key():
    workflow = build_diagnostic_workflow(root=PROJECT_ROOT)
    result = workflow.start()

    assert result["diagnostic"]["status"] == "in_progress"
    assert result["state_update"] is None
    assert result["diagnostic"]["session"]["variant_round"] == 0


def test_build_dual_track_diagnostic_workflow_starts_formative_offline():
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    result = workflow.start()

    assert result["phase"] == "formative"
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None


def test_build_diagnostic_handoff_service_reuses_reviewed_template_bank_offline():
    service = build_diagnostic_handoff_service(root=PROJECT_ROOT)

    plan = service.plan(
        topic_ids=["uniform_cost_search"], intent="comparison"
    )

    assert plan["template_ids"] == ["verify_ucs_min_g_choice_v1"]
    assert plan["evidence_eligible"] is False


def test_targeted_bfs_handoff_preserves_plan_order_and_updates_only_related_concepts():
    planner = build_diagnostic_handoff_service(root=PROJECT_ROOT)
    plan = planner.plan(
        topic_ids=["breadth_first_search", "completeness_optimality_complexity"],
        intent="comparison",
    )
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    original = copy.deepcopy(learner_state)

    result = workflow.start_quick_verification(
        concept_ids=plan["topic_ids"],
        intent=plan["intent"],
        template_ids=plan["template_ids"],
    )

    assert result["session"]["verification_session"]["template_ids"] == plan["template_ids"]
    assert workflow.current_verification_question(session=result["session"])["total_steps"] == 2
    for answer, template_id in (
        ("equal_cost", "verify_bfs_equal_cost_condition_v1"),
        ("iddfs_equal_cost_optimal", "verify_search_algorithm_properties_v1"),
    ):
        result = workflow.submit_verification(
            session=result["session"],
            answer=answer,
            submitted_template_id=template_id,
            learner_state=learner_state,
        )

    assert learner_state == original
    assert result["phase"] == "completed"
    assert result["verification"]["summary"]["total_steps"] == 2
    assert {item["concept_id"] for item in result["state_update"]["updates"]} == {
        "breadth_first_search", "completeness_optimality_complexity"
    }
    assert "uniform_cost_search" not in result["state_update"]["learner_state"]["mastery"]


def test_targeted_ucs_handoff_is_one_question_and_updates_only_ucs_once_completed():
    planner = build_diagnostic_handoff_service(root=PROJECT_ROOT)
    plan = planner.plan(topic_ids=["uniform_cost_search"], intent="comparison")
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)

    result = workflow.start_quick_verification(
        concept_ids=plan["topic_ids"], intent=plan["intent"], template_ids=plan["template_ids"]
    )
    question = workflow.current_verification_question(session=result["session"])
    assert question["template_id"] == "verify_ucs_min_g_choice_v1"
    assert question["step_number"] == 1
    assert question["total_steps"] == 1
    result = workflow.submit_verification(
        session=result["session"], answer="A",
        submitted_template_id=question["template_id"], learner_state=learner_state,
    )

    assert result["phase"] == "completed"
    assert result["verification"]["summary"]["passed_steps"] == 1
    assert [item["concept_id"] for item in result["state_update"]["updates"]] == [
        "uniform_cost_search"
    ]


@pytest.mark.parametrize(
    "template_ids",
    [
        ["verify_bfs_frontier_choice_v1", "verify_bfs_frontier_choice_v1"],
        ["verify_ucs_min_g_choice_v1"],
        ["unreviewed_or_unknown_template"],
    ],
)
def test_targeted_start_rejects_ui_supplied_templates_outside_the_reviewed_plan(template_ids):
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    with pytest.raises(DualTrackDiagnosticError, match="template_ids"):
        workflow.start_quick_verification(
            concept_ids=["breadth_first_search"],
            intent="comparison",
            template_ids=template_ids,
        )


def test_formative_can_be_continued_through_all_steps_without_state_update():
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    result = workflow.start()

    for _ in range(3):
        result = workflow.continue_formative(session=result["session"])

    assert result["phase"] == "verification_ready"
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None


def test_quick_verification_keeps_template_evidence_aligned_and_updates_only_after_step_three():
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    original_state = copy.deepcopy(learner_state)
    result = workflow.start_quick_verification(concept_ids=[
        "breadth_first_search",
        "completeness_optimality_complexity",
        "uniform_cost_search",
    ], template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])
    expected = [
        ("verify_bfs_frontier_choice_v1", "A"),
        ("verify_bfs_equal_cost_condition_v1", "equal_cost"),
        ("verify_ucs_min_g_choice_v1", "A"),
    ]
    for index, (template_id, answer) in enumerate(expected):
        question = workflow.current_verification_question(session=result["session"])
        assert question["template_id"] == template_id
        result = workflow.submit_verification(
            session=result["session"],
            answer=answer,
            submitted_template_id=question["template_id"],
            learner_state=learner_state,
        )
        if index < 2:
            assert result["state_update"] is None

    assert learner_state == original_state
    records = result["verification"]["summary"]["observation_records"]
    assert [item["template_id"] for item in records] == [item[0] for item in expected]
    assert records[-1]["concept_ids"] == ["uniform_cost_search"]
    assert set(result["state_update"]["learner_state"]["mastery"]) == {
        "breadth_first_search", "completeness_optimality_complexity", "uniform_cost_search"
    }


def test_all_revealed_quick_verification_completes_without_mastery_observations():
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    original_state = copy.deepcopy(learner_state)
    result = workflow.start_quick_verification(concept_ids=[
        "breadth_first_search",
        "completeness_optimality_complexity",
        "uniform_cost_search",
    ], template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])

    for index in range(3):
        question = workflow.current_verification_question(session=result["session"])
        result = workflow.request_verification_reveal(
            session=result["session"], template_id=question["template_id"]
        )
        assert result["session"]["verification_session"]["interaction_state"] == "revealing"
        result = workflow.acknowledge_verification_reveal(
            session=result["session"], template_id=question["template_id"],
            learner_state=learner_state,
        )
        if index < 2:
            assert result["state_update"] is None

    assert result["phase"] == "completed"
    assert result["verification"]["summary"]["concept_observations"] == {}
    assert result["state_update"]["updates"] == []
    assert result["state_update"]["learner_state"] == original_state


def test_mixed_evidence_last_step_direct_reveal_completes_and_preserves_ucs_mastery():
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    learner_state["mastery"]["uniform_cost_search"] = 0.6
    original_state = copy.deepcopy(learner_state)

    class CountingIntegration:
        def __init__(self, delegate):
            self.delegate = delegate
            self.calls = 0

        def apply(self, *, learner_state, diagnostic_summary):
            self.calls += 1
            return self.delegate.apply(
                learner_state=learner_state, diagnostic_summary=diagnostic_summary
            )

    integration = CountingIntegration(workflow._state_integration_service)
    workflow._state_integration_service = integration
    result = workflow.start_quick_verification(concept_ids=[
        "breadth_first_search",
        "completeness_optimality_complexity",
        "uniform_cost_search",
    ], template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])
    for answer, template_id in (
        ("A", "verify_bfs_frontier_choice_v1"),
        ("equal_cost", "verify_bfs_equal_cost_condition_v1"),
    ):
        result = workflow.submit_verification(
            session=result["session"],
            answer=answer,
            submitted_template_id=template_id,
            learner_state=learner_state,
        )

    question = workflow.current_verification_question(session=result["session"])
    revealed = workflow.request_verification_reveal(
        session=result["session"], template_id=question["template_id"]
    )
    result = workflow.acknowledge_verification_reveal(
        session=revealed["session"],
        template_id=question["template_id"],
        learner_state=learner_state,
    )

    assert result["phase"] == "completed"
    assert integration.calls == 1
    summary = result["verification"]["summary"]
    assert summary["passed_steps"] == 2
    assert summary["concept_observations"] == {
        "breadth_first_search": [1.0, 1.0],
        "completeness_optimality_complexity": [1.0],
    }
    assert summary["unobserved_concept_ids"] == ["uniform_cost_search"]
    updates = {item["concept_id"]: item for item in result["state_update"]["updates"]}
    assert updates["breadth_first_search"]["selected_signal"] == 1.0
    assert updates["completeness_optimality_complexity"]["selected_signal"] == 1.0
    assert "uniform_cost_search" not in updates
    assert result["state_update"]["skipped_updates"] == [{
        "concept_id": "uniform_cost_search",
        "old_mastery": 0.6,
        "selected_signal": None,
        "update_applied": False,
        "selection_reason": "no_independent_observation",
        "new_mastery": 0.6,
    }]
    assert result["state_update"]["learner_state"]["mastery"]["uniform_cost_search"] == 0.6
    assert learner_state == original_state
    assert result["state_update"]["recommendation"] is not None


def test_last_step_wrong_hint_wrong_reveal_acknowledges_to_completed():
    workflow = build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    result = workflow.start_quick_verification(concept_ids=[
        "breadth_first_search",
        "completeness_optimality_complexity",
        "uniform_cost_search",
    ], template_ids=[
        "verify_bfs_frontier_choice_v1",
        "verify_bfs_equal_cost_condition_v1",
        "verify_ucs_min_g_choice_v1",
    ])
    result = workflow.submit_verification(
        session=result["session"], answer="A",
        submitted_template_id="verify_bfs_frontier_choice_v1", learner_state=learner_state,
    )
    result = workflow.submit_verification(
        session=result["session"], answer="equal_cost",
        submitted_template_id="verify_bfs_equal_cost_condition_v1", learner_state=learner_state,
    )
    result = workflow.submit_verification(
        session=result["session"], answer="C",
        submitted_template_id="verify_ucs_min_g_choice_v1", learner_state=learner_state,
    )
    result = workflow.choose_verification_hint_retry(
        session=result["session"], template_id="verify_ucs_min_g_choice_v1"
    )
    result = workflow.submit_verification(
        session=result["session"], answer="B",
        submitted_template_id="verify_ucs_min_g_choice_v1", learner_state=learner_state,
    )
    assert result["session"]["verification_session"]["interaction_state"] == "revealing"
    result = workflow.acknowledge_verification_reveal(
        session=result["session"], template_id="verify_ucs_min_g_choice_v1",
        learner_state=learner_state,
    )

    assert result["phase"] == "completed"
    observations = result["verification"]["summary"]["observation_records"]
    assert [(item["score"], item["assisted"]) for item in observations[-2:]] == [
        (0.0, False), (0.0, True)
    ]
    assert result["state_update"]["updates"][-1]["selected_signal"] == 0.0


def test_diagnostic_student_ui_uses_natural_attempt_copy_and_hides_internal_update_trace():
    app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    assert "冲浪尝试" not in app_source
    assert '"知识点": row["title_zh"]' in app_source
    assert '"更新后掌握度": row["new_mastery"]' in app_source
    assert '"作答帮助级别": [' in app_source
    assert '"信号选择原因": selection_reasons.get(' in app_source
    assert "workflow.submit_formative(session=deepcopy(session), answer=answer)" in app_source
    assert "workflow.submit_verification(" in app_source
    assert "快速诊断（推荐）" in app_source
    assert "深度理解检查（可选）" in app_source
    assert "workflow.start_quick_verification(" in app_source
    assert "workflow.continue_formative(" in app_source
    assert "开放式反馈可能无法覆盖所有正确表达，不直接影响你的学习记录。" in app_source
    assert "introai_formative_answer_{question_key}_{question['step_number']}_" in app_source
    assert "workflow.current_verification_question(session=deepcopy(session))" in app_source
    assert "introai_verification_{session.get('track_id')}_{session.get('phase')}_" in app_source
    assert "submitted_template_id=question[\"template_id\"]" in app_source
    assert "index=None" in app_source
    assert 'st.warning("请先选择一个答案。")' in app_source
    assert "本题最多作答 2 次。" in app_source
    assert 'st.button("查看答案"' in app_source
    assert "没有思路，查看答案" not in app_source
    assert "查看答案与解析" in app_source
    assert 'retry_column.button("再试一次"' in app_source
    assert "根据提示再试一次" not in app_source
    assert "我理解了，进入下一题" in app_source
    assert "我理解了，完成诊断" in app_source
    assert "verification_unavailable" in app_source
    assert "本次结果仅作为学习反馈。" in app_source


def test_qa_handoff_ui_uses_explicit_plan_and_never_auto_starts_verification():
    app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    assert "针对本题的快速诊断" in app_source
    assert "开始审核诊断（{len(template_ids)}题）" in app_source
    assert "前往审核诊断" not in app_source
    assert "_render_ordinary_qa_diagnostic_cta" not in app_source
    assert "qa-handoff-cta" not in app_source
    assert "针对性快速诊断已准备好，请点击上方‘诊断学习’继续。" in app_source
    assert "题目来自人工审核模板，不由模型临时生成。" in app_source
    assert "当前已有未完成的诊断，请先完成或重新开始。" in app_source
    assert "build_diagnostic_handoff_service(root=ROOT)" in app_source
    assert "template_ids=plan_copy[\"template_ids\"]" in app_source
    assert "QA_DIAGNOSTIC_PLAN_KEY" in app_source
    assert "PENDING_DIAGNOSTIC_PLAN_KEY" in app_source
    assert "_render_qa_diagnostic_plan(st, plan=current_plan)" in app_source
    assert '"diagnostic_plan": current_plan' in app_source
    assert 'target="diagnostic_handoff"' in app_source


def test_ordinary_qa_region_has_one_dynamic_start_button_and_no_scroll_request():
    plan = {
        "available": True,
        "topic_ids": ["uniform_cost_search"],
        "planning_topic_ids": ["uniform_cost_search"],
        "template_ids": ["verify_ucs_min_g_choice_v1"],
    }
    st = _HandoffStreamlit({}, button_result=False)
    streamlit_app._render_qa_diagnostic_plan(st, plan=plan)

    assert st.infos == [
        "已找到 1 道与本题相关的人工审核诊断题，完成后可更新学习记录。"
    ]
    assert st.buttons == [
        ("开始审核诊断（1题）", {
            "key": "introai_start_qa_handoff_diagnostic",
            "type": "primary",
        })
    ]
    assert "前往审核诊断" not in st.infos
    assert "introai_scroll_request" not in st.session_state


def test_student_concept_label_uses_chinese_title_and_unknown_fallback(monkeypatch):
    st = _FakeStreamlit()
    monkeypatch.setattr(
        streamlit_app,
        "_get_app_data",
        lambda _st: {
            "knowledge_data": {
                "knowledge_points": [
                    {"id": "search_problem_formulation", "title_zh": "搜索问题建模"}
                ]
            }
        },
    )

    assert streamlit_app._concept_label(st, "search_problem_formulation") == "搜索问题建模"
    assert streamlit_app._concept_label(st, "unknown_concept") == "未知知识点"


def test_developer_update_rows_use_stable_chinese_labels_before_raw_trace():
    rows = streamlit_app._developer_update_rows(
        [
            {
                "title_zh": "一致代价搜索",
                "old_mastery": 0.2,
                "observation_scores": [0.0, 1.0],
                "observation_assistance": [False, True],
                "observation_assistance_levels": ["none", "clarification"],
                "selected_signal": 0.0,
                "selection_reason": "last_unassisted_observation",
                "new_mastery": 0.13,
            }
        ]
    )

    assert rows == [
        {
            "知识点": "一致代价搜索",
            "旧掌握度": 0.2,
            "原始作答分数": [0.0, 1.0],
            "作答帮助级别": ["无帮助", "澄清问题后作答"],
            "最终采用的独立信号": 0.0,
            "信号选择原因": "最后一次未受教学帮助影响的作答",
            "更新后掌握度": 0.13,
        }
    ]


def test_build_question_answer_service_accepts_injected_adapter():
    service = build_question_answer_service(root=PROJECT_ROOT, adapter=FakeAdapter())

    assert callable(getattr(service, "ask"))


def test_real_qa_composition_accepts_iddfs_structured_output_and_handoff():
    adapter = IddfsQuestionAnswerAdapter()
    service = build_question_answer_service(root=PROJECT_ROOT, adapter=adapter)
    question = "请解释迭代加深深度优先搜索（IDDFS）是否完备，以及它在什么条件下是最优的。"

    result = service.ask(question)

    assert result["understanding"]["topic_ids"] == [
        "iterative_deepening_search",
        "completeness_optimality_complexity",
    ]
    assert result["response"]["status"] == "insufficient_evidence"
    assert len(adapter.calls) == 2

    handoff = build_diagnostic_handoff_service(root=PROJECT_ROOT)
    plan = handoff.plan_from_qa_result(qa_result=result)
    assert plan["available"] is True
    assert "verify_search_algorithm_properties_v1" in plan["template_ids"]


def test_real_qa_composition_uses_safe_a_star_diagnostic_transition_and_handoff():
    adapter = AstarDiagnosticRequestAdapter()
    service = build_question_answer_service(root=PROJECT_ROOT, adapter=adapter)
    question = "在 A* 搜索中，如果一个节点的 g(N)=4，h(N)=3，那么 f(N) 等于多少？请用一道诊断题测试我。"

    result = service.ask(question)

    assert result["response"]["status"] == "diagnostic_available"
    assert "7" not in result["response"]["answer"]
    assert "答案" not in result["response"]["answer"]
    assert result["diagnostic_plan"]["available"] is True
    assert result["diagnostic_plan"]["template_ids"] == ["verify_astar_f_value_v1"]
    # The strong explicit reviewed-diagnostic request is resolved before
    # question understanding, retrieval, or answer generation.
    assert adapter.calls == []


@pytest.mark.parametrize("missing_name", ["knowledge_points.json", "course_chunks.json", "diagnostic_tracks.json"])
def test_missing_data_file_becomes_app_service_error(tmp_path, missing_name):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for source_name in (
        "knowledge_points.json",
        "course_chunks.json",
        "diagnostic_questions.json",
        "diagnostic_tracks.json",
    ):
        source = PROJECT_ROOT / "data" / source_name
        if source_name != missing_name:
            (data_dir / source_name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(AppServiceError, match="加载失败"):
        load_app_data(tmp_path)


def test_invalid_diagnostic_schema_becomes_app_service_error(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for source_name in (
        "knowledge_points.json",
        "course_chunks.json",
        "diagnostic_questions.json",
        "diagnostic_tracks.json",
    ):
        source = PROJECT_ROOT / "data" / source_name
        (data_dir / source_name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    broken = json.loads((data_dir / "diagnostic_tracks.json").read_text(encoding="utf-8"))
    broken["tracks"][0]["steps"][0]["question_id"] = "missing_question"
    (data_dir / "diagnostic_tracks.json").write_text(
        json.dumps(broken), encoding="utf-8"
    )

    with pytest.raises(AppServiceError, match="加载失败"):
        load_app_data(tmp_path)


def test_initial_learner_state_is_fresh_and_not_data_file_object():
    first = load_initial_learner_state(PROJECT_ROOT)
    original = copy.deepcopy(first)
    first["mastery"]["breadth_first_search"] = 0.0
    first["misconceptions"].append("temporary")
    second = load_initial_learner_state(PROJECT_ROOT)

    assert original["mastery"] == {}
    assert original["misconceptions"] == []
    assert original["learning_evidence"] == []
    assert second["mastery"] == {}
    assert second["misconceptions"] == []
    assert second["learning_evidence"] == []
    assert first is not second
    assert first["mastery"] is not second["mastery"]


def test_empty_initial_state_open_diagnostic_remains_formative_only():
    workflow = build_diagnostic_workflow(root=PROJECT_ROOT)
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    result = workflow.start()
    session = result["diagnostic"]["session"]

    for answer in (
        "BFS expands nodes level by level and finds the fewest steps.",
        "BFS finds the fewest steps; it is optimal only with equal step costs and otherwise may not find the lowest path cost.",
        "UCS handles different costs and chooses the lowest path cost using cumulative path cost g(n).",
    ):
        result = workflow.submit(
            session=session,
            answer=answer,
            learner_state=learner_state,
        )
        session = result["diagnostic"]["session"]

    assert result["diagnostic"]["status"] == "completed"
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None
    assert learner_state["mastery"] == {}
    assert learner_state["mastery"] == {}


def test_free_question_answering_does_not_change_learner_state():
    learner_state = load_initial_learner_state(PROJECT_ROOT)
    before = copy.deepcopy(learner_state)
    service = build_question_answer_service(
        root=PROJECT_ROOT, adapter=OfflineQuestionAnswerAdapter()
    )

    service.ask("BFS 是什么？")

    assert learner_state == before


def test_reset_then_reload_restores_empty_initial_state():
    session_state = {
        "introai_learner_state": {
            "student_id": "streamlit_user",
            "mastery": {"breadth_first_search": 0.7},
            "misconceptions": [],
            "learning_evidence": [],
        }
    }
    reset_session_state(session_state)

    assert "introai_learner_state" not in session_state
    assert load_initial_learner_state(PROJECT_ROOT)["mastery"] == {}


def test_invalid_root_is_clear_app_service_error(tmp_path):
    with pytest.raises(AppServiceError, match="项目目录"):
        load_app_data(tmp_path / "missing")
