from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from introai_tutor.app_services import (
    build_dual_track_diagnostic_workflow,
    load_initial_learner_state,
)
from introai_tutor.diagnostic_state_integration import (
    DiagnosticStateIntegrationService,
)
from introai_tutor.dual_track_diagnostics import (
    DualTrackDiagnosticWorkflowService,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import TemplateSelectionService
from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticService,
)


ROOT = Path(__file__).resolve().parents[1]


class _UnusedFormativeService:
    def start(self, **_kwargs):
        raise AssertionError("multiple-choice UI fixture must not start formative")

    def submit(self, **_kwargs):
        raise AssertionError("multiple-choice UI fixture must not submit formative")

    def skip_current(self, **_kwargs):
        raise AssertionError("multiple-choice UI fixture must not skip formative")


def _fixture_template(template_id="test_multiple_choice_fixture_v1", priority=10):
    return {
        "id": template_id,
        "schema_version": 1,
        "review_status": "human_verified",
        "purpose": "mastery_verification",
        "concept_ids": ["breadth_first_search"],
        "eligible_intents": ["diagnostic_request"],
        "selection_priority": priority,
        "question_type": "multiple_choice",
        "prompt": f"离线多选 UI 测试：{template_id}",
        "choices": [
            {"id": "A", "text": "测试选项甲"},
            {"id": "B", "text": "测试选项乙"},
            {"id": "C", "text": "测试选项丙"},
            {"id": "D", "text": "测试选项丁"},
        ],
        "expected_answer": {"choice_ids": ["A", "C"]},
        "deterministic_scorer": "multiple_choice_v1",
        "misconception_rules": [],
        "teaching_support": {
            "hint": "这是离线测试提示。",
            "explanation": "这是离线测试解析。",
        },
        "benchmark_case_ids": [f"{template_id}_correct", f"{template_id}_wrong"],
    }


def _fixture_workflow(templates):
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    concepts = {point["id"] for point in knowledge["knowledge_points"]}
    template_data = {"schema_version": 1, "templates": deepcopy(templates)}
    return DualTrackDiagnosticWorkflowService(
        formative_service=_UnusedFormativeService(),
        template_selection_service=TemplateSelectionService(
            templates_data=template_data,
            valid_concept_ids=concepts,
        ),
        verification_service=VerificationDiagnosticService(
            templates=deepcopy(templates)
        ),
        state_integration_service=DiagnosticStateIntegrationService(
            knowledge_data=knowledge,
            recommendation_fn=lambda *_args: None,
        ),
    )


def _new_active_app(templates):
    workflow = _fixture_workflow(templates)
    result = workflow.start_quick_verification(
        concept_ids=["breadth_first_search"]
    )
    app_test = AppTest.from_file(ROOT / "app.py", default_timeout=10)
    app_test.session_state["introai_learner_state"] = load_initial_learner_state(
        ROOT
    )
    app_test.session_state[
        "introai_dual_track_diagnostic_workflow"
    ] = workflow
    app_test.session_state["introai_diagnostic_mode"] = "quick"
    app_test.session_state["introai_dual_track_result"] = result
    app_test.session_state["introai_dual_track_session"] = deepcopy(
        result["session"]
    )
    app_test.run()
    assert not app_test.exception
    return app_test


def _new_production_active_app(concept_id, template_id=None):
    workflow = build_dual_track_diagnostic_workflow(root=ROOT)
    result = workflow.start_quick_verification(
        concept_ids=[concept_id],
        intent="definition",
    )
    if template_id is None:
        template_id = result["session"]["verification_session"]["template_ids"][0]
    result = workflow.start_quick_verification(
        concept_ids=[concept_id],
        intent="definition",
        template_ids=[template_id],
    )
    app_test = AppTest.from_file(ROOT / "app.py", default_timeout=10)
    app_test.session_state["introai_learner_state"] = load_initial_learner_state(
        ROOT
    )
    app_test.session_state[
        "introai_dual_track_diagnostic_workflow"
    ] = workflow
    app_test.session_state["introai_diagnostic_mode"] = "quick"
    app_test.session_state["introai_dual_track_result"] = result
    app_test.session_state["introai_dual_track_session"] = deepcopy(
        result["session"]
    )
    app_test.run()
    assert not app_test.exception
    return app_test


def _current_question(app_test):
    workflow = app_test.session_state[
        "introai_dual_track_diagnostic_workflow"
    ]
    return workflow.current_verification_question(
        session=app_test.session_state["introai_dual_track_session"]
    )


