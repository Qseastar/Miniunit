from copy import deepcopy
from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

import app as streamlit_app
from introai_tutor.app_services import (
    build_diagnostic_handoff_service,
    build_dual_track_diagnostic_workflow,
    build_question_answer_service,
)
from introai_tutor.course_material_preview import citation_preview_key
from introai_tutor.deepseek_adapter import DeepSeekRequestError
from introai_tutor.pilot_feedback_ui import (
    ANONYMOUS_CODE_KEY,
    DOWNLOAD_FILENAME_KEY,
    FORM_REVISION_KEY,
    PREPARED_PAYLOAD_KEY,
    SERIALIZED_PAYLOAD_KEY,
    pilot_widget_inventory,
)
from introai_tutor.pilot_tasks import load_pilot_tasks, ordered_tasks
from introai_tutor.tutor_service import TutorServiceError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QA_SUBMIT_KEY = "FormSubmitter:introai_qa_form-提交问题"
HANDOFF_START_KEY = "introai_start_qa_handoff_diagnostic"
UNAVAILABLE_MESSAGE = "当前没有与本问题对应的审核验证题，本次仅提供课程回答。"


class _OfflineQAService:
    """Return reviewed, deterministic QA routing without adapters or network."""

    def __init__(self):
        self.calls = []

    def ask(self, question):
        self.calls.append(question)
        if question.startswith("A* frontier"):
            understanding = {
                "in_scope": True,
                "intent": "algorithm_trace",
                "topic_ids": ["a_star_search"],
                "diagnostic_topic_ids": ["a_star_search"],
                "supporting_topic_ids": [],
                "search_terms": ["A*", "frontier", "f(n)"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        elif question.startswith("A*"):
            understanding = {
                "in_scope": True,
                "intent": "property",
                "topic_ids": [
                    "a_star_search",
                    "admissibility_and_consistency",
                ],
                "diagnostic_topic_ids": [
                    "a_star_search",
                    "admissibility_and_consistency",
                ],
                "supporting_topic_ids": [],
                "search_terms": ["A*", "admissibility", "consistency"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        elif question.startswith("BFS"):
            understanding = {
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
                "search_terms": ["BFS", "path cost", "UCS"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        elif question.startswith("graph search"):
            understanding = {
                "in_scope": True,
                "intent": "definition",
                "topic_ids": [
                    "tree_search_vs_graph_search",
                    "frontier_and_explored_set",
                ],
                "diagnostic_topic_ids": ["tree_search_vs_graph_search"],
                "supporting_topic_ids": ["frontier_and_explored_set"],
                "search_terms": ["graph search", "repeated state"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        elif question.startswith("DFS"):
            understanding = {
                "in_scope": True,
                "intent": "algorithm_trace",
                "topic_ids": ["depth_first_search", "frontier_and_explored_set"],
                "diagnostic_topic_ids": ["depth_first_search"],
                "supporting_topic_ids": ["frontier_and_explored_set"],
                "search_terms": ["DFS", "stack", "frontier"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        elif question.startswith("IDDFS"):
            understanding = {
                "in_scope": True,
                "intent": "definition",
                "topic_ids": ["iterative_deepening_search", "depth_first_search"],
                "diagnostic_topic_ids": ["iterative_deepening_search"],
                "supporting_topic_ids": ["depth_first_search"],
                "search_terms": ["IDDFS", "depth limit"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        else:
            understanding = {
                "in_scope": True,
                "intent": "definition",
                "topic_ids": [
                    "uniform_cost_search",
                    "frontier_and_explored_set",
                ],
                "diagnostic_topic_ids": ["uniform_cost_search"],
                "supporting_topic_ids": ["frontier_and_explored_set"],
                "search_terms": ["UCS", "frontier", "path cost"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.95,
            }
        return {
            "question": question,
            "understanding": deepcopy(understanding),
            "retrieval": {
                "candidate_count": 0,
                "selected_count": 0,
                "selected_chunk_ids": [],
                "topic_coverage": {},
                "results": [],
            },
            "response": {
                "status": "answered",
                "answer": "离线课程回答",
                "answer_blocks": [],
                "used_chunk_ids": [],
                "citations": [],
                "limitations": [],
                "confidence": 1.0,
            },
        }


class _CitationQAService(_OfflineQAService):
    def ask(self, question):
        result = super().ask(question)
        result["response"]["answer"] = "课程回答"
        result["response"]["answer_blocks"] = [
            {
                "citations": [
                    {
                        "chunk_id": "synthetic_chunk_a",
                        "source_file": "ai_lec3_informed_search.pdf",
                        "page_start": 16,
                        "page_end": 25,
                        "section_title": "A* 搜索",
                        "source_role": "course_core",
                    },
                    {
                        "chunk_id": "synthetic_chunk_b",
                        "source_file": "ai_lec2_uninformed_search.pdf",
                        "page_start": 26,
                        "page_end": 26,
                        "section_title": "BFS",
                        "source_role": "course_core",
                    },
                ]
            }
        ]
        return result


def _new_app_test(*, qa_service=None):
    app_test = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10)
    app_test.session_state["introai_qa_service"] = qa_service or _OfflineQAService()
    app_test.session_state["introai_diagnostic_handoff_service"] = (
        build_diagnostic_handoff_service(root=PROJECT_ROOT)
    )
    app_test.session_state["introai_dual_track_diagnostic_workflow"] = (
        build_dual_track_diagnostic_workflow(root=PROJECT_ROOT)
    )
    app_test.run()
    assert not app_test.exception
    return app_test


def _new_persistent_exposure_app_test(tmp_path):
    """Use the real P3d composition with an isolated local SQLite database."""
    app_test = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10)
    app_test.session_state["introai_state_db_path"] = tmp_path / "state.sqlite3"
    app_test.session_state["introai_qa_service"] = _OfflineQAService()
    app_test.session_state["introai_diagnostic_handoff_service"] = (
        build_diagnostic_handoff_service(root=PROJECT_ROOT)
    )
    app_test.run()
    assert not app_test.exception
    return app_test


def _submit(app_test, question):
    _qa_text_area(app_test).input(question)
    app_test.button(key=QA_SUBMIT_KEY).click()
    app_test.run()
    assert not app_test.exception


def _qa_text_area(app_test):
    areas = [area for area in app_test.text_area if area.label == "输入课程问题"]
    assert len(areas) == 1
    return areas[0]


def _visible_text(app_test):
    return [
        *(element.value for element in app_test.info),
        *(element.value for element in app_test.caption),
        *(element.value for element in app_test.markdown),
    ]


def _button_keys(app_test):
    return {button.key for button in app_test.button}


def test_citation_preview_buttons_are_isolated_and_unavailable_is_graceful(monkeypatch):
    monkeypatch.delenv("INTROAI_COURSE_MATERIALS_DIR", raising=False)
    app_test = _new_app_test(qa_service=_CitationQAService())
    _submit(app_test, "BFS 是什么？")

    preview_buttons = [button for button in app_test.button if button.label == "查看引用课件"]
    assert len(preview_buttons) == 2
    first_key = f"{citation_preview_key({'chunk_id': 'synthetic_chunk_a'}, 1)}_open"
    app_test.button(key=first_key).click()
    app_test.run()
    assert not app_test.exception
    assert any("当前无法预览这条课件引用" in item.value for item in app_test.info)
    assert any(
        "ai_lec3_informed_search.pdf · 第16页" in item.value
        for item in app_test.caption
    )
    assert any("引用范围：第16–25页" in item.value for item in app_test.caption)
    assert app_test.session_state["introai_citation_preview"] == {
        "answer_revision": 1,
        "index": 1,
        "page": 16,
    }
    assert any(button.label == "← 上一页" and button.disabled for button in app_test.button)
    next_button = next(button for button in app_test.button if button.label == "下一页 →")
    assert next_button.disabled is False
    next_button.click()
    app_test.run()
    assert app_test.session_state["introai_citation_preview"]["page"] == 17
    assert "introai_scroll_request" not in app_test.session_state
    previous_button = next(button for button in app_test.button if button.label == "← 上一页")
    assert previous_button.disabled is False
    previous_button.click()
    app_test.run()
    assert app_test.session_state["introai_citation_preview"]["page"] == 16
    app_test.session_state["introai_citation_preview"] = {
        "answer_revision": 1,
        "index": 1,
        "page": 25,
    }
    app_test.run()
    assert any(button.label == "下一页 →" and button.disabled for button in app_test.button)

    second_key = f"{citation_preview_key({'chunk_id': 'synthetic_chunk_b'}, 0)}_open"
    app_test.button(key=second_key).click()
    app_test.run()
    assert app_test.session_state["introai_citation_preview"] == {
        "answer_revision": 1,
        "index": 0,
        "page": 26,
    }
    markdown_values = [item.value for item in app_test.markdown]
    assert markdown_values.count("#### 引用课件预览") == 1
    assert markdown_values.index("- **BFS** · `ai_lec2_uninformed_search.pdf` · 第 26 页 · 课程核心材料") < markdown_values.index(
        "#### 引用课件预览"
    )
    assert not any(button.label == "← 上一页" for button in app_test.button)
    assert len([button for button in app_test.button if button.label == "查看引用课件"]) == 2

    _submit(app_test, "UCS 是什么？")
    assert "introai_citation_preview" not in app_test.session_state
    assert "introai_citation_preview_scroll_revision" not in app_test.session_state


class _CitationPreviewStateStreamlit:
    def __init__(self):
        self.session_state = {}


def test_citation_preview_events_and_stale_page_state_are_scoped_to_one_answer():
    citation = {
        "source_file": "ai_lec3_informed_search.pdf",
        "source_role": "course_core",
        "page_start": 16,
        "page_end": 25,
    }
    st = _CitationPreviewStateStreamlit()

    streamlit_app._open_citation_preview(
        st, citation=citation, index=0, answer_revision=4
    )
    first_request = dict(st.session_state["introai_scroll_request"])
    assert st.session_state["introai_citation_preview"] == {
        "answer_revision": 4,
        "index": 0,
        "page": 16,
    }
    assert first_request["target"] == "qa_citation_preview"

    streamlit_app._open_citation_preview(
        st, citation=citation, index=0, answer_revision=4
    )
    assert st.session_state["introai_scroll_request"]["event_id"] != first_request["event_id"]

    st.session_state["introai_citation_preview"]["page"] = 26
    assert streamlit_app._citation_preview_state(
        st.session_state, citation=citation, index=0, answer_revision=4
    ) is None
    st.session_state["introai_citation_preview"]["page"] = 16
    assert streamlit_app._citation_preview_state(
        st.session_state, citation=citation, index=0, answer_revision=5
    ) is None

    streamlit_app._clear_citation_preview(st.session_state)
    assert "introai_citation_preview" not in st.session_state
    assert "introai_citation_preview_scroll_revision" not in st.session_state
    assert "introai_scroll_request" not in st.session_state


def test_student_visible_qa_examples_use_ucs_not_ucb():
    app_test = _new_app_test()
    examples = "\n".join(_visible_text(app_test))

    assert "UCS 为什么按累计路径代价选择下一个节点？" in examples
    assert "UCB 如何平衡探索和利用？" not in examples


def _pilot_inventory(app_test):
    tasks = ordered_tasks(
        load_pilot_tasks(PROJECT_ROOT / "data" / "pilot_search_algorithms_tasks.json")
    )
    return pilot_widget_inventory(
        task_ids=[task["task_id"] for task in tasks],
        revision=(
            app_test.session_state[FORM_REVISION_KEY]
            if FORM_REVISION_KEY in app_test.session_state
            else 0
        ),
    )


class _FailureThenSuccessQAService:
    def __init__(self):
        self.calls = []

    def ask(self, question):
        self.calls.append(question)
        if len(self.calls) == 1:
            raise TutorServiceError(
                "synthetic timeout",
                stage="qa_topic_classification",
                correlation_id="testcorr001",
                failure_kind="upstream_timeout",
            )
        return _OfflineQAService().ask(question)


@pytest.mark.smoke
def test_apptest_a_star_property_now_routes_to_reviewed_consistency_template():
    app_test = _new_app_test()

    _submit(app_test, "A* 可采纳性和一致性")
    assert "可用题目：1 题" in _visible_text(app_test)
    assert HANDOFF_START_KEY in _button_keys(app_test)
    assert app_test.session_state["introai_qa_diagnostic_plan"]["template_ids"] == [
        "verify_consistency_edge_check_v1"
    ]

    _submit(app_test, "UCS frontier")

    visible = _visible_text(app_test)
    assert "可用题目：1 题" in visible
    assert "匹配知识点：一致代价搜索" in visible
    assert HANDOFF_START_KEY in _button_keys(app_test)
    assert UNAVAILABLE_MESSAGE not in visible
    assert app_test.session_state["introai_qa_service"].calls == [
        "A* 可采纳性和一致性",
        "UCS frontier",
    ]


def test_apptest_timeout_preserves_question_and_manual_retry_recovers_once():
    service = _FailureThenSuccessQAService()
    app_test = _new_app_test(qa_service=service)

    _submit(app_test, "UCS frontier")

    assert "模型服务暂时不可用。你的问题已保留，学习记录未受影响。" in [
        element.value for element in app_test.error
    ]
    assert _qa_text_area(app_test).value == "UCS frontier"
    assert "introai_retry_qa_question" in _button_keys(app_test)
    assert service.calls == ["UCS frontier"]

    app_test.button(key="introai_retry_qa_question").click()
    app_test.run()

    assert service.calls == ["UCS frontier", "UCS frontier"]
    assert not app_test.error
    assert "introai_qa_retry_state" not in app_test.session_state
    assert app_test.session_state["introai_last_qa_result"]["response"]["status"] == "answered"


def test_apptest_fresh_qa_widget_is_blank_and_session_local_while_reruns_preserve_drafts():
    first = _new_app_test()
    first_area = _qa_text_area(first)
    assert first_area.value == ""
    first_key = first_area.key
    assert first_key.startswith("introai_qa_question_")
    first_area.input("UCS frontier")
    first.run()
    assert _qa_text_area(first).value == "UCS frontier"

    second = _new_app_test()
    second_area = _qa_text_area(second)
    assert second_area.value == ""
    assert second_area.key.startswith("introai_qa_question_")
    assert second_area.key != first_key


def test_apptest_explicit_ucs_handoff_skips_unavailable_model_without_answer():
    class _UnavailableAdapter:
        def __init__(self):
            self.calls = []

        def complete_json(self, **kwargs):
            self.calls.append(kwargs)
            raise DeepSeekRequestError(
                "synthetic timeout", failure_kind="upstream_timeout"
            )

    adapter = _UnavailableAdapter()
    app_test = _new_app_test(
        qa_service=build_question_answer_service(root=PROJECT_ROOT, adapter=adapter)
    )

    _submit(app_test, "请用审核诊断题测试我对一致代价搜索如何选择下一个节点的理解。")

    assert adapter.calls == []
    assert HANDOFF_START_KEY in _button_keys(app_test)
    assert "模型服务暂时不可用" not in _visible_text(app_test)
    result = app_test.session_state["introai_last_qa_result"]
    assert result["response"]["status"] == "diagnostic_available"
    assert result["diagnostic_plan"]["template_ids"] == ["verify_ucs_min_g_choice_v1"]


def test_apptest_ucs_then_a_star_replaces_plan_with_reviewed_consistency_template():
    app_test = _new_app_test()

    _submit(app_test, "UCS frontier")
    assert HANDOFF_START_KEY in _button_keys(app_test)

    _submit(app_test, "A* 可采纳性和一致性")

    assert "可用题目：1 题" in _visible_text(app_test)
    assert HANDOFF_START_KEY in _button_keys(app_test)
    assert app_test.session_state["introai_qa_diagnostic_plan"]["template_ids"] == [
        "verify_consistency_edge_check_v1"
    ]
    assert app_test.session_state["introai_qa_service"].calls == [
        "UCS frontier",
        "A* 可采纳性和一致性",
    ]


@pytest.mark.smoke
def test_apptest_supported_a_star_handoff_is_available_and_replaces_old_plan():
    app_test = _new_app_test()
    _submit(app_test, "UCS frontier")
    assert HANDOFF_START_KEY in _button_keys(app_test)

    _submit(app_test, "A* frontier 根据什么选择节点？")

    visible = _visible_text(app_test)
    assert "可用题目：1 题" in visible
    # The Markdown source escapes the algorithm token; Streamlit renders the
    # student-visible label as the literal “A* 搜索”.
    assert "匹配知识点：A\\* 搜索" in visible
    assert HANDOFF_START_KEY in _button_keys(app_test)
    plan = app_test.session_state["introai_qa_diagnostic_plan"]
    assert plan["template_ids"] == ["verify_astar_min_f_choice_v1"]
    assert plan["planning_source"] == "diagnostic_topic_ids"


@pytest.mark.smoke
def test_apptest_direct_ucs_is_one_question_and_starts_one_of_one():
    app_test = _new_app_test()
    _submit(app_test, "UCS frontier")

    assert "可用题目：1 题" in _visible_text(app_test)
    assert HANDOFF_START_KEY in _button_keys(app_test)
    assert app_test.session_state["introai_qa_service"].calls == ["UCS frontier"]

    app_test.button(key=HANDOFF_START_KEY).click()
    app_test.run()

    assert not app_test.exception
    assert app_test.session_state["introai_diagnostic_origin"] == "qa_handoff"
    session = app_test.session_state["introai_dual_track_session"]
    assert session["verification_session"]["template_ids"] == [
        "verify_ucs_min_g_choice_v1"
    ]
    workflow = app_test.session_state["introai_dual_track_diagnostic_workflow"]
    question = workflow.current_verification_question(session=session)
    assert (question["step_number"], question["total_steps"]) == (1, 1)
    assert app_test.session_state["introai_qa_service"].calls == ["UCS frontier"]


def test_apptest_completed_template_restarts_as_practice_without_mastery_update(tmp_path):
    app_test = _new_persistent_exposure_app_test(tmp_path)
    _submit(app_test, "UCS frontier")
    app_test.button(key=HANDOFF_START_KEY).click()
    app_test.run()
    app_test.radio[0].set_value("A")
    submit_key = next(button.key for button in app_test.button if button.label == "提交验证答案")
    app_test.button(key=submit_key).click()
    app_test.run()
    first_mastery = deepcopy(app_test.session_state["introai_learner_state"]["mastery"])
    assert first_mastery["uniform_cost_search"] == pytest.approx(0.35)

    app_test.button(key="introai_return_to_qa").click()
    app_test.run()
    _submit(app_test, "UCS frontier")
    assert "开始复习练习（1题）" in [button.label for button in app_test.button]
    app_test.button(key=HANDOFF_START_KEY).click()
    app_test.run()
    assert app_test.session_state["introai_dual_track_result"]["practice_only"] is True
    app_test.radio[0].set_value("A")
    submit_key = next(button.key for button in app_test.button if button.label == "提交验证答案")
    app_test.button(key=submit_key).click()
    app_test.run()
    result = app_test.session_state["introai_dual_track_result"]
    assert result["practice_only"] is True
    assert result["state_update"] is None
    assert app_test.session_state["introai_learner_state"]["mastery"] == first_mastery

@pytest.mark.smoke
def test_apptest_bfs_plan_includes_reviewed_bfs_and_property_questions():
    app_test = _new_app_test()
    _submit(app_test, "BFS 步数与路径代价")

    visible = _visible_text(app_test)
    assert "可用题目：2 题" in visible
    assert "匹配知识点：广度优先搜索、完备性、最优性与复杂度" in visible
    plan = app_test.session_state["introai_last_qa_result"]["diagnostic_plan"]
    assert plan["template_ids"] == [
        "verify_bfs_equal_cost_condition_v1",
        "verify_search_algorithm_properties_v1",
    ]
    assert "verify_ucs_min_g_choice_v1" not in plan["template_ids"]


@pytest.mark.smoke
def test_apptest_p2d_qa_plan_replaces_prior_plan_and_starts_bound_dfs_template():
    app_test = _new_app_test()

    _submit(app_test, "graph search 怎样处理重复状态？")
    first_plan = app_test.session_state["introai_last_qa_result"][
        "diagnostic_plan"
    ]
    assert first_plan["template_ids"] == [
        "verify_graph_search_repeated_state_handling_v1",
    ]

    _submit(app_test, "DFS 使用 stack 时下一步扩展哪个节点？")
    second_plan = app_test.session_state["introai_last_qa_result"][
        "diagnostic_plan"
    ]
    assert second_plan["template_ids"] == ["verify_dfs_frontier_choice_v1"]
    assert second_plan["intent"] == "algorithm_trace"
    assert second_plan["planning_topic_ids"] == ["depth_first_search"]
    assert second_plan["supporting_topic_ids"] == ["frontier_and_explored_set"]
    assert second_plan != first_plan
    assert "针对本题的快速诊断" in [
        item.value for item in app_test.subheader
    ]
    assert "可用题目：1 题" in _visible_text(app_test)
    assert HANDOFF_START_KEY in _button_keys(app_test)

    app_test.button(key=HANDOFF_START_KEY).click()
    app_test.run()

    session = app_test.session_state["introai_dual_track_session"]
    assert session["verification_session"]["template_ids"] == [
        "verify_dfs_frontier_choice_v1"
    ]
    assert app_test.session_state["introai_last_qa_result"][
        "diagnostic_plan"
    ] == second_plan
    assert app_test.session_state["introai_qa_service"].calls == [
        "graph search 怎样处理重复状态？",
        "DFS 使用 stack 时下一步扩展哪个节点？",
    ]


@pytest.mark.smoke
def test_apptest_completed_handoff_can_return_without_clearing_learning_records():
    app_test = _new_app_test()
    _submit(app_test, "UCS frontier")
    app_test.button(key=HANDOFF_START_KEY).click()
    app_test.run()

    app_test.radio[0].set_value("A")
    submit_key = next(
        button.key
        for button in app_test.button
        if button.label == "提交验证答案"
    )
    app_test.button(key=submit_key).click()
    app_test.run()
    assert app_test.session_state["introai_dual_track_result"]["phase"] == "completed"
    before_state = deepcopy(app_test.session_state["introai_learner_state"])
    assert before_state["mastery"]
    # P5B currently stores deterministic verification evidence in the
    # completed summary rather than adding a learner_state.learning_evidence
    # entry. The return action must preserve whichever history exists.
    before_evidence = deepcopy(before_state["learning_evidence"])

    app_test.button(key="introai_return_to_qa").click()
    app_test.run()

    assert not app_test.exception
    assert app_test.session_state["introai_learner_state"] == before_state
    assert app_test.session_state["introai_learner_state"]["learning_evidence"] == before_evidence
    assert app_test.session_state["introai_completed_verification_summaries"]
    assert "introai_dual_track_result" not in app_test.session_state
    assert "introai_dual_track_session" not in app_test.session_state
    assert "introai_diagnostic_mode" not in app_test.session_state
    assert "已返回课程问答，学习记录已保留。" in [
        item.value for item in app_test.success
    ]

    _submit(app_test, "UCS frontier")
    assert not app_test.exception


@pytest.mark.smoke
def test_apptest_clear_all_learning_records_requires_confirmation():
    app_test = _new_app_test()
    app_test.session_state["introai_learner_state"]["mastery"] = {
        "uniform_cost_search": 0.35
    }
    before = deepcopy(app_test.session_state["introai_learner_state"])

    app_test.button(key="introai_reset_all").click()
    app_test.run()

    assert app_test.session_state["introai_learner_state"] == before
    assert "introai_confirm_reset_all" in _button_keys(app_test)

    app_test.button(key="introai_confirm_reset_all").click()
    app_test.run()

    assert app_test.session_state["introai_learner_state"]["mastery"] == {}


@pytest.mark.smoke
def test_apptest_mastery_map_is_complete_and_selects_a_chinese_concept_detail():
    app_test = _new_app_test()

    assert [tab.label for tab in app_test.tabs] == ["课程自由问答", "诊断学习", "知识掌握图谱"]
    assert app_test.radio(key="introai_mastery_map_view").value == "分层浏览"
    assert {
        item.label for item in app_test.metric
    } >= {
        "知识点总数", "已追踪", "尚未追踪", "建议复习", "初步掌握", "掌握较稳", "可审核诊断覆盖"
    }
    map_metrics = {
        item.label: int(item.value)
        for item in app_test.metric
        if item.label in {"知识点总数", "已追踪", "尚未追踪", "建议复习", "初步掌握", "掌握较稳", "可审核诊断覆盖"}
    }
    assert map_metrics == {
        "知识点总数": 26,
        "已追踪": 0,
        "尚未追踪": 26,
        "建议复习": 0,
        "初步掌握": 0,
        "掌握较稳": 0,
            "可审核诊断覆盖": 21,
    }
    app_test.radio(key="introai_mastery_map_view").set_value("关系图")
    app_test.run()
    assert any("课程先修关系图" in item for item in _visible_text(app_test))
    app_test.radio(key="introai_mastery_map_view").set_value("分层浏览")
    app_test.run()
    map_node_buttons = [
        button
        for button in app_test.button
        if button.key and button.key.startswith("introai_mastery_map_select_")
    ]
    assert len(map_node_buttons) == 26
    assert any("尚未追踪" in item for item in _visible_text(app_test))
    assert not any("search_problem_formulation" in item for item in _visible_text(app_test))

    app_test.button(
        key="introai_mastery_map_select_iterative_deepening_search"
    ).click()
    app_test.run()

    assert not app_test.exception
    assert app_test.session_state["introai_mastery_map_selected_concept"] == "iterative_deepening_search"
    assert app_test.session_state["introai_mastery_map_action_revision"] == 1
    assert "mastery-map-action-1" in app_test.session_state[
        "introai_scroll_consumed_events"
    ]
    assert "迭代加深深度优先搜索" in [item.value for item in app_test.subheader]
    assert any("反复执行深度受限的深度优先搜索" in item for item in _visible_text(app_test))
    assert any("直接后续知识" in item for item in _visible_text(app_test))
    assert "introai_mastery_map_start_iterative_deepening_search" in _button_keys(app_test)
    assert "introai_mastery_map_return_overview" in _button_keys(app_test)
    assert app_test.button(key="introai_mastery_map_return_overview").label == "↑ 返回知识图谱"

    before_state = deepcopy(app_test.session_state["introai_learner_state"])
    app_test.button(key="introai_mastery_map_return_overview").click()
    app_test.run()
    assert not app_test.exception
    assert app_test.session_state["introai_mastery_map_selected_concept"] == "iterative_deepening_search"
    assert app_test.session_state["introai_mastery_map_action_revision"] == 2
    assert "mastery-map-action-2" in app_test.session_state[
        "introai_scroll_consumed_events"
    ]
    assert app_test.session_state["introai_learner_state"] == before_state

    # Later explicit actions must rebuild the same fixed detail anchor with a
    # fresh event token, even when the concept has not changed.
    app_test.button(key="introai_mastery_map_select_a_star_search").click()
    app_test.run()
    assert app_test.session_state["introai_mastery_map_selected_concept"] == "a_star_search"
    assert app_test.session_state["introai_mastery_map_action_revision"] == 3
    assert "mastery-map-action-3" in app_test.session_state["introai_scroll_consumed_events"]
    assert "A* 搜索" in [item.value for item in app_test.subheader]

    app_test.button(key="introai_mastery_map_return_overview").click()
    app_test.run()
    app_test.button(key="introai_mastery_map_select_a_star_search").click()
    app_test.run()
    assert app_test.session_state["introai_mastery_map_selected_concept"] == "a_star_search"
    assert app_test.session_state["introai_mastery_map_action_revision"] == 5
    assert "mastery-map-action-5" in app_test.session_state["introai_scroll_consumed_events"]

    app_test.button(key="introai_mastery_map_return_overview").click()
    app_test.run()
    app_test.button(key="introai_mastery_map_select_iterative_deepening_search").click()
    app_test.run()
    assert app_test.session_state["introai_mastery_map_selected_concept"] == "iterative_deepening_search"
    assert app_test.session_state["introai_mastery_map_action_revision"] == 7
    assert "mastery-map-action-7" in app_test.session_state["introai_scroll_consumed_events"]
    assert app_test.session_state["introai_learner_state"] == before_state
    assert "introai_dual_track_session" not in app_test.session_state


@pytest.mark.smoke
def test_apptest_mastery_map_qa_prefill_is_non_submitting_and_diagnostic_uses_reviewed_session():
    app_test = _new_app_test()
    before_mastery = deepcopy(app_test.session_state["introai_learner_state"]["mastery"])

    app_test.button(key="introai_mastery_map_ask_search_problem_formulation").click()
    app_test.run()

    assert not app_test.exception
    assert _qa_text_area(app_test).value == "请结合课件讲解搜索问题建模。"
    assert app_test.session_state["introai_qa_service"].calls == []
    assert app_test.session_state["introai_learner_state"]["mastery"] == before_mastery

    app_test.radio(key="introai_mastery_map_view").set_value("分层浏览")
    app_test.run()
    app_test.button(key="introai_mastery_map_select_uniform_cost_search").click()
    app_test.run()
    app_test.button(key="introai_mastery_map_start_uniform_cost_search").click()
    app_test.run()

    assert not app_test.exception
    assert app_test.session_state["introai_dual_track_result"]["phase"] == "verification"
    assert app_test.session_state["introai_dual_track_session"]["verification_session"]["template_ids"] == [
        "verify_ucs_min_g_choice_v1"
    ]
    assert app_test.session_state["introai_learner_state"]["mastery"] == before_mastery

    app_test.radio[0].set_value("A")
    submit_key = next(
        button.key
        for button in app_test.button
        if button.label == "提交验证答案"
    )
    app_test.button(key=submit_key).click()
    app_test.run()
    assert app_test.session_state["introai_dual_track_result"]["phase"] == "completed"

    app_test.button(key="introai_open_mastery_map_after_verification").click()
    app_test.run()
    assert not app_test.exception
    assert app_test.session_state["introai_mastery_map_selected_concept"] == "uniform_cost_search"
    assert app_test.session_state["introai_dual_track_result"]["phase"] == "completed"


def test_apptest_mastery_map_uncovered_concept_never_creates_an_empty_diagnostic():
    app_test = _new_app_test()

    app_test.radio(key="introai_mastery_map_view").set_value("分层浏览")
    app_test.run()
    app_test.button(key="introai_mastery_map_select_llm_search_and_test_time_scaling").click()
    app_test.run()

    assert "introai_mastery_map_start_llm_search_and_test_time_scaling" not in _button_keys(app_test)
    assert any("暂无审核诊断" in item for item in _visible_text(app_test))
    assert "introai_dual_track_result" not in app_test.session_state


def test_apptest_mastery_map_layer_filter_is_transient_and_has_a_safe_empty_state():
    app_test = _new_app_test()

    app_test.radio(key="introai_mastery_map_view").set_value("分层浏览")
    app_test.run()
    app_test.selectbox(key="introai_mastery_map_layer_filter").set_value("当前推荐")
    app_test.run()
    recommendation_buttons = [
        button for button in app_test.button
        if button.key and button.key.startswith("introai_mastery_map_select_")
    ]
    assert len(recommendation_buttons) == 1

    app_test.selectbox(key="introai_mastery_map_layer_filter").set_value("建议复习")
    app_test.run()
    assert not [
        button for button in app_test.button
        if button.key and button.key.startswith("introai_mastery_map_select_")
    ]
    assert any("当前筛选没有符合条件" in item for item in _visible_text(app_test))


def test_apptest_pilot_mode_is_hidden_by_default(monkeypatch):
    monkeypatch.delenv("INTROAI_PILOT_MODE", raising=False)
    app_test = _new_app_test()

    assert [tab.label for tab in app_test.tabs] == ["课程自由问答", "诊断学习", "知识掌握图谱"]
    assert not any("内测任务与反馈" in item for item in _visible_text(app_test))
    assert not any(key and key.startswith("introai_pilot_") for key in _button_keys(app_test))


def test_apptest_pilot_mode_generates_download_only_payload_without_learning_mutation(monkeypatch):
    monkeypatch.setenv("INTROAI_PILOT_MODE", "1")
    app_test = _new_app_test()
    before_state = deepcopy(app_test.session_state["introai_learner_state"])
    before_summaries = deepcopy(
        app_test.session_state["introai_completed_verification_summaries"]
    )

    assert [tab.label for tab in app_test.tabs] == [
        "课程自由问答", "诊断学习", "知识掌握图谱", "内测任务与反馈"
    ]
    assert any("Pilot release：p4d" in item for item in _visible_text(app_test))
    assert any("feedback schema：v1" in item for item in _visible_text(app_test))
    assert any("匿名测试编号与测试重点角色是两个不同概念" in item for item in _visible_text(app_test))
    inventory = _pilot_inventory(app_test)
    pilot_tasks = [
        checkbox.key for checkbox in app_test.checkbox if checkbox.key in inventory["tasks"].values()
    ]
    assert len(pilot_tasks) == 6
    code = app_test.session_state[ANONYMOUS_CODE_KEY]
    assert code.startswith("G-")
    assert "introai_pilot_tester_code" not in app_test.session_state
    app_test.checkbox(key=inventory["tasks"]["course_question_answering"]).set_value(True)
    for rating_id in (
        "qa_clarity", "citation_helpfulness", "diagnostic_relevance",
        "diagnostic_feedback_clarity", "mastery_map_helpfulness",
        "navigation_naturalness", "learning_record_trust", "overall_intent_to_use",
    ):
        app_test.selectbox(key=inventory["ratings"][rating_id]).set_value(3)
    app_test.button(key=f"FormSubmitter:{inventory['form']}-生成反馈下载").click()
    app_test.run()

    payload = app_test.session_state[PREPARED_PAYLOAD_KEY]
    assert payload["tester_code"] == code
    assert payload["completed_task_ids"] == ["course_question_answering"]
    # AppTest does not currently expose ``st.download_button`` as a regular
    # button element; the prepared, validated payload is its sole input.
    assert payload["schema_version"] == 1
    assert json.loads(app_test.session_state[SERIALIZED_PAYLOAD_KEY]) == payload
    assert code in app_test.session_state[DOWNLOAD_FILENAME_KEY]
    assert any(expander.label == "查看将要下载的反馈数据" for expander in app_test.expander)
    assert app_test.session_state["introai_learner_state"] == before_state
    assert app_test.session_state["introai_completed_verification_summaries"] == before_summaries
    assert "introai_dual_track_result" not in app_test.session_state


def test_apptest_pilot_reset_replaces_all_form_state_without_touching_learning_state(monkeypatch):
    monkeypatch.setenv("INTROAI_PILOT_MODE", "yes")
    app_test = _new_app_test()
    before_state = deepcopy(app_test.session_state["introai_learner_state"])
    before_summaries = deepcopy(app_test.session_state["introai_completed_verification_summaries"])
    old_code = app_test.session_state[ANONYMOUS_CODE_KEY]
    old_inventory = _pilot_inventory(app_test)
    for checkbox in app_test.checkbox:
        if checkbox.key in old_inventory["tasks"].values():
            checkbox.set_value(True)
    for selectbox in app_test.selectbox:
        if selectbox.key in old_inventory["ratings"].values():
            selectbox.set_value(3)
    for text_area in app_test.text_area:
        if text_area.key in old_inventory["free_text"].values():
            text_area.input("需要保留到生成前")
    app_test.button(key=f"FormSubmitter:{old_inventory['form']}-生成反馈下载").click()
    app_test.run()

    assert PREPARED_PAYLOAD_KEY in app_test.session_state
    app_test.button(key=old_inventory["reset"]).click()
    app_test.run()

    new_inventory = _pilot_inventory(app_test)
    assert app_test.session_state["introai_learner_state"] == before_state
    assert app_test.session_state["introai_completed_verification_summaries"] == before_summaries
    assert app_test.session_state[ANONYMOUS_CODE_KEY] != old_code
    assert PREPARED_PAYLOAD_KEY not in app_test.session_state
    assert SERIALIZED_PAYLOAD_KEY not in app_test.session_state
    assert DOWNLOAD_FILENAME_KEY not in app_test.session_state
    assert all(app_test.checkbox(key=key).value is False for key in new_inventory["tasks"].values())
    assert all(app_test.selectbox(key=key).value == "请选择" for key in new_inventory["ratings"].values())
    assert all(app_test.text_area(key=key).value == "" for key in new_inventory["free_text"].values())
    assert any("反馈表已重置" in item.value for item in app_test.success)
    app_test.run()
    assert not any("反馈表已重置" in item.value for item in app_test.success)