def _answer_key(app_test):
    question = _current_question(app_test)
    session = app_test.session_state["introai_dual_track_session"]
    return (
        f"introai_verification_{session['track_id']}_{session['phase']}_"
        f"{question['step_number']}_{question['attempt_number']}_"
        f"{question['template_id']}"
    )


def _submit_key(answer_key):
    return (
        "FormSubmitter:introai_verification_form_"
        f"{answer_key}-提交验证答案"
    )


def _submit_multiple(app_test, selected_ids):
    key = _answer_key(app_test)
    app_test.multiselect(key=key).set_value(selected_ids)
    app_test.button(key=_submit_key(key)).click()
    app_test.run()
    assert not app_test.exception


def _submit_single(app_test, selected_id):
    key = _answer_key(app_test)
    app_test.radio(key=key).set_value(selected_id)
    app_test.button(key=_submit_key(key)).click()
    app_test.run()
    assert not app_test.exception


@pytest.mark.smoke
def test_multiple_choice_ui_renders_text_but_submits_stable_ids_and_completes():
    app_test = _new_active_app([_fixture_template()])
    key = _answer_key(app_test)
    widget = app_test.multiselect(key=key)

    assert widget.label == "选择所有正确答案"
    assert widget.options == ["测试选项甲", "测试选项乙", "测试选项丙", "测试选项丁"]

    _submit_multiple(app_test, ["C", "A"])

    result = app_test.session_state["introai_dual_track_result"]
    history = result["verification"]["session"]["history"]
    assert result["phase"] == "completed"
    assert history[0]["submitted_answer"] == ["C", "A"]
    assert history[0]["passed"] is True


@pytest.mark.smoke
@pytest.mark.parametrize("selected_ids", [["A"], ["A", "B", "C"]])
def test_multiple_choice_ui_fewer_or_extra_choices_score_zero(selected_ids):
    app_test = _new_active_app([_fixture_template()])

    _submit_multiple(app_test, selected_ids)

    result = app_test.session_state["introai_dual_track_result"]
    assert result["phase"] == "verification"
    assert result["verification"]["evaluation"]["score"] == 0.0
    assert result["verification"]["session"]["interaction_state"] == "retry_ready"


@pytest.mark.smoke
def test_multiple_choice_ui_empty_selection_creates_no_attempt():
    app_test = _new_active_app([_fixture_template()])
    key = _answer_key(app_test)
    original = deepcopy(app_test.session_state["introai_dual_track_session"])

    app_test.button(key=_submit_key(key)).click()
    app_test.run()

    assert not app_test.exception
    assert "请至少选择一个答案。" in [item.value for item in app_test.warning]
    assert app_test.session_state["introai_dual_track_session"] == original
    assert (
        app_test.session_state["introai_dual_track_session"][
            "verification_session"
        ]["history"]
        == []
    )


def test_multiple_choice_ui_hint_assisted_correct_keeps_prior_independent_zero():
    app_test = _new_active_app([_fixture_template()])
    _submit_multiple(app_test, ["A"])

    app_test.button(
        key="introai_verification_retry_test_multiple_choice_fixture_v1"
    ).click()
    app_test.run()
    _submit_multiple(app_test, ["A", "C"])

    result = app_test.session_state["introai_dual_track_result"]
    history = result["verification"]["session"]["history"]
    update = result["state_update"]["updates"][0]
    assert [(item["score"], item["assisted"]) for item in history] == [
        (0.0, False),
        (1.0, True),
    ]
    assert update["selected_signal"] == 0.0


def test_multiple_choice_ui_reveal_after_wrong_does_not_add_observation():
    app_test = _new_active_app([_fixture_template()])
    _submit_multiple(app_test, ["A"])

    app_test.button(
        key="introai_verification_reveal_after_wrong_"
        "test_multiple_choice_fixture_v1"
    ).click()
    app_test.run()

    session = app_test.session_state["introai_dual_track_session"]
    assert session["verification_session"]["interaction_state"] == "revealing"
    assert len(session["verification_session"]["history"]) == 1
    assert session["verification_session"]["history"][0]["score"] == 0.0


@pytest.mark.smoke
def test_multiple_choice_ui_next_step_uses_new_empty_widget_state():
    templates = [
        _fixture_template("test_multiple_choice_first_v1", priority=20),
        _fixture_template("test_multiple_choice_second_v1", priority=10),
    ]
    app_test = _new_active_app(templates)
    first_key = _answer_key(app_test)
    _submit_multiple(app_test, ["A", "C"])

    question = _current_question(app_test)
    second_key = _answer_key(app_test)
    assert question["template_id"] == "test_multiple_choice_second_v1"
    assert second_key != first_key
    assert app_test.multiselect(key=second_key).value == []


def test_existing_single_choice_ui_still_submits_choice_id():
    workflow = build_dual_track_diagnostic_workflow(root=ROOT)
    result = workflow.start_quick_verification(
        concept_ids=["uniform_cost_search"],
        intent="definition",
    )
    app_test = AppTest.from_file(ROOT / "app.py", default_timeout=10)
    app_test.session_state["introai_learner_state"] = load_initial_learner_state(
        ROOT
    )
    app_test.session_state[
        "introai_dual_track_diagnostic_workflow"
    ] = workflow
    app_test.session_state["introai_diagnostic_mode"] = "quick"
    app_test.session_state["introai_dual_track_result"] = result
    app_test.session_state["introai_dual_track_session"] = deepcopy(
        result["session"]
    )
    app_test.run()
    key = _answer_key(app_test)
    assert app_test.radio(key=key).options == ["B", "A", "C"]

    app_test.run()
    assert app_test.radio(key=key).options == ["B", "A", "C"]

    app_test.radio(key=key).set_value("A")
    app_test.button(key=_submit_key(key)).click()
    app_test.run()

    assert not app_test.exception
    completed = app_test.session_state["introai_dual_track_result"]
    assert completed["phase"] == "completed"
    assert completed["verification"]["session"]["history"][0][
        "selected_choice_id"
    ] == "A"


def test_rebalanced_ucs_first_displayed_choice_remains_wrong():
    app_test = _new_production_active_app("uniform_cost_search")
    key = _answer_key(app_test)

    assert app_test.radio(key=key).options[0] == "B"
    _submit_single(app_test, "B")

    result = app_test.session_state["introai_dual_track_result"]
    assert result["phase"] == "verification"
    assert result["verification"]["evaluation"]["passed"] is False
    assert result["verification"]["session"]["interaction_state"] == "retry_ready"


@pytest.mark.smoke
def test_production_problem_components_multiple_choice_completes_with_five_items():
    app_test = _new_production_active_app("search_problem_formulation")
    question = _current_question(app_test)
    key = _answer_key(app_test)

    assert question["template_id"] == "verify_search_problem_components_v1"
    assert "五个组成部分" in question["prompt"]
    assert "state_space" not in question["choices"]
    assert "状态空间" not in app_test.multiselect(key=key).options
    assert "状态转移模型" in app_test.multiselect(key=key).options
    assert app_test.multiselect(key=key).options == [
        "初始状态",
        "预先指定必须使用哪一种搜索算法",
        "可执行动作",
        "状态转移模型",
        "预先指定 frontier 必须使用哪一种容器",
        "目标测试",
        "路径代价",
    ]

    _submit_multiple(
        app_test,
        [
            "initial_state",
            "actions",
            "transition_model",
            "goal_test",
            "path_cost",
        ],
    )

    completed = app_test.session_state["introai_dual_track_result"]
    assert completed["phase"] == "completed"
    assert completed["verification"]["session"]["history"][0]["passed"] is True
    assert [item["concept_id"] for item in completed["state_update"]["updates"]] == [
        "search_problem_formulation"
    ]


@pytest.mark.smoke
def test_production_successor_single_choice_submits_move_right():
    app_test = _new_production_active_app("state_space_and_operators")
    question = _current_question(app_test)
    key = _answer_key(app_test)

    assert question["template_id"] == "verify_successor_operator_v1"
    assert "以下四个候选状态中" in question["prompt"]
    assert app_test.radio(key=key).options == [
        "空格、2、1 / 3、4、5 / 6、7、8",
        "1、空格、2 / 3、4、5 / 6、7、8",
        "1、2、3 / 4、5、6 / 7、8、空格",
        "空格、1、2 / 3、4、5 / 6、7、8",
    ]

    _submit_single(app_test, "move_right")

    completed = app_test.session_state["introai_dual_track_result"]
    assert completed["phase"] == "completed"
    history = completed["verification"]["session"]["history"]
    assert history[0]["selected_choice_id"] == "move_right"
    assert history[0]["passed"] is True


@pytest.mark.smoke
@pytest.mark.parametrize(
    (
        "concept_id",
        "template_id",
        "answer",
        "prompt_fragments",
        "choice_text",
        "correct_position",
    ),
    [
        (
            "tree_search_vs_graph_search",
            "verify_graph_search_repeated_state_handling_v1",
            "discard_repeat",
            ("closed 称为 explored", "frontier 保存 search node", "STATE[N]=S"),
            "跳过节点 N，不再次扩展状态 S",
            3,
        ),
        (
            "depth_first_search",
            "verify_dfs_frontier_choice_v1",
            "node_c",
            ("栈底 → 栈顶", "A(depth=1)", "C(depth=2)"),
            "节点 C",
            4,
        ),
        (
            "iterative_deepening_search",
            "verify_iddfs_depth_limit_schedule_v1",
            "restart_limit_2",
            ("0、1、2", "每一轮都从根节点重新运行"),
            "把 depth limit 提高到 2，并从根节点重新运行 depth-limited DFS",
            1,
        ),
    ],
)
def test_p2d_production_single_choice_paths_render_reviewed_text_and_complete(
    concept_id,
    template_id,
    answer,
    prompt_fragments,
    choice_text,
    correct_position,
):
    app_test = _new_production_active_app(concept_id, template_id)
    question = _current_question(app_test)
    key = _answer_key(app_test)

    assert question["template_id"] == template_id
    assert all(fragment in question["prompt"] for fragment in prompt_fragments)
    assert app_test.radio(key=key).options.index(choice_text) + 1 == correct_position

    _submit_single(app_test, answer)

    completed = app_test.session_state["introai_dual_track_result"]
    history = completed["verification"]["session"]["history"]
    assert completed["phase"] == "completed"
    assert history[0]["selected_choice_id"] == answer
    assert history[0]["passed"] is True
    assert [item["concept_id"] for item in completed["state_update"]["updates"]] == [
        concept_id
    ]


@pytest.mark.parametrize(
    ("concept_id", "wrong_answer"),
    [
        ("tree_search_vs_graph_search", "expand_then_record"),
        ("depth_first_search", "node_b"),
        ("iterative_deepening_search", "continue_limit_2"),
    ],
)
def test_p2d_production_wrong_single_choices_enter_retry(
    concept_id, wrong_answer
):
    app_test = _new_production_active_app(concept_id)

    _submit_single(app_test, wrong_answer)

    result = app_test.session_state["introai_dual_track_result"]
    assert result["phase"] == "verification"
    assert result["verification"]["evaluation"]["score"] == 0.0
    assert result["verification"]["session"]["interaction_state"] == "retry_ready"


@pytest.mark.smoke
def test_p2d_repeated_state_hint_retry_preserves_assistance_provenance():
    app_test = _new_production_active_app("tree_search_vs_graph_search")
    _submit_single(app_test, "expand_then_record")

    app_test.button(
        key="introai_verification_retry_"
        "verify_graph_search_repeated_state_handling_v1"
    ).click()
    app_test.run()
    _submit_single(app_test, "discard_repeat")

    completed = app_test.session_state["introai_dual_track_result"]
    history = completed["verification"]["session"]["history"]
    assert [(item["score"], item["assistance_level"]) for item in history] == [
        (0.0, "none"),
        (1.0, "hint"),
    ]
    assert completed["state_update"]["updates"][0]["selected_signal"] == 0.0


def test_p2d_repeated_state_reveal_uses_existing_single_choice_path():
    app_test = _new_production_active_app("tree_search_vs_graph_search")
    _submit_single(app_test, "expand_then_record")

    app_test.button(
        key="introai_verification_reveal_after_wrong_"
        "verify_graph_search_repeated_state_handling_v1"
    ).click()
    app_test.run()

    session = app_test.session_state["introai_dual_track_session"]
    reveal = app_test.session_state[
        "introai_dual_track_diagnostic_workflow"
    ].current_verification_reveal(session=session)
    assert session["verification_session"]["interaction_state"] == "revealing"
    assert reveal["correct_choice_text"] == "跳过节点 N，不再次扩展状态 S"
    assert reveal["assistance_level"] == "reveal"


@pytest.mark.smoke
def test_p2e_g_h_multiple_choice_renders_reviewed_order_and_updates_only_primary_concept():
    app_test = _new_production_active_app("informed_search_and_heuristics")
    question = _current_question(app_test)
    key = _answer_key(app_test)

    assert question["template_id"] == "verify_informed_search_g_h_roles_v1"
    assert app_test.multiselect(key=key).options == [
        "g(n) 表示从起始结点到结点 n 的开销代价值。",
        "h(n) 表示从起始结点到结点 n 已经付出的路径开销。",
        "h(n) 表示从结点 n 到目标结点路径中所估算的最小开销代价值。",
        "g(n) 表示从结点 n 到目标结点的估计剩余代价。",
    ]

    _submit_multiple(app_test, ["g_path_cost", "h_goal_estimate"])

    completed = app_test.session_state["introai_dual_track_result"]
    assert completed["phase"] == "completed"
    assert [item["concept_id"] for item in completed["state_update"]["updates"]] == [
        "informed_search_and_heuristics"
    ]


@pytest.mark.smoke
@pytest.mark.parametrize(
    (
        "concept_id", "template_id", "answer", "correct_position",
        "prompt_fragment", "correct_text",
    ),
    [
        (
            "greedy_best_first_search",
            "verify_greedy_min_h_choice_v1",
            "node_b",
            2,
            "A 的 g=1、h=5",
            "节点 B",
        ),
        (
            "a_star_search",
            "verify_astar_min_f_choice_v1",
            "node_c",
            3,
            "f(n)=g(n)+h(n)",
            "节点 C",
        ),
        (
            "admissibility_and_consistency",
            "verify_admissibility_no_overestimate_v1",
            "equal_and_under",
            4,
            "h*(P)=4",
            "h(P)=4，h(Q)=6",
        ),
    ],
)
def test_p2e_single_choice_production_paths_complete_with_static_positions(
    concept_id, template_id, answer, correct_position, prompt_fragment, correct_text
):
    app_test = _new_production_active_app(concept_id, template_id)
    question = _current_question(app_test)
    key = _answer_key(app_test)

    assert question["template_id"] == template_id
    assert prompt_fragment in question["prompt"]
    assert app_test.radio(key=key).options.index(correct_text) + 1 == correct_position

    _submit_single(app_test, answer)

    completed = app_test.session_state["introai_dual_track_result"]
    assert completed["phase"] == "completed"
    assert [item["concept_id"] for item in completed["state_update"]["updates"]] == [
        concept_id
    ]


@pytest.mark.parametrize(
    ("concept_id", "wrong_answer"),
    [
        ("greedy_best_first_search", "node_d"),
        ("a_star_search", "node_a"),
        ("admissibility_and_consistency", "p_overestimates"),
    ],
)
def test_p2e_single_choice_wrong_answer_enters_existing_retry_path(
    concept_id, wrong_answer
):
    app_test = _new_production_active_app(concept_id)

    _submit_single(app_test, wrong_answer)

    result = app_test.session_state["introai_dual_track_result"]
    assert result["phase"] == "verification"
    assert result["verification"]["evaluation"]["score"] == 0.0
    assert result["verification"]["session"]["interaction_state"] == "retry_ready"


@pytest.mark.smoke
def test_production_frontier_explored_multiple_choice_renders_timeline_and_completes():
    app_test = _new_production_active_app("frontier_and_explored_set")
    question = _current_question(app_test)
    key = _answer_key(app_test)
    rendered_questions = [item.value for item in app_test.subheader]

    assert question["template_id"] == "verify_frontier_explored_membership_v1"
    assert "graph-search 约定" in question["prompt"]
    assert "在第2步完成后" in question["prompt"]
    assert any("graph-search 约定" in value for value in rendered_questions)
    assert "节点 X 位于 frontier" in app_test.multiselect(key=key).options
    assert "状态 Y 位于 explored" in app_test.multiselect(key=key).options

    _submit_multiple(app_test, ["y_explored", "x_frontier"])

    completed = app_test.session_state["introai_dual_track_result"]
    assert completed["phase"] == "completed"
    assert completed["verification"]["session"]["history"][0]["passed"] is True


@pytest.mark.parametrize(
    ("concept_id", "selected_ids"),
    [
        (
            "search_problem_formulation",
            ["initial_state", "actions", "transition_model", "goal_test"],
        ),
        (
            "frontier_and_explored_set",
            ["x_frontier"],
        ),
        (
            "frontier_and_explored_set",
            ["x_frontier", "y_explored", "x_explored"],
        ),
    ],
)
def test_promoted_multiple_choice_production_wrong_answers_enter_retry(
    concept_id, selected_ids
):
    app_test = _new_production_active_app(concept_id)

    _submit_multiple(app_test, selected_ids)

    result = app_test.session_state["introai_dual_track_result"]
    assert result["phase"] == "verification"
    assert result["verification"]["evaluation"]["score"] == 0.0
    assert result["verification"]["session"]["interaction_state"] == "retry_ready"
