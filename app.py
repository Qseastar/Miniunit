"""Streamlit entry point for the selected IntroAI Tutor course module."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from html import escape
import logging
import re
import time
import uuid
import json
from typing import Any

from introai_tutor.app_services import (
    AppServiceError,
    build_diagnostic_handoff_service,
    build_dual_track_diagnostic_workflow,
    build_diagnostic_workflow,
    build_question_answer_service,
    build_learner_state_persistence_service,
    build_reviewed_template_exposure_policy,
    load_module_app_package,
    load_registered_module_options,
    load_initial_learner_state,
)
from introai_tutor.deepseek_adapter import (
    DeepSeekConfigurationError,
    DeepSeekRequestError,
    DeepSeekResponseError,
)
from introai_tutor.diagnostic_state_integration import DiagnosticStateIntegrationError
from introai_tutor.diagnostic_feedback import DiagnosticFeedbackError
from introai_tutor.diagnostic_semantics import (
    DiagnosticSemanticAdjudicationError,
    DiagnosticSemanticAdjudicator,
)
from introai_tutor.diagnostic_tutoring import DiagnosticTutorError
from introai_tutor.diagnostic_workflow import DiagnosticWorkflowError
from introai_tutor.diagnostic_handoff import DiagnosticHandoffError
from introai_tutor.dual_track_diagnostics import DualTrackDiagnosticError
from introai_tutor.template_selection import DiagnosticTemplateError
from introai_tutor.template_selection import load_diagnostic_templates
from introai_tutor.verification_diagnostics import VerificationDiagnosticError
from introai_tutor.grounded_answering import GroundedAnswerError
from introai_tutor.course_material_preview import (
    citation_preview_key,
    preview_citation,
    preview_unavailable_message,
)
from introai_tutor.question_understanding import QuestionUnderstandingError
from introai_tutor.tutor_service import TutorServiceError
from introai_tutor.learner_profile import resolve_learner_id, start_new_profile
from introai_tutor.learner_state_repository import LearnerStatePersistenceError
from introai_tutor.recommend import recommend_next_concept
from introai_tutor.ui_formatting import (
    format_qa_result,
    format_pages,
    format_concept_label,
    choice_text_by_id,
    misconception_label,
    reset_session_state,
    source_role_label,
    status_label,
    tracked_mastery_count,
    update_rows,
    escape_algorithm_markdown_tokens,
)
from introai_tutor.ui_scroll import (
    SCROLL_REQUEST_KEY,
    consume_scroll_request,
    request_scroll,
    scroll_anchor_markup,
    scroll_component_key,
    scroll_script_markup,
)
from introai_tutor.mastery_map import (
    MasteryMapError,
    build_concept_detail,
    build_mastery_map_model,
    concept_question_prefill,
    default_selected_concept_id,
    load_mastery_map_layout,
)
from introai_tutor.mastery_map_visualization import (
    LAYER_FILTERS,
    build_visual_mastery_map_model,
    filter_layered_nodes,
    load_concept_copy_zh,
)
from introai_tutor.pilot_feedback import (
    FEEDBACK_SCHEMA_VERSION,
    FREE_TEXT_FIELDS,
    RATING_FIELDS,
    PilotFeedbackError,
    build_feedback_payload,
    feedback_filename,
    payload_json,
)
from introai_tutor.pilot_focus_roles import PILOT_EXECUTION_RELEASE
from introai_tutor.pilot_mode import is_pilot_mode_enabled
from introai_tutor.pilot_tasks import PilotTaskError, load_pilot_tasks, ordered_tasks
from introai_tutor.pilot_feedback_ui import (
    DOWNLOAD_FILENAME_KEY,
    PREPARED_PAYLOAD_KEY,
    RESET_REQUEST_KEY,
    SERIALIZED_PAYLOAD_KEY,
    consume_reset_flash,
    current_form_revision,
    ensure_anonymous_tester_code,
    pilot_widget_inventory,
    reset_pilot_feedback_form,
)
from introai_tutor.pilot_access import (
    ACCESS_ERROR_KEY,
    access_input_key,
    compare_access_code,
    configured_access_code,
    grant_access,
    is_access_granted,
    logout_access,
    policy_from_environment,
    public_access_error,
    public_configuration_error,
    request_input_clear,
)
from introai_tutor.ui_state import (
    build_diagnostic_flash,
    clear_diagnostic_state,
    consume_diagnostic_flash,
    diagnostic_variant_round,
    diagnostic_attempt_status,
    diagnostic_question_widget_key,
    validate_current_diagnostic_question,
    DIAGNOSTIC_UNRESOLVED_MESSAGE,
    elapsed_seconds,
    advance_diagnostic_variant_round,
    DIAGNOSTIC_ORIGIN_KEY,
    HANDOFF_SOURCE_TOPICS_KEY,
    PENDING_DIAGNOSTIC_PLAN_KEY,
    QA_DIAGNOSTIC_PLAN_KEY,
    resolve_qa_diagnostic_plan,
    store_qa_result_with_diagnostic_plan,
    has_active_diagnostic,
    qa_question_widget_key,
    set_qa_question_value,
)


ROOT = Path(__file__).resolve().parent
_LOGGER = logging.getLogger(__name__)
_SECRET_LOG_PATTERN = re.compile(r"(?i)(bearer\s+|api[_-]?key\s*[=:]\s*)[^\s,;]+")
_MASTERY_MAP_ACTION_REVISION_KEY = "introai_mastery_map_action_revision"
_QA_RETRY_STATE_KEY = "introai_qa_retry_state"
_CITATION_PREVIEW_STATE_KEY = "introai_citation_preview"
_CITATION_PREVIEW_SCROLL_REVISION_KEY = "introai_citation_preview_scroll_revision"
_SELECTED_MODULE_KEY = "introai_selected_module_id"
_MODULE_SCOPED_SERVICE_KEYS = (
    "introai_app_data",
    "introai_qa_service",
    "introai_diagnostic_handoff_service",
    "introai_diagnostic_workflow",
    "introai_dual_track_diagnostic_workflow",
    "introai_mastery_map_static_inputs",
)
_RETRYABLE_QA_FAILURE_KINDS = frozenset(
    {
        "upstream_timeout",
        "upstream_connection",
        "upstream_rate_limited",
        "upstream_server_error",
        "invalid_model_response",
    }
)
_ACCESS_LOGOUT_REQUEST_KEY = "introai_pilot_access_logout_requested"
_PUBLIC_ERRORS = (
    AppServiceError,
    DeepSeekConfigurationError,
    DeepSeekRequestError,
    DeepSeekResponseError,
    QuestionUnderstandingError,
    GroundedAnswerError,
    TutorServiceError,
    DiagnosticTutorError,
    DiagnosticStateIntegrationError,
    DiagnosticFeedbackError,
    DiagnosticSemanticAdjudicationError,
    DiagnosticWorkflowError,
    DiagnosticHandoffError,
    DualTrackDiagnosticError,
    DiagnosticTemplateError,
    VerificationDiagnosticError,
    LearnerStatePersistenceError,
    MasteryMapError,
)


def main() -> None:
    """Render the three-tab MVP; Streamlit is imported only when executed."""
    try:
        import streamlit as st
    except ImportError as error:  # pragma: no cover - exercised by the CLI
        raise SystemExit(
            "Streamlit is not installed. Install requirements.txt first."
        ) from error

    st.set_page_config(
        page_title="IntroAI Tutor",
        page_icon="🔎",
        layout="wide",
    )
    _consume_pilot_logout_request(st)
    if not _ensure_pilot_access(st):
        return
    _ensure_learner_state(st)
    _flush_pending_persistence(st)
    _render_sidebar(st)
    try:
        module = _get_app_data(st)["module"]
        st.title("IntroAI Tutor — " + module["display_name_zh"])
        st.caption("课程材料约束的 " + module["display_name_en"] + " 学习助手")
    except (AppServiceError, KeyError, TypeError):
        st.title("IntroAI Tutor")
        st.error("当前课程模块暂时不可用，请稍后重试。")
        return
    _apply_pending_mastery_map_qa_prefill(st)
    pilot_enabled = is_pilot_mode_enabled()
    labels = ["课程自由问答", "诊断学习", "知识掌握图谱"]
    if pilot_enabled:
        labels.append("内测任务与反馈")
    tabs = st.tabs(labels)
    qa_tab, diagnostic_tab, mastery_map_tab = tabs[:3]
    with qa_tab:
        _render_question_answering(st)
    with diagnostic_tab:
        _render_diagnostic(st)
    with mastery_map_tab:
        _render_mastery_map(st)
    if pilot_enabled:
        with tabs[3]:
            _render_internal_pilot(st)
    _render_pending_scroll(st)


def _ensure_pilot_access(st: Any) -> bool:
    """Enforce the optional pilot gate before learner/app initialization."""
    # Ordinary development mode must not be affected by pilot-only host or
    # access-code configuration left in a developer's environment.
    if not is_pilot_mode_enabled():
        return True
    try:
        policy = policy_from_environment()
    except (ValueError, TypeError):
        st.title("IntroAI Tutor — 内测访问")
        st.error(public_configuration_error())
        return False
    if not policy.pilot_enabled:
        return True
    if not policy.access_required:
        st.warning("当前为仅本机的负责人开发模式，未启用内测访问码；不要对外暴露此服务。")
        return True
    if not policy.access_code_valid:
        st.title("IntroAI Tutor — 内测访问")
        st.error(public_configuration_error())
        st.caption("这是短期、低规模的负责人托管内测访问，不是账号系统。")
        return False
    if is_access_granted(st.session_state):
        return True
    _render_pilot_access_gate(st)
    return False


def _render_pilot_access_gate(st: Any) -> None:
    st.title("IntroAI Tutor — 内测访问")
    st.caption("请输入负责人单独发送的本次内测访问码。此访问码不是账号密码，也不会写入 URL 或学习记录。")
    st.caption("访问通过后，当前浏览器会获得独立的本地学习档案。请不要分享自己的 learner URL。")
    input_key = access_input_key(st.session_state)
    error_message = st.session_state.pop(ACCESS_ERROR_KEY, None)
    if isinstance(error_message, str) and error_message:
        st.error(error_message)
    with st.form("introai_pilot_access_form"):
        submitted_code = st.text_input("内测访问码", type="password", key=input_key)
        submitted = st.form_submit_button("进入内测")
    if not submitted:
        return
    request_input_clear(st.session_state, input_key)
    if compare_access_code(submitted_code, configured_access_code()):
        grant_access(st.session_state)
    else:
        st.session_state[ACCESS_ERROR_KEY] = public_access_error()
    st.rerun()


def _consume_pilot_logout_request(st: Any) -> None:
    if st.session_state.pop(_ACCESS_LOGOUT_REQUEST_KEY, False) is not True:
        return
    logout_access(st.session_state)
    # Clear the in-memory application snapshot, but leave the query parameter
    # and SQLite profile untouched so a later login can resume it.
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith("introai_"):
            # Keep the current Streamlit widget identity available for the
            # immediate relock rerun, but erase its value.  Dropping a live
            # widget key before Streamlit collects its state can raise a
            # widget-state error; an empty value retains no submitted code.
            if key.startswith("introai_pilot_access_code_"):
                st.session_state[key] = ""
                continue
            st.session_state.pop(key, None)


def _request_pilot_logout(st: Any) -> None:
    st.session_state[_ACCESS_LOGOUT_REQUEST_KEY] = True
    st.rerun()


def _render_internal_pilot(st: Any) -> None:
    """Render download-only pilot tasks without touching learning state."""
    try:
        tasks_data = _get_pilot_tasks(st)
        tasks = ordered_tasks(tasks_data)
        task_ids = tuple(task["task_id"] for task in tasks)
        if st.session_state.pop(RESET_REQUEST_KEY, False) is True:
            reset_pilot_feedback_form(st.session_state)
        code = ensure_anonymous_tester_code(st.session_state)
        inventory = pilot_widget_inventory(
            task_ids=task_ids,
            revision=current_form_revision(st.session_state),
        )
    except (OSError, ValueError, PilotTaskError) as error:
        _LOGGER.warning("pilot_ui_unavailable category=%s", type(error).__name__)
        st.warning("内测反馈暂时不可用，不影响课程问答、诊断或学习记录。")
        return
    reset_flash = consume_reset_flash(st.session_state)
    st.subheader("内测任务与反馈")
    st.info("本页仅用于生成你自行下载的匿名反馈文件，不会写入学习档案。")
    st.caption(f"Pilot release：{PILOT_EXECUTION_RELEASE} · feedback schema：v{FEEDBACK_SCHEMA_VERSION}（兼容 P4a）")
    st.caption("匿名测试编号与测试重点角色是两个不同概念；角色用于分工，编号仅用于区分反馈文件。")
    st.caption("系统会自动生成匿名测试编号；无需填写姓名、学号或联系方式。")
    st.caption("请不要在开放反馈中填写个人信息、API Key、案件信息或其他敏感内容。")
    if reset_flash:
        st.success(reset_flash)
    for task in tasks:
        st.markdown(f"**任务 {task['order']}：{task['title_zh']}**")
        st.write(task["instructions_zh"])
        st.caption("观察点：" + task["observations_zh"])
        if task["estimated_minutes"] is not None:
            st.caption(f"预计用时：约 {task['estimated_minutes']} 分钟（可选）")
        st.checkbox("已完成", key=inventory["tasks"][task["task_id"]])

    st.subheader("结构化反馈")
    st.caption("量表端点：1 = 很差 / 完全不同意；5 = 很好 / 完全同意。")
    st.write(f"匿名测试编号：`{code}`")
    st.caption("该编号仅用于区分反馈文件，不关联你的学习档案或身份。")
    with st.form(inventory["form"]):
        ratings: dict[str, Any] = {}
        for rating_id, label in RATING_FIELDS.items():
            ratings[rating_id] = st.selectbox(
                label,
                options=["请选择", 1, 2, 3, 4, 5],
                key=inventory["ratings"][rating_id],
            )
        free_text: dict[str, str] = {}
        for field, label in FREE_TEXT_FIELDS.items():
            free_text[field] = st.text_area(
                label,
                key=inventory["free_text"][field],
                max_chars=2000,
                height=80,
            )
        prepared = st.form_submit_button("生成反馈下载")
    if prepared:
        completed = [
            task["task_id"]
            for task in tasks
            if st.session_state.get(inventory["tasks"][task["task_id"]]) is True
        ]
        try:
            payload = build_feedback_payload(
                tasks_data=tasks_data,
                tester_code=code,
                completed_task_ids=completed,
                ratings=ratings,
                free_text_feedback=free_text,
            )
            encoded = payload_json(payload, valid_task_ids=set(task_ids))
        except PilotFeedbackError as error:
            st.session_state.pop(PREPARED_PAYLOAD_KEY, None)
            st.session_state.pop(SERIALIZED_PAYLOAD_KEY, None)
            st.session_state.pop(DOWNLOAD_FILENAME_KEY, None)
            st.error(str(error))
        else:
            st.session_state[PREPARED_PAYLOAD_KEY] = payload
            st.session_state[SERIALIZED_PAYLOAD_KEY] = encoded
            st.session_state[DOWNLOAD_FILENAME_KEY] = feedback_filename(payload)
            st.success(f"反馈已生成，匿名测试编号为 {code}。")
    payload = st.session_state.get(PREPARED_PAYLOAD_KEY)
    if isinstance(payload, dict):
        try:
            encoded = st.session_state.get(SERIALIZED_PAYLOAD_KEY)
            filename = st.session_state.get(DOWNLOAD_FILENAME_KEY)
            if not isinstance(encoded, bytes) or not isinstance(filename, str):
                raise PilotFeedbackError("反馈文件已失效，请重新生成。")
            if encoded != payload_json(payload, valid_task_ids=set(task_ids)):
                raise PilotFeedbackError("反馈文件已失效，请重新生成。")
            st.caption("文件只包含任务勾选、评分和主动填写的反馈；不包含课程问题、答案或学习档案。")
            st.download_button(
                "下载本次内测反馈",
                data=encoded,
                file_name=filename,
                mime="application/json",
                key=inventory["download"],
            )
            with st.expander("查看将要下载的反馈数据", expanded=False):
                st.json(payload)
        except PilotFeedbackError:
            st.session_state.pop(PREPARED_PAYLOAD_KEY, None)
            st.session_state.pop(SERIALIZED_PAYLOAD_KEY, None)
            st.session_state.pop(DOWNLOAD_FILENAME_KEY, None)
            st.warning("反馈文件已失效，请重新生成。")
    if st.button("重置内测反馈表", key=inventory["reset"]):
        st.session_state[RESET_REQUEST_KEY] = True
        st.rerun()


def _get_pilot_tasks(st: Any) -> dict[str, Any]:
    if "introai_pilot_tasks" not in st.session_state:
        st.session_state["introai_pilot_tasks"] = load_pilot_tasks(
            ROOT / "data" / "pilot_search_algorithms_tasks.json"
        )
    return st.session_state["introai_pilot_tasks"]


def _ensure_learner_state(st: Any) -> None:
    if "introai_learner_state" in st.session_state:
        return
    try:
        learner_id, _ = resolve_learner_id(st.query_params)
        service = _get_learner_state_persistence_service(st)
        restored = service.restore(
            learner_id=learner_id,
            empty_state=load_initial_learner_state(ROOT),
        )
        st.session_state["introai_learner_id"] = learner_id
        st.session_state["introai_learner_state"] = restored["learner_state"]
        st.session_state["introai_completed_verification_summaries"] = restored[
            "completed_summaries"
        ]
        if restored["warnings"]:
            st.session_state["introai_persistence_warning"] = (
                "部分学习记录无法恢复；其余合法记录已恢复。"
            )
        try:
            st.session_state["introai_last_recommendation"] = recommend_next_concept(
                _get_app_data(st)["knowledge_data"], restored["learner_state"]
            )
        except ValueError:
            st.session_state.pop("introai_last_recommendation", None)
    except (AppServiceError, LearnerStatePersistenceError) as error:
        # Session-only use remains safe when the local database is unavailable.
        _log_persistence_failure(error, "restore")
        st.session_state["introai_learner_state"] = load_initial_learner_state(ROOT)
        st.session_state["introai_persistence_warning"] = "当前仅在本次会话中保存，持久化暂不可用。"
        st.session_state["introai_learner_error"] = str(error)


def _render_sidebar(st: Any) -> None:
    with st.sidebar:
        _render_module_selector(st)
        pilot_policy = policy_from_environment() if is_pilot_mode_enabled() else None
        if pilot_policy is not None and pilot_policy.access_required and is_access_granted(st.session_state):
            st.caption("内测访问已通过（仅当前浏览器会话）")
            if st.button("退出内测访问", key="introai_pilot_access_logout"):
                _request_pilot_logout(st)
        st.subheader("当前学习状态")
        learner_state = st.session_state.get("introai_learner_state")
        if isinstance(learner_state, dict):
            st.metric("已跟踪知识点", tracked_mastery_count(learner_state))
            learner_id = st.session_state.get("introai_learner_id")
            if isinstance(learner_id, str):
                st.caption(f"本地学习档案：已启用（{learner_id[:8]}）")
            recommendation = st.session_state.get("introai_last_recommendation")
            if isinstance(recommendation, dict) and recommendation.get("concept_id"):
                st.caption(f"最近推荐：{_concept_label(st, recommendation['concept_id'])}")
        else:
            st.warning("学习者状态暂时不可用。")
        warning = st.session_state.get("introai_persistence_warning")
        if isinstance(warning, str) and warning:
            st.warning(warning)
        with st.expander("本地学习记录说明", expanded=False):
            st.write("刷新页面或重启服务后会恢复当前本地档案的学习状态。")
            st.write("清空操作只影响当前本地档案；新无痕窗口会创建新档案。")
            st.write("复制当前 localhost URL 可在本机恢复同一档案；不提供跨设备同步。")
        if st.session_state.get("introai_confirm_clear_learning_records"):
            st.warning("确认后将清空当前浏览器 session 中的全部学习记录。")
            confirm_column, cancel_column = st.columns(2)
            if confirm_column.button("确认清空", key="introai_confirm_reset_all", type="primary"):
                try:
                    _get_learner_state_persistence_service(st).clear(
                        learner_id=_current_learner_id(st)
                    )
                except (AppServiceError, LearnerStatePersistenceError):
                    _log_persistence_failure("clear_failed", "clear")
                    st.session_state["introai_persistence_warning"] = "本次状态未能持久保存，未清空学习记录。"
                    st.rerun()
                    return
                reset_session_state(st.session_state)
                st.session_state.pop("introai_last_recommendation", None)
                st.session_state.pop("introai_learner_error", None)
                st.session_state.pop("introai_diagnostic_variant_round", None)
                st.rerun()
            if cancel_column.button("取消", key="introai_cancel_reset_all"):
                st.session_state.pop("introai_confirm_clear_learning_records", None)
                st.rerun()
        elif st.button("清空全部学习记录", key="introai_reset_all"):
            st.session_state["introai_confirm_clear_learning_records"] = True
            st.rerun()
        if st.button("创建新的本地学习档案", key="introai_new_local_profile"):
            learner_id = start_new_profile(st.query_params)
            reset_session_state(st.session_state)
            st.session_state["introai_learner_id"] = learner_id
            st.rerun()


def _render_module_selector(st: Any) -> None:
    """Render the one shared, registry-backed course-module selector."""
    try:
        options = load_registered_module_options(ROOT)
    except AppServiceError as error:
        st.warning(str(error))
        return
    module_ids = [item["module_id"] for item in options]
    current = st.session_state.get(_SELECTED_MODULE_KEY)
    if current not in module_ids:
        current = module_ids[0]
    labels = {
        item["module_id"]: item["display_name_zh"] + " / " + item["display_name_en"]
        for item in options
    }
    selected = st.selectbox(
        "当前课程模块",
        options=module_ids,
        index=module_ids.index(current),
        format_func=lambda module_id: labels[module_id],
        key="introai_module_selector",
    )
    if selected != current:
        _switch_selected_module(st, selected, valid_module_ids=set(module_ids))
        st.rerun()


def _switch_selected_module(st: Any, module_id: str, *, valid_module_ids: set[str]) -> None:
    """Change module context without changing persisted learner evidence."""
    if not isinstance(module_id, str) or module_id not in valid_module_ids:
        raise AppServiceError("未知课程模块，无法切换。")
    for key in _MODULE_SCOPED_SERVICE_KEYS:
        st.session_state.pop(key, None)
    clear_diagnostic_state(st.session_state)
    _clear_citation_preview(st.session_state)
    for key in (
        "introai_last_qa_result",
        "introai_qa_error",
        _QA_RETRY_STATE_KEY,
        "introai_last_qa_elapsed",
        "introai_qa_result_revision",
        "introai_qa_input_session_token",
        "introai_mastery_map_selected_concept",
        _MASTERY_MAP_ACTION_REVISION_KEY,
        "introai_mastery_map_view",
        "introai_mastery_map_layer_filter",
        "introai_pending_mastery_map_qa_question",
        "introai_mastery_map_navigation_message",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith("introai_qa_question_"):
            st.session_state.pop(key, None)
    st.session_state[_SELECTED_MODULE_KEY] = module_id
    learner_state = st.session_state.get("introai_learner_state")
    if isinstance(learner_state, dict):
        try:
            st.session_state["introai_last_recommendation"] = recommend_next_concept(
                _get_app_data(st)["knowledge_data"], learner_state
            )
        except (AppServiceError, ValueError):
            st.session_state.pop("introai_last_recommendation", None)


def _render_question_answering(st: Any) -> None:
    _render_scroll_anchor(st, "qa_input")
    if st.session_state.pop("introai_returned_to_qa", False):
        st.success("已返回课程问答，学习记录已保留。")
    map_navigation_message = st.session_state.pop(
        "introai_mastery_map_navigation_message", None
    )
    if isinstance(map_navigation_message, str) and map_navigation_message:
        st.info(map_navigation_message)
    module = _get_app_data(st)["module"]
    st.write("回答仅基于当前“" + module["display_name_zh"] + "”模块课件，并显示对应课件来源。")
    if module["module_id"] == "search_algorithms":
        st.caption(
            "示例：BFS 找到的是步数最少还是总代价最低？｜A* 的启发函数为什么要可采纳？｜UCS 为什么按累计路径代价选择下一个节点？"
        )
        placeholder = "例如：BFS 找到的是步数最少还是总代价最低？"
    else:
        st.caption("请围绕当前模块的课程材料提问；切换模块后，问答与引用范围会同时切换。")
        placeholder = "例如：请解释当前模块中的一个核心概念。"
    question_key = qa_question_widget_key(st.session_state)
    with st.form("introai_qa_form"):
        question = st.text_area(
            "输入课程问题",
            key=question_key,
            height=100,
            placeholder=placeholder,
        )
        submitted = st.form_submit_button("提交问题")
    rerun_after_success = False
    if submitted:
        if not isinstance(question, str) or not question.strip():
            st.warning("请输入问题后再提交。")
        else:
            rerun_after_success = _submit_qa_question(st, question=question)

    if rerun_after_success:
        st.rerun()

    error_message = st.session_state.get("introai_qa_error")
    if error_message:
        st.error(error_message)
    retry_state = st.session_state.get(_QA_RETRY_STATE_KEY)
    if _can_retry_qa_failure(retry_state):
        if st.button("重新尝试本次问题", key="introai_retry_qa_question"):
            if _submit_qa_question(st, question=retry_state["question"]):
                st.rerun()
    result = st.session_state.get("introai_last_qa_result")
    if not isinstance(result, dict):
        return
    view = format_qa_result(result)
    st.info(f"状态：{view['status_label']}")
    if view["answer"]:
        st.markdown(view["answer"])
    elapsed = st.session_state.get("introai_last_qa_elapsed")
    if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
        st.caption(f"本次回答用时 {max(0.0, elapsed):.1f} 秒")
    if view["citations"]:
        st.subheader("课件来源")
        answer_revision = _current_qa_result_revision(st.session_state)
        for citation_index, citation in enumerate(view["citations"]):
            st.markdown(
                f"- **{citation.get('section_title', '未命名章节')}** · "
                f"`{citation.get('source_file', '')}` · "
                f"{format_pages(citation['page_start'], citation['page_end'])} · "
                f"{source_role_label(citation.get('source_role'))}"
            )
            _render_citation_preview_button(
                st,
                citation=citation,
                index=citation_index,
                answer_revision=answer_revision,
            )
            _render_citation_preview_panel(
                st,
                citation=citation,
                index=citation_index,
                answer_revision=answer_revision,
            )
    if view["limitations"]:
        with st.expander("回答限制", expanded=False):
            for limitation in view["limitations"]:
                st.write(limitation)
    current_plan = resolve_qa_diagnostic_plan(
        qa_result=result,
        cached_plan=st.session_state.get(QA_DIAGNOSTIC_PLAN_KEY),
    )
    _render_qa_diagnostic_plan(st, plan=current_plan)
    with st.expander("开发者详情", expanded=False):
        st.json(
            {
                "understanding": result.get("understanding"),
                "retrieval": result.get("retrieval"),
                "diagnostic_plan": current_plan,
                "diagnostic_origin": st.session_state.get(DIAGNOSTIC_ORIGIN_KEY),
                "active_template_ids": _active_template_ids(st.session_state),
            }
        )


def _render_citation_preview_button(
    st: Any, *, citation: dict[str, Any], index: int, answer_revision: int
) -> None:
    """Render one isolated, explicit cited-page preview action."""

    widget_key = citation_preview_key(citation, index)
    if st.button("查看引用课件", key=f"{widget_key}_open"):
        _open_citation_preview(
            st,
            citation=citation,
            index=index,
            answer_revision=answer_revision,
        )
        # A clicked later citation would otherwise leave the earlier panel in
        # this same Streamlit run.  Re-render from the new selected state so
        # exactly one preview is inline beneath its own citation.
        st.rerun()


def _render_citation_preview_panel(
    st: Any, *, citation: dict[str, Any], index: int, answer_revision: int
) -> None:
    """Render a selected citation inline, with lazy range-bound navigation."""

    state = _citation_preview_state(
        st.session_state,
        citation=citation,
        index=index,
        answer_revision=answer_revision,
    )
    if state is None:
        return

    page_start, page_end = _citation_page_bounds(citation)
    current_page = state["page"]
    _render_scroll_anchor(st, "qa_citation_preview")
    st.markdown("#### 引用课件预览")
    st.caption(f"{citation.get('source_file', '')} · 第{current_page}页")
    st.caption(f"引用范围：{_citation_range_label(page_start, page_end)}")
    preview = preview_citation(
        citation,
        page=current_page,
        manifest_path=_get_app_data(st)["paths"]["course_material_manifest_path"],
    )
    if preview.available and preview.image_bytes:
        st.image(preview.image_bytes, caption=f"第 {preview.page} 页", use_container_width=True)
    else:
        st.info(preview_unavailable_message())

    widget_key = citation_preview_key(citation, index)
    if page_start != page_end:
        previous, page_label, next_page = st.columns((1, 2, 1))
        if previous.button(
            "← 上一页",
            key=f"{widget_key}_previous",
            disabled=current_page == page_start,
        ):
            state["page"] = current_page - 1
            st.session_state[_CITATION_PREVIEW_STATE_KEY] = state
            st.rerun()
        page_label.caption(f"第{current_page}页 / 引用范围{_citation_range_label(page_start, page_end)}")
        if next_page.button(
            "下一页 →",
            key=f"{widget_key}_next",
            disabled=current_page == page_end,
        ):
            state["page"] = current_page + 1
            st.session_state[_CITATION_PREVIEW_STATE_KEY] = state
            st.rerun()
    if st.button("收起", key=f"{widget_key}_close"):
        st.session_state.pop(_CITATION_PREVIEW_STATE_KEY, None)
        st.rerun()


def _citation_page_bounds(citation: dict[str, Any]) -> tuple[int, int]:
    """Return a UI range only when citation pages already have safe integers."""

    page_start, page_end = citation.get("page_start"), citation.get("page_end")
    if (
        type(page_start) is not int
        or type(page_end) is not int
        or page_start < 1
        or page_end < page_start
    ):
        raise ValueError("citation page range is invalid.")
    return page_start, page_end


def _citation_range_label(page_start: int, page_end: int) -> str:
    """Format only validated physical citation pages for the student UI."""

    return f"第{page_start}页" if page_start == page_end else f"第{page_start}–{page_end}页"


def _current_qa_result_revision(session_state: Any) -> int:
    """Return the current persisted QA-result namespace, or a safe zero value."""

    revision = session_state.get("introai_qa_result_revision", 0)
    return revision if type(revision) is int and revision >= 0 else 0


def _citation_preview_state(
    session_state: Any,
    *,
    citation: dict[str, Any],
    index: int,
    answer_revision: int,
) -> dict[str, int] | None:
    """Return one current-answer preview state without trusting stale widgets."""

    state = session_state.get(_CITATION_PREVIEW_STATE_KEY)
    if not isinstance(state, dict) or set(state) != {"answer_revision", "index", "page"}:
        return None
    if (
        type(state["answer_revision"]) is not int
        or type(state["index"]) is not int
        or type(state["page"]) is not int
        or state["answer_revision"] != answer_revision
        or state["index"] != index
    ):
        return None
    try:
        page_start, page_end = _citation_page_bounds(citation)
    except ValueError:
        return None
    if not page_start <= state["page"] <= page_end:
        return None
    return dict(state)


def _open_citation_preview(
    st: Any, *, citation: dict[str, Any], index: int, answer_revision: int
) -> None:
    """Open one inline preview and queue one fresh, fixed-anchor scroll event."""

    page_start, _ = _citation_page_bounds(citation)
    st.session_state[_CITATION_PREVIEW_STATE_KEY] = {
        "answer_revision": answer_revision,
        "index": index,
        "page": page_start,
    }
    current = st.session_state.get(_CITATION_PREVIEW_SCROLL_REVISION_KEY, 0)
    if type(current) is not int or current < 0:
        current = 0
    revision = current + 1
    st.session_state[_CITATION_PREVIEW_SCROLL_REVISION_KEY] = revision
    request_scroll(
        st.session_state,
        target="qa_citation_preview",
        event_id=f"qa-citation-preview-{answer_revision}-{revision}",
    )


def _clear_citation_preview(session_state: Any) -> None:
    """Clear only transient citation-preview state, including an unrendered scroll."""

    session_state.pop(_CITATION_PREVIEW_STATE_KEY, None)
    session_state.pop(_CITATION_PREVIEW_SCROLL_REVISION_KEY, None)
    pending = session_state.get(SCROLL_REQUEST_KEY)
    if isinstance(pending, dict) and pending.get("target") == "qa_citation_preview":
        session_state.pop(SCROLL_REQUEST_KEY, None)


def _submit_qa_question(st: Any, *, question: str) -> bool:
    """Submit exactly one saved question and return whether a rerun is needed."""
    try:
        service = _get_qa_service(st)
        started_at = time.monotonic()
        with st.spinner("正在理解问题、检索课件并生成回答……"):
            result = service.ask(question)
        elapsed = elapsed_seconds(started_at, time.monotonic())
        try:
            plan = _get_diagnostic_handoff_service(st).plan_from_qa_result(
                qa_result=result,
                exposed_template_ids=_exposed_template_ids(st),
            )
        except _PUBLIC_ERRORS as error:
            _log_qa_failure(error, "qa_handoff_construction")
            plan = result.get("diagnostic_plan") if isinstance(result, dict) else None
            if not isinstance(plan, dict):
                plan = {
                    "available": False,
                    "message": "当前没有与本题对应的审核验证题，本次仅提供课程回答。",
                }
        bound_result = store_qa_result_with_diagnostic_plan(
            st.session_state,
            qa_result=result,
            diagnostic_plan=plan,
        )
        st.session_state["introai_last_qa_elapsed"] = elapsed
        st.session_state.pop("introai_qa_error", None)
        _clear_citation_preview(st.session_state)
        st.session_state.pop(_QA_RETRY_STATE_KEY, None)
        revision = _next_qa_result_revision(st.session_state)
        if _is_explicit_diagnostic_result(bound_result):
            request_scroll(
                st.session_state,
                target="diagnostic_handoff",
                event_id=f"qa-explicit-diagnostic-{revision}",
            )
        return True
    except _PUBLIC_ERRORS as error:
        _record_qa_failure(st, question=question, error=error)
    except Exception as error:
        _record_qa_failure(st, question=question, error=error)
    return False


def _record_qa_failure(st: Any, *, question: str, error: BaseException) -> None:
    """Keep one transient retry record without touching learner evidence."""
    _log_qa_failure(error, getattr(error, "failure_stage", "qa_unknown"))
    st.session_state.pop("introai_last_qa_result", None)
    st.session_state.pop("introai_last_qa_elapsed", None)
    _clear_citation_preview(st.session_state)
    st.session_state.pop(QA_DIAGNOSTIC_PLAN_KEY, None)
    kind = getattr(error, "failure_kind", "internal_application_error")
    if kind not in _RETRYABLE_QA_FAILURE_KINDS | {"model_configuration"}:
        kind = "internal_application_error"
    correlation_id = getattr(error, "correlation_id", None)
    if not isinstance(correlation_id, str) or not correlation_id:
        correlation_id = uuid.uuid4().hex[:12]
    st.session_state["introai_qa_error"] = _friendly_error(error, correlation_id=correlation_id)
    if kind in _RETRYABLE_QA_FAILURE_KINDS:
        st.session_state[_QA_RETRY_STATE_KEY] = {
            "question": question,
            "failure_kind": kind,
            "correlation_id": correlation_id,
        }
    else:
        st.session_state.pop(_QA_RETRY_STATE_KEY, None)


def _can_retry_qa_failure(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("question"), str)
        and bool(value["question"].strip())
        and value.get("failure_kind") in _RETRYABLE_QA_FAILURE_KINDS
        and isinstance(value.get("correlation_id"), str)
    )


def _apply_pending_mastery_map_qa_prefill(st: Any) -> None:
    """Apply a map-requested prefill before the QA widget is created."""
    pending = st.session_state.pop("introai_pending_mastery_map_qa_question", None)
    if not isinstance(pending, str) or not pending.strip():
        return
    set_qa_question_value(st.session_state, pending)


def _render_qa_diagnostic_plan(
    st: Any, *, plan: dict[str, Any] | None = None
) -> None:
    """Render an optional, reviewed-plan handoff without starting it automatically."""
    if plan is None:
        plan = resolve_qa_diagnostic_plan(
            qa_result=st.session_state.get("introai_last_qa_result"),
            cached_plan=st.session_state.get(QA_DIAGNOSTIC_PLAN_KEY),
        )
    if not isinstance(plan, dict):
        return
    _render_scroll_anchor(st, "diagnostic_handoff")
    st.subheader("针对本题的快速诊断")
    if plan.get("available") is not True:
        st.info(plan.get("message", "当前没有与本题对应的审核验证题，本次仅提供课程回答。"))
        return
    template_ids = plan.get("template_ids")
    topic_ids = plan.get("planning_topic_ids", plan.get("topic_ids"))
    if not isinstance(template_ids, list) or not template_ids or not isinstance(topic_ids, list):
        st.info("当前没有与本题对应的审核验证题，本次仅提供课程回答。")
        return
    st.info(
        f"已找到 {len(template_ids)} 道与本题相关的人工审核诊断题，"
        "完成后可更新学习记录。"
    )
    st.caption(f"可用题目：{len(template_ids)} 题")
    titles = _topic_titles(st, topic_ids)
    if titles:
        st.write(
            "匹配知识点："
            + escape_algorithm_markdown_tokens("、".join(titles))
        )
    st.caption("题目来自人工审核模板，不由模型临时生成。")
    practice_only = _plan_is_practice_only(st, template_ids)
    if practice_only:
        st.info("你已经完成过这些人工审核题，本次重做用于巩固，不会重复提高掌握度。")
    pending_plan = st.session_state.get(PENDING_DIAGNOSTIC_PLAN_KEY)
    if has_active_diagnostic(st.session_state):
        if (
            st.session_state.get(DIAGNOSTIC_ORIGIN_KEY) == "qa_handoff"
            and isinstance(pending_plan, dict)
            and pending_plan.get("template_ids") == template_ids
        ):
            st.success("针对性快速诊断已准备好，请点击上方‘诊断学习’继续。")
        else:
            st.warning("当前已有未完成的诊断，请先完成或重新开始。")
        return
    if st.button(
        f"开始复习练习（{len(template_ids)}题）" if practice_only else f"开始审核诊断（{len(template_ids)}题）",
        key="introai_start_qa_handoff_diagnostic",
        type="primary",
    ):
        _start_qa_handoff_diagnostic(st, plan)
        return


def _start_qa_handoff_diagnostic(st: Any, plan: dict[str, Any]) -> None:
    """Start only the reviewed templates listed by a previously computed plan."""
    _start_reviewed_diagnostic(st, plan=plan, origin="qa_handoff")


def _start_reviewed_diagnostic(st: Any, *, plan: dict[str, Any], origin: str) -> None:
    """Start an existing reviewed plan without duplicating verification setup."""
    if origin not in {"qa_handoff", "mastery_map"}:
        raise ValueError("origin must be qa_handoff or mastery_map.")
    if has_active_diagnostic(st.session_state):
        st.warning("当前已有未完成的诊断，请先完成或重新开始。")
        return
    plan_copy = deepcopy(plan)
    try:
        workflow = _get_dual_track_diagnostic_workflow(st)
        clear_diagnostic_state(st.session_state)
        planning_topic_ids = plan_copy.get(
            "planning_topic_ids", plan_copy["topic_ids"]
        )
        result = workflow.start_quick_verification(
            concept_ids=planning_topic_ids,
            intent=plan_copy["intent"],
            template_ids=plan_copy["template_ids"],
            **_exposure_workflow_kwargs(st),
        )
        active_template_ids = result["session"]["verification_session"]["template_ids"]
        if active_template_ids != plan_copy["template_ids"]:
            raise DualTrackDiagnosticError("planned verification templates did not match session.")
        qa_result = st.session_state.get("introai_last_qa_result")
        if origin == "qa_handoff" and isinstance(qa_result, dict):
            store_qa_result_with_diagnostic_plan(
                st.session_state,
                qa_result=qa_result,
                diagnostic_plan=plan_copy,
            )
        elif origin == "qa_handoff":
            st.session_state[QA_DIAGNOSTIC_PLAN_KEY] = deepcopy(plan_copy)
        st.session_state[PENDING_DIAGNOSTIC_PLAN_KEY] = deepcopy(plan_copy)
        st.session_state[DIAGNOSTIC_ORIGIN_KEY] = origin
        st.session_state[HANDOFF_SOURCE_TOPICS_KEY] = list(planning_topic_ids)
        st.session_state["introai_diagnostic_mode"] = "quick"
        st.session_state["introai_dual_track_result"] = result
        st.session_state["introai_dual_track_session"] = deepcopy(result["session"])
        _request_scroll_for_diagnostic_result(st, result)
        st.success(
            "针对性快速诊断已准备好，请点击上方‘诊断学习’继续。"
            if origin == "qa_handoff"
            else "审核诊断已准备好，正在定位第一题。"
        )
    except _PUBLIC_ERRORS as error:
        if origin == "qa_handoff":
            st.session_state[QA_DIAGNOSTIC_PLAN_KEY] = deepcopy(plan_copy)
        st.error(_friendly_error(error))


def _topic_titles(st: Any, topic_ids: list[Any]) -> list[str]:
    """Translate validated concept IDs to student-facing Chinese titles."""
    try:
        data = _get_app_data(st)
    except AppServiceError:
        return []
    return [
        format_concept_label(topic_id, data["knowledge_data"])
        for topic_id in topic_ids
        if isinstance(topic_id, str)
    ]


def _concept_label(st: Any, concept_id: Any, *, developer: bool = False) -> str:
    try:
        knowledge_data = _get_app_data(st)["knowledge_data"]
    except AppServiceError:
        return "未知知识点"
    return format_concept_label(concept_id, knowledge_data, developer=developer)


def _get_mastery_map_static_inputs(st: Any) -> dict[str, Any]:
    """Load the small immutable map inputs once per Streamlit session."""
    cached = st.session_state.get("introai_mastery_map_static_inputs")
    if isinstance(cached, dict):
        return cached
    data = _get_app_data(st)
    paths = data["paths"]
    if "mastery_map_layout_path" not in paths or "concept_copy_zh_path" not in paths:
        raise MasteryMapError("当前模块尚未配置知识图谱布局。")
    valid_concept_ids = {
        point["id"] for point in data["knowledge_data"]["knowledge_points"]
    }
    templates_data = load_diagnostic_templates(
        paths["diagnostic_templates_path"],
        valid_concept_ids=valid_concept_ids,
    )
    inputs = {
        "layout_data": load_mastery_map_layout(
            paths["mastery_map_layout_path"]
        ),
        "templates_data": templates_data,
        "concept_copy_data": load_concept_copy_zh(
            paths["concept_copy_zh_path"]
        ),
    }
    st.session_state["introai_mastery_map_static_inputs"] = inputs
    return inputs


def _render_mastery_map(st: Any) -> None:
    """Render deterministic visual and card views over the existing course DAG."""
    _render_scroll_anchor(st, "mastery_map")
    _render_scroll_anchor(st, "mastery_map_overview")
    try:
        module = _get_app_data(st)["module"]
        if "mastery_map_layout_path" not in _get_app_data(st)["paths"]:
            st.subheader(module["display_name_zh"] + "学习状态")
            st.info("当前模块尚未提供知识图谱布局；课程问答与审核诊断仍可正常使用。")
            return
    except (AppServiceError, KeyError, TypeError):
        st.error("当前课程模块暂时不可用，请稍后重试。")
        return
    try:
        data = _get_app_data(st)
        static_inputs = _get_mastery_map_static_inputs(st)
        learner_state = st.session_state.get("introai_learner_state", {})
        map_model = build_mastery_map_model(
            knowledge_data=data["knowledge_data"],
            layout_data=static_inputs["layout_data"],
            templates_data=static_inputs["templates_data"],
            learner_state=learner_state,
            recommendation=st.session_state.get("introai_last_recommendation"),
        )
        selected_id = st.session_state.get("introai_mastery_map_selected_concept")
        if not isinstance(selected_id, str) or selected_id not in map_model["nodes_by_id"]:
            selected_id = default_selected_concept_id(map_model=map_model)
            st.session_state["introai_mastery_map_selected_concept"] = selected_id
        visual_model = build_visual_mastery_map_model(
            map_model=map_model,
            concept_copy_data=static_inputs["concept_copy_data"],
            knowledge_data=data["knowledge_data"],
            selected_concept_id=selected_id,
        )
    except (AppServiceError, DiagnosticTemplateError, MasteryMapError) as error:
        _LOGGER.warning("mastery_map_unavailable category=%s", type(error).__name__)
        st.error("知识掌握图谱暂时不可用，请稍后重试。")
        return

    st.subheader(module["display_name_zh"] + "知识掌握图谱")
    st.write(
        "节点状态反映系统根据审核诊断证据形成的掌握度估计，不是考试成绩。课程问答、浏览知识点和开放式反馈不会直接提高掌握度。"
    )
    _render_mastery_map_styles(st)
    _render_mastery_map_legend(st)
    _render_mastery_map_progress_summary(st, visual_model["summary"])
    recommended_id = visual_model["map_model"].get("recommended_concept_id")
    if isinstance(recommended_id, str):
        st.info("当前推荐：" + visual_model["nodes_by_id"][recommended_id]["title_zh"])

    # This is the actionable browser area, distinct from the summary above.
    _render_scroll_anchor(st, "mastery_map_graph")
    view = st.radio(
        "知识图谱视图",
        options=("关系图", "分层浏览"),
        index=1,
        horizontal=True,
        key="introai_mastery_map_view",
    )
    if view == "关系图":
        _render_mastery_map_global_graph(st, visual_model=visual_model)
        _render_mastery_map_focus(st, focus=visual_model["focus"])
    else:
        _render_mastery_map_layers(st, visual_model=visual_model, selected_id=selected_id)

    detail = build_concept_detail(
        map_model=visual_model["map_model"],
        concept_id=selected_id,
        learning_evidence=(
            learner_state.get("learning_evidence", [])
            if isinstance(learner_state, dict)
            else []
        ),
    )
    detail["recommendation_reason"] = _student_map_recommendation_reason(
        detail.get("recommendation_reason"), map_model=visual_model["map_model"]
    )
    _render_mastery_map_detail(st, detail=detail)
    for warning in visual_model["map_model"]["warnings"]:
        with st.expander("图谱开发者详情", expanded=False):
            st.write(warning)


def _render_mastery_map_progress_summary(st: Any, summary: dict[str, int]) -> None:
    """Show evidence-tracking counts as aligned native metric cards."""
    st.markdown("#### 学习进度摘要")
    cards = (
        ("知识点总数", summary["total"]),
        ("已追踪", summary["tracked"]),
        ("尚未追踪", summary["untracked"]),
        ("建议复习", summary["review"]),
        ("初步掌握", summary["developing"]),
        ("掌握较稳", summary["steady"]),
    )
    for offset in (0, 3):
        row = st.columns(3)
        for column, (label, value) in zip(row, cards[offset : offset + 3]):
            with column.container(border=True):
                st.metric(label, value)
    with st.container(border=True):
        st.metric("可审核诊断覆盖", summary["covered"])
    st.caption("以上是已有审核证据的覆盖与状态计数，不是课程完成百分比或考试成绩。")


def _render_mastery_map_global_graph(st: Any, *, visual_model: dict[str, Any]) -> None:
    st.markdown("#### 课程先修关系图")
    st.caption(
        "箭头从直接先修知识指向后续知识；紫色边框表示当前推荐，蓝色边框表示当前查看，相关边会加深。"
    )
    try:
        st.graphviz_chart(visual_model["global_dot"], width="stretch", height=680)
    except Exception as error:  # Graph rendering is progressive enhancement only.
        _LOGGER.debug("mastery_map_graphviz_unavailable category=%s", type(error).__name__)
        st.info("关系图暂时不可用；你仍可切换到“分层浏览”查看并操作全部知识点。")


def _render_mastery_map_focus(st: Any, *, focus: dict[str, Any] | None) -> None:
    """Render the selected node's direct DAG neighborhood without fragile graph clicks."""
    if not isinstance(focus, dict):
        return
    st.markdown("#### 当前知识点关系")
    prerequisite_column, selected_column, dependent_column = st.columns(3)
    with prerequisite_column:
        st.caption("直接先修")
        _render_mastery_map_relation_items(st, focus.get("prerequisites"), empty_label="无")
    with selected_column:
        st.caption("当前知识点")
        node = focus["selected"]
        st.markdown(f"**{escape(node['title_zh'])}**")
        st.write(node["mastery"]["label"])
        st.caption("可审核诊断" if node["coverage"]["available"] else "当前暂无审核诊断")
    with dependent_column:
        st.caption("直接后续知识")
        _render_mastery_map_relation_items(st, focus.get("dependents"), empty_label="无")


def _render_mastery_map_relation_items(st: Any, items: Any, *, empty_label: str) -> None:
    if not isinstance(items, list) or not items:
        st.write(empty_label)
        return
    for item in items:
        st.write("• " + item["title_zh"] + "（" + item["mastery"]["label"] + "）")


def _render_mastery_map_layers(st: Any, *, visual_model: dict[str, Any], selected_id: str) -> None:
    st.caption("分层浏览保留稳定的点击入口，适合小屏与关系图不可用时使用。")
    filter_key = st.selectbox(
        "筛选知识点",
        options=tuple(LAYER_FILTERS),
        format_func=lambda key: LAYER_FILTERS[key],
        key="introai_mastery_map_layer_filter",
    )
    layers = filter_layered_nodes(visual_model["layers"], filter_key=filter_key)
    if not layers:
        st.info("当前筛选没有符合条件的知识点；可切换到“全部知识点”继续浏览。")
        return
    for layer in layers:
        st.markdown(f"#### {layer['stage_name']}")
        nodes = layer["nodes"]
        columns = st.columns(min(3, len(nodes)))
        for index, node in enumerate(nodes):
            with columns[index % len(columns)]:
                _render_mastery_map_node(st, node=node, selected_id=selected_id)
                if st.button(
                    "查看详情",
                    key=f"introai_mastery_map_select_{node['concept_id']}",
                    type="primary" if node["concept_id"] == selected_id else "secondary",
                ):
                    _select_mastery_map_concept(
                        st,
                        concept_id=node["concept_id"],
                        valid_concept_ids=set(visual_model["nodes_by_id"]),
                    )
                    st.rerun()


def _render_mastery_map_styles(st: Any) -> None:
    """Keep status colours in a small, named UI token set."""
    st.markdown(
        """
        <style>
        :root {
          --introai-map-untracked-bg: #eef1f3;
          --introai-map-untracked-fg: #263238;
          --introai-map-review-bg: #e6f1e7;
          --introai-map-review-fg: #24452a;
          --introai-map-developing-bg: #cfe8d3;
          --introai-map-developing-fg: #173b20;
          --introai-map-steady-bg: #97cfa1;
          --introai-map-steady-fg: #102c17;
          --introai-map-unavailable-bg: #fff2cc;
          --introai-map-unavailable-fg: #4a3500;
        }
        .introai-mastery-map-card { border-radius: 0.5rem; padding: 0.6rem; min-height: 6.8rem; margin-bottom: 0.25rem; overflow-wrap: anywhere; }
        .introai-mastery-map-card strong { display: block; }
        .introai-mastery-map-card .introai-map-selected { font-weight: 700; }
        .mastery-map-status-untracked { background: var(--introai-map-untracked-bg); color: var(--introai-map-untracked-fg); }
        .mastery-map-status-review { background: var(--introai-map-review-bg); color: var(--introai-map-review-fg); }
        .mastery-map-status-developing { background: var(--introai-map-developing-bg); color: var(--introai-map-developing-fg); }
        .mastery-map-status-steady { background: var(--introai-map-steady-bg); color: var(--introai-map-steady-fg); }
        .mastery-map-status-unavailable { background: var(--introai-map-unavailable-bg); color: var(--introai-map-unavailable-fg); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_mastery_map_legend(st: Any) -> None:
    st.caption(
        "图例：尚未追踪｜建议复习｜初步掌握｜掌握较稳；“可审核诊断”表示存在人工审核的正式验证题。"
    )


def _render_mastery_map_node(st: Any, *, node: dict[str, Any], selected_id: str) -> None:
    mastery = node["mastery"]
    score = mastery["score"]
    score_text = "" if score is None else f"掌握度估计：{score:.2f}"
    recommendation = '<div class="introai-map-selected">当前推荐</div>' if node["is_recommended"] else ""
    selected = '<div class="introai-map-selected">当前选中</div>' if node["concept_id"] == selected_id else ""
    coverage = node["coverage"]
    coverage_text = (
        f"可审核诊断 · {coverage['template_count']}题"
        if coverage["available"]
        else "当前暂无审核诊断"
    )
    lines = [
        f'<div class="introai-mastery-map-card {mastery["css_token"]}">',
        f"<strong>{escape(node['title_zh'])}</strong>",
        f"<div>{escape(mastery['label'])}</div>",
    ]
    if score_text:
        lines.append(f"<div>{score_text}</div>")
    lines.extend((f"<div>{escape(coverage_text)}</div>", recommendation, selected, "</div>"))
    st.markdown("".join(lines), unsafe_allow_html=True)


def _render_mastery_map_detail(st: Any, *, detail: dict[str, Any]) -> None:
    _render_scroll_anchor(st, "mastery_map_detail")
    st.markdown("### 知识点详情")
    st.subheader(detail["title_zh"])
    if isinstance(detail.get("title_en"), str) and detail["title_en"]:
        st.caption(detail["title_en"])
    st.markdown("#### 状态信息")
    mastery = detail["mastery"]
    score = mastery["score"]
    st.write(
        "系统估计掌握度："
        + (f"{score:.2f}" if score is not None else "暂无记录")
        + f"（{mastery['label']}）"
    )
    st.caption("该数值基于审核诊断证据形成的估计，不是考试成绩；课程问答和浏览不会直接提高它。")
    st.write(
        f"审核诊断覆盖：{detail['coverage']['label']}（{detail['coverage']['template_count']}题）"
    )
    st.write("概念说明：" + detail.get("summary_zh", "暂无学生端概念说明。"))
    st.markdown("#### 关系信息")
    prerequisite_titles = [item["title_zh"] for item in detail["prerequisites"]]
    st.write("直接先修：" + ("、".join(prerequisite_titles) if prerequisite_titles else "无"))
    dependent_titles = [item["title_zh"] for item in detail.get("dependents", [])]
    st.write("直接后续知识：" + ("、".join(dependent_titles) if dependent_titles else "无"))
    st.write("最近学习证据：" + detail["evidence_summary"]["label"])
    st.write("最近更新时间：暂无记录")
    if detail["is_recommended"]:
        st.info("当前推荐：" + (detail.get("recommendation_reason") or "建议继续学习此知识点。"))

    st.markdown("#### 下一步操作")
    overview_column, question_column, diagnostic_column = st.columns(3)
    if overview_column.button(
        "↑ 返回知识图谱",
        key="introai_mastery_map_return_overview",
    ):
        _return_to_mastery_map_overview(st)
        st.rerun()
    if question_column.button(
        "围绕此知识点提问",
        key=f"introai_mastery_map_ask_{detail['concept_id']}",
    ):
        st.session_state["introai_pending_mastery_map_qa_question"] = concept_question_prefill(concept=detail)
        st.session_state["introai_mastery_map_navigation_message"] = "已预填一个课程问题；请检查后自行提交。"
        request_scroll(
            st.session_state,
            target="qa_input",
            event_id=f"mastery-map-qa-{detail['concept_id']}",
        )
        st.rerun()
    if detail["coverage"]["available"]:
        if diagnostic_column.button(
            f"开始审核诊断（{detail['coverage']['template_count']}题）",
            key=f"introai_mastery_map_start_{detail['concept_id']}",
            type="primary",
        ):
            _start_mastery_map_diagnostic(st, concept_id=detail["concept_id"])
    else:
        diagnostic_column.info("当前暂无人工审核诊断题")

    with st.expander("图谱开发者详情", expanded=False):
        st.json(
            {
                "concept_id": detail["concept_id"],
                "raw_mastery": detail["mastery"]["score"],
                "production_template_ids": detail["coverage"]["template_ids"],
                "prerequisite_ids": [item["concept_id"] for item in detail["prerequisites"]],
                "evidence_template_ids": detail["evidence_summary"]["template_ids"],
            }
        )


def _student_map_recommendation_reason(reason: Any, *, map_model: dict[str, Any]) -> str | None:
    """Translate known internal IDs in an existing recommendation for students."""
    if not isinstance(reason, str) or not reason.strip():
        return None
    nodes = map_model.get("nodes_by_id") if isinstance(map_model, dict) else None
    if not isinstance(nodes, dict):
        return "建议继续学习此知识点。"
    translated = reason.strip()
    for concept_id, node in sorted(nodes.items(), key=lambda item: len(item[0]), reverse=True):
        title = node.get("title_zh") if isinstance(node, dict) else None
        if not isinstance(title, str) or not title:
            continue
        translated = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(concept_id)}(?![A-Za-z0-9_])",
            title,
            translated,
        )
    if re.search(r"\b[a-z][a-z0-9_]*_[a-z0-9_]+\b", translated):
        return "建议继续学习此知识点。"
    return translated


def _select_mastery_map_concept(
    st: Any, *, concept_id: str, valid_concept_ids: set[str]
) -> bool:
    """Select a known map node and queue one post-rerun detail transition."""
    if (
        not isinstance(concept_id, str)
        or not isinstance(valid_concept_ids, set)
        or concept_id not in valid_concept_ids
    ):
        raise MasteryMapError("Unknown mastery-map concept selection.")
    st.session_state["introai_mastery_map_selected_concept"] = concept_id
    return _request_mastery_map_scroll(st, target="mastery_map_detail")


def _request_mastery_map_scroll(st: Any, *, target: str) -> bool:
    """Create a fresh transient map event for every explicit user action."""
    revision = _next_mastery_map_action_revision(st.session_state)
    return request_scroll(
        st.session_state,
        target=target,
        event_id=f"mastery-map-action-{revision}",
    )


def _return_to_mastery_map_overview(st: Any) -> bool:
    """Queue the actionable graph area without changing the selection."""
    return _request_mastery_map_scroll(st, target="mastery_map_graph")


def _next_mastery_map_action_revision(session_state: Any) -> int:
    """Return the next non-persistent revision used for map-only UI actions."""
    if not hasattr(session_state, "get") or not hasattr(session_state, "__setitem__"):
        raise ValueError("session_state must be a mutable mapping.")
    current = session_state.get(_MASTERY_MAP_ACTION_REVISION_KEY, 0)
    if isinstance(current, bool) or not isinstance(current, int) or current < 0:
        current = 0
    revision = current + 1
    session_state[_MASTERY_MAP_ACTION_REVISION_KEY] = revision
    return revision


def _start_mastery_map_diagnostic(st: Any, *, concept_id: str) -> None:
    """Reuse the reviewed handoff and session constructor; never create questions."""
    try:
        plan = _get_diagnostic_handoff_service(st).plan(
            topic_ids=[concept_id], intent="diagnostic_request",
            exposed_template_ids=_exposed_template_ids(st),
        )
        if plan.get("available") is not True or not plan.get("template_ids"):
            st.warning("当前没有可启动的审核诊断，请先查看课程讲解。")
            return
        _start_reviewed_diagnostic(st, plan=plan, origin="mastery_map")
        if isinstance(st.session_state.get("introai_dual_track_result"), dict):
            st.rerun()
    except _PUBLIC_ERRORS as error:
        st.error(_friendly_error(error))


def _next_qa_result_revision(session_state: Any) -> int:
    current = session_state.get("introai_qa_result_revision", 0)
    if isinstance(current, bool) or not isinstance(current, int) or current < 0:
        current = 0
    revision = current + 1
    session_state["introai_qa_result_revision"] = revision
    return revision


def _is_explicit_diagnostic_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    response = result.get("response")
    return isinstance(response, dict) and response.get("status") == "diagnostic_available"


def _active_template_ids(session_state: Any) -> list[str]:
    if not hasattr(session_state, "get"):
        return []
    session = session_state.get("introai_dual_track_session")
    verification = session.get("verification_session") if isinstance(session, dict) else None
    template_ids = verification.get("template_ids") if isinstance(verification, dict) else None
    return list(template_ids) if isinstance(template_ids, list) else []


def _render_scroll_anchor(st: Any, target: str) -> None:
    """Render one stable, whitelist-backed anchor without changing focus."""
    st.markdown(scroll_anchor_markup(target), unsafe_allow_html=True)


def _render_pending_scroll(st: Any) -> None:
    """Consume one requested UI transition after all fixed anchors are rendered."""
    request = consume_scroll_request(st.session_state)
    if request is None:
        return
    try:
        from streamlit.components.v1 import html

        # ``components.v1.html`` itself has no key parameter. A fresh,
        # validated container key gives every explicit event a fresh iframe,
        # including A -> B and A -> A map-detail navigation.
        with st.container(key=scroll_component_key(request["event_id"])):
            html(
                scroll_script_markup(
                    request["target"],
                    event_id=request["event_id"],
                    activate_tab_index={
                        "qa_input": 0,
                        "qa_citation_preview": 0,
                        "diagnostic_question": 1,
                        "diagnostic_completion": 1,
                        "mastery_map": 2,
                        "mastery_map_overview": 2,
                        "mastery_map_graph": 2,
                        "mastery_map_detail": 2,
                    }.get(request["target"]),
                ),
                height=0,
                width=0,
            )
    except Exception as error:  # Progressive enhancement must never block learning.
        _LOGGER.debug("ui_scroll_unavailable category=%s", type(error).__name__)


def _request_scroll_for_diagnostic_result(st: Any, result: Any) -> bool:
    """Queue at most one scroll for a new question or the completed summary."""
    if not isinstance(result, dict):
        return False
    phase = result.get("phase")
    if result.get("exposure_persistence_degraded") is True:
        st.warning("学习记录暂时无法持久保存；本次会话仍会避免重复计入同一道题。")
    if phase == "completed":
        return request_scroll(
            st.session_state,
            target="diagnostic_completion",
            event_id="diagnostic-completion",
        )
    if phase not in {"formative", "verification"}:
        return False
    section = result.get(phase)
    question = section.get("question") if isinstance(section, dict) else None
    if not isinstance(question, dict):
        return False
    step_number = question.get("step_number")
    stable_id = question.get("template_id", question.get("prompt_id", question.get("id")))
    if (
        isinstance(step_number, bool)
        or not isinstance(step_number, int)
        or step_number < 1
        or not isinstance(stable_id, str)
        or not stable_id
    ):
        return False
    return request_scroll(
        st.session_state,
        target="diagnostic_question",
        event_id=f"diagnostic-{phase}-{step_number}-{stable_id}",
    )


def _render_diagnostic(st: Any) -> None:
    """Render formative dialogue first, then reviewed mastery verification."""
    if "introai_learner_state" not in st.session_state:
        st.error(
            st.session_state.get(
                "introai_learner_error", "学习者状态不可用，暂时无法开始诊断。"
            )
        )
        return
    try:
        workflow = _get_dual_track_diagnostic_workflow(st)
        data = _get_app_data(st)
    except AppServiceError as error:
        st.error(str(error))
        return

    tracks_data = data.get("tracks_data") or {}
    tracks = tracks_data.get("tracks", []) if isinstance(tracks_data, dict) else []
    module = data["module"]
    default_track_id = module.get("default_formative_track_id")
    track = next(
        (item for item in tracks if item.get("id") == default_track_id),
        None,
    )
    if isinstance(track, dict):
        st.subheader(track.get("title", "BFS → 等步代价 → UCS"))
        st.write("三步目标：理解 BFS 的逐层扩展、等步代价条件，以及不等代价时 UCS 的作用。")

    result = st.session_state.get("introai_dual_track_result")
    if not isinstance(result, dict):
        st.subheader("选择诊断方式")
        st.write("推荐先用快速诊断完成受审核的选择题验证；开放式检查仅用于学习反馈。")
        quick_concepts = list(module["default_diagnostic_concept_ids"])
        try:
            quick_plan = _get_diagnostic_handoff_service(st).plan(
                topic_ids=quick_concepts,
                intent="diagnostic_request",
                max_templates=3,
                exposed_template_ids=_exposed_template_ids(st),
            )
            quick_practice_only = _plan_is_practice_only(
                st, quick_plan.get("template_ids", [])
            )
        except _PUBLIC_ERRORS:
            quick_plan, quick_practice_only = None, False
        formative_available = isinstance(track, dict)
        columns = st.columns(2) if formative_available else (st.container(),)
        quick_column = columns[0]
        quick_label = (
            f"开始复习练习（{len(quick_plan['template_ids'])}题）"
            if quick_practice_only and isinstance(quick_plan, dict)
            else "快速诊断（推荐）"
        )
        if quick_column.button(quick_label, key="introai_start_quick_diagnostic", type="primary"):
            try:
                clear_diagnostic_state(st.session_state)
                result = workflow.start_quick_verification(
                    concept_ids=quick_concepts, **_exposure_workflow_kwargs(st)
                )
                st.session_state["introai_diagnostic_mode"] = "quick"
                st.session_state[DIAGNOSTIC_ORIGIN_KEY] = "default"
                st.session_state["introai_dual_track_result"] = result
                st.session_state["introai_dual_track_session"] = deepcopy(result["session"])
                st.session_state.pop("introai_diagnostic_error", None)
                _request_scroll_for_diagnostic_result(st, result)
                st.rerun()
            except _PUBLIC_ERRORS as error:
                st.error(_friendly_error(error))
        if formative_available and columns[1].button("深度理解检查（可选）", key="introai_start_formative_diagnostic"):
            try:
                clear_diagnostic_state(st.session_state)
                result = workflow.start(
                    track_id=default_track_id,
                    variant_round=diagnostic_variant_round(st.session_state),
                )
                st.session_state["introai_diagnostic_mode"] = "formative"
                st.session_state[DIAGNOSTIC_ORIGIN_KEY] = "formative"
                st.session_state["introai_dual_track_result"] = result
                st.session_state["introai_dual_track_session"] = deepcopy(result["session"])
                st.session_state.pop("introai_diagnostic_error", None)
                _request_scroll_for_diagnostic_result(st, result)
                st.rerun()
            except _PUBLIC_ERRORS as error:
                st.error(_friendly_error(error))
        return

    session = st.session_state.get("introai_dual_track_session")
    if not isinstance(session, dict):
        st.error("诊断会话暂时不可用，请重新开始诊断。")
        return

    pending_plan = st.session_state.get(PENDING_DIAGNOSTIC_PLAN_KEY)
    if (
        st.session_state.get(DIAGNOSTIC_ORIGIN_KEY) == "qa_handoff"
        and isinstance(pending_plan, dict)
        and isinstance(pending_plan.get("template_ids"), list)
    ):
        st.subheader("针对刚才问题的快速诊断")
        titles = _topic_titles(
            st,
            pending_plan.get(
                "planning_topic_ids", pending_plan.get("topic_ids", [])
            ),
        )
        st.caption(f"本次共 {len(pending_plan['template_ids'])} 道审核验证题。")
        if titles:
            st.write("匹配知识点：" + "、".join(titles))
        st.caption("完成后，结果将用于更新学习记录。")

    phase = result.get("phase")
    if phase == "completed":
        _render_completed_verification(st, result)
        return
    if phase == "verification_ready":
        _render_formative_feedback(st, result.get("formative"))
        st.success("形成性理解检查已完成。本阶段只提供学习反馈，不更新掌握度。")
        if st.button("开始掌握度验证", key="introai_start_verification"):
            try:
                concepts = list(module["default_diagnostic_concept_ids"])
                next_result = workflow.start_verification(
                    session=deepcopy(session), concept_ids=concepts,
                    **_exposure_workflow_kwargs(st),
                )
                st.session_state["introai_dual_track_result"] = next_result
                st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
                _request_scroll_for_diagnostic_result(st, next_result)
                st.rerun()
            except _PUBLIC_ERRORS as error:
                st.error(_friendly_error(error))
        return
    if phase == "formative":
        _render_formative_step(st, workflow, result, session)
        return
    if phase == "verification":
        if result.get("practice_only") is True:
            st.info("当前为复习练习：仍会给出答案反馈，但不会重复提高掌握度。")
        elif result.get("attempt_mode") == "mixed":
            st.info("本轮包含正式验证与复习练习；只有尚未完成过的审核题会更新学习记录。")
        _render_verification_step(st, workflow, result, session)
        return
    if phase == "verification_unavailable":
        st.info(result.get("message", "本次结果仅作为学习反馈。"))
        if st.button("重新开始诊断", key="introai_restart_unavailable_diagnostic"):
            advance_diagnostic_variant_round(st.session_state)
            clear_diagnostic_state(st.session_state)
            st.rerun()
        return
    st.error("诊断状态暂时不可用，请重新开始诊断。")


def _render_formative_step(st: Any, workflow: Any, result: dict[str, Any], session: dict[str, Any]) -> None:
    formative = result.get("formative", {})
    question = formative.get("question") if isinstance(formative, dict) else None
    if not isinstance(question, dict):
        st.error("形成性问题暂时不可用，请重新开始诊断。")
        return
    _render_scroll_anchor(st, "diagnostic_question")
    _render_formative_feedback(st, formative)
    if (
        st.session_state.get("introai_formative_feedback_error")
        or formative.get("feedback_unavailable") is True
    ):
        st.warning("本次智能反馈暂时不可用，你仍可以继续学习。")
    st.caption("开放式反馈可能无法覆盖所有正确表达，不直接影响你的学习记录。")
    st.progress(question["step_number"] / question["total_steps"], text=f"形成性第 {question['step_number']} / {question['total_steps']} 题")
    st.subheader(question["prompt"])
    question_key = question.get("prompt_id", question["id"])
    answer_key = (
        f"introai_formative_answer_{question_key}_{question['step_number']}_"
        f"{question['attempt_number']}"
    )
    with st.form(f"introai_formative_form_{answer_key}"):
        answer = st.text_area("输入你的答案", key=answer_key, height=130)
        submitted = st.form_submit_button("提交形成性回答")
    if submitted:
        try:
            next_result = workflow.submit_formative(session=deepcopy(session), answer=answer)
            st.session_state["introai_dual_track_result"] = next_result
            st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
            st.session_state.pop("introai_formative_feedback_error", None)
            _request_scroll_for_diagnostic_result(st, next_result)
            st.rerun()
        except _PUBLIC_ERRORS as error:
            # Formative feedback is advisory.  A recoverable semantic or
            # feedback failure must not trap the learner on this prompt.
            st.session_state["introai_formative_feedback_error"] = True
            st.rerun()

    retry_column, continue_column = st.columns(2)
    if retry_column.button("再试一次", key=f"introai_formative_retry_{answer_key}"):
        st.session_state.pop("introai_formative_feedback_error", None)
        st.rerun()
    if continue_column.button("继续下一题", key=f"introai_formative_continue_{answer_key}"):
        try:
            next_result = workflow.continue_formative(session=deepcopy(session))
            st.session_state["introai_dual_track_result"] = next_result
            st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
            st.session_state.pop("introai_formative_feedback_error", None)
            _request_scroll_for_diagnostic_result(st, next_result)
            st.rerun()
        except _PUBLIC_ERRORS:
            # Keep the same safe continuation affordance; never expose a
            # lower-level semantic or adapter error in formative study.
            st.session_state["introai_formative_feedback_error"] = True
            st.rerun()


def _render_formative_feedback(st: Any, formative: Any) -> None:
    if not isinstance(formative, dict) or not formative.get("formative_status"):
        return
    label = formative.get("formative_status_label", "需要澄清")
    status = formative.get("formative_status")
    renderer = st.success if status == "understood" else st.warning if status == "likely_misconception" else st.info
    renderer(f"系统给出的学习反馈：{label}")
    for message in formative.get("formative_feedback", []):
        st.write(f"可以进一步说明：{message}")
    question = formative.get("clarifying_question")
    if isinstance(question, str) and question:
        st.info(question)


def _render_verification_step(st: Any, workflow: Any, result: dict[str, Any], session: dict[str, Any]) -> None:
    verification = result.get("verification", {})
    try:
        # Result.evaluation is intentionally retained as a previous-answer
        # flash, but the prompt bundle must always be rebuilt from the latest
        # verification session.  Never combine a cached prompt with current
        # choices or infer a template from the displayed step number.
        question = workflow.current_verification_question(session=deepcopy(session))
    except _PUBLIC_ERRORS:
        st.error("掌握度验证题暂时不可用，请重新开始诊断。")
        return
    verification_session = session.get("verification_session", {})
    interaction_state = verification_session.get("interaction_state")
    evaluation = verification.get("evaluation") if isinstance(verification, dict) else None
    _render_scroll_anchor(st, "diagnostic_question")
    st.caption("掌握度验证：受审核的确定性选择题，完成后才会更新学习状态。")
    st.progress(question["step_number"] / question["total_steps"], text=f"验证第 {question['step_number']} / {question['total_steps']} 题")
    st.subheader(question["prompt"])
    if interaction_state == "revealing":
        _render_verification_reveal(st, workflow, session, question)
        return
    if interaction_state == "retry_ready":
        st.warning("回答不正确，还可再试 1 次。")
        if isinstance(evaluation, dict):
            for message in evaluation.get("feedback", []):
                st.write(message)
        retry_column, reveal_column = st.columns(2)
        if retry_column.button("再试一次", key=f"introai_verification_retry_{question['template_id']}"):
            try:
                next_result = workflow.choose_verification_hint_retry(
                    session=deepcopy(session), template_id=question["template_id"],
                    **_exposure_workflow_kwargs(st),
                )
                st.session_state["introai_dual_track_result"] = next_result
                st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
                st.rerun()
            except _PUBLIC_ERRORS as error:
                st.error(_friendly_error(error))
        if reveal_column.button("查看答案与解析", key=f"introai_verification_reveal_after_wrong_{question['template_id']}"):
            _request_verification_reveal(st, workflow, session, question)
        return
    if interaction_state != "answering":
        st.error("验证题状态暂时不可用，请重新开始诊断。")
        return
    if question["attempt_number"] == 1:
        st.caption("本题最多作答 2 次。")
    elif verification_session.get("pending_assistance"):
        st.info("请根据提示完成本次作答。")
    choices = choice_text_by_id(question["choices"])
    key = (
        f"introai_verification_{session.get('track_id')}_{session.get('phase')}_"
        f"{question['step_number']}_{question['attempt_number']}_{question['template_id']}"
    )
    question_type = question.get("question_type")
    if question_type not in {"single_choice", "multiple_choice"}:
        st.error("当前验证题型尚未接入学生界面。")
        return
    with st.form(f"introai_verification_form_{key}"):
        if question_type == "single_choice":
            submitted_answer = st.radio(
                "选择答案",
                list(choices),
                format_func=lambda choice_id: choices[choice_id],
                index=None,
                key=key,
            )
        else:
            submitted_answer = st.multiselect(
                "选择所有正确答案",
                list(choices),
                format_func=lambda choice_id: choices[choice_id],
                default=None,
                key=key,
            )
        submitted = st.form_submit_button("提交验证答案")
    if submitted:
        if submitted_answer is None or (
            isinstance(submitted_answer, list) and not submitted_answer
        ):
            if question_type == "multiple_choice":
                st.warning("请至少选择一个答案。")
            else:
                st.warning("请先选择一个答案。")
            return
        try:
            next_result = workflow.submit_verification(
                session=deepcopy(session),
                answer=deepcopy(submitted_answer),
                submitted_template_id=question["template_id"],
                learner_state=deepcopy(st.session_state["introai_learner_state"]),
                **_exposure_workflow_kwargs(st),
            )
            st.session_state["introai_dual_track_result"] = next_result
            st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
            if isinstance(next_result.get("state_update"), dict):
                st.session_state["introai_learner_state"] = deepcopy(next_result["state_update"]["learner_state"])
                st.session_state["introai_last_recommendation"] = deepcopy(next_result["state_update"].get("recommendation"))
                _record_completed_verification_summary(st, next_result)
                _queue_completed_persistence(st, next_result)
                _flush_pending_persistence(st)
            _request_scroll_for_diagnostic_result(st, next_result)
            st.rerun()
        except _PUBLIC_ERRORS as error:
            st.error(_friendly_error(error))
    if question["attempt_number"] == 1:
        if st.button("查看答案", key=f"introai_verification_reveal_before_attempt_{question['template_id']}"):
            _request_verification_reveal(st, workflow, session, question)


def _request_verification_reveal(st: Any, workflow: Any, session: dict[str, Any], question: dict[str, Any]) -> None:
    try:
        next_result = workflow.request_verification_reveal(
            session=deepcopy(session), template_id=question["template_id"],
            **_exposure_workflow_kwargs(st),
        )
        st.session_state["introai_dual_track_result"] = next_result
        st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
        st.rerun()
    except _PUBLIC_ERRORS as error:
        st.error(_friendly_error(error))


def _render_verification_reveal(st: Any, workflow: Any, session: dict[str, Any], question: dict[str, Any]) -> None:
    try:
        reveal = workflow.current_verification_reveal(session=deepcopy(session))
    except _PUBLIC_ERRORS:
        st.error("答案解析暂时不可用，请重新开始诊断。")
        return
    st.success(f"正确答案：{reveal['correct_choice_text']}")
    st.info(f"解析：{reveal['explanation']}")
    st.caption("本题答案已展示，本次结果不会作为独立掌握证据。")
    verification_session = session["verification_session"]
    is_last_step = verification_session["step_index"] == len(verification_session["template_ids"]) - 1
    acknowledge_label = "我理解了，完成诊断" if is_last_step else "我理解了，进入下一题"
    if st.button(acknowledge_label, key=f"introai_verification_acknowledge_{question['template_id']}"):
        try:
            next_result = workflow.acknowledge_verification_reveal(
                session=deepcopy(session),
                template_id=question["template_id"],
                learner_state=deepcopy(st.session_state["introai_learner_state"]),
                **_exposure_workflow_kwargs(st),
            )
            st.session_state["introai_dual_track_result"] = next_result
            st.session_state["introai_dual_track_session"] = deepcopy(next_result["session"])
            if isinstance(next_result.get("state_update"), dict):
                st.session_state["introai_learner_state"] = deepcopy(next_result["state_update"]["learner_state"])
                st.session_state["introai_last_recommendation"] = deepcopy(next_result["state_update"].get("recommendation"))
                _record_completed_verification_summary(st, next_result)
                _queue_completed_persistence(st, next_result)
                _flush_pending_persistence(st)
            _request_scroll_for_diagnostic_result(st, next_result)
            st.rerun()
        except _PUBLIC_ERRORS as error:
            st.error(_friendly_error(error))


def _render_completed_verification(st: Any, result: dict[str, Any]) -> None:
    _render_scroll_anchor(st, "diagnostic_completion")
    practice_only = result.get("practice_only") is True
    if practice_only:
        st.success("复习练习已完成。")
        st.info("本次为复习练习，未重复计入掌握度。")
    else:
        st.success("掌握度验证已完成。")
    verification = result.get("verification", {})
    summary = verification.get("summary", {}) if isinstance(verification, dict) else {}
    st.write(f"通过验证题：{summary.get('passed_steps', 0)} / {summary.get('total_steps', 0)}")
    state_update = result.get("state_update")
    if isinstance(state_update, dict):
        st.subheader("掌握度更新")
        data = _get_app_data(st)
        rows = update_rows(state_update, data["knowledge_data"])
        if rows:
            st.dataframe([{"知识点": row["title_zh"], "更新后掌握度": row["new_mastery"]} for row in rows], hide_index=True, width="stretch")
        recommendation = state_update.get("recommendation")
        if isinstance(recommendation, dict) and recommendation.get("concept_id"):
            st.subheader("下一步推荐")
            st.write(_concept_label(st, recommendation["concept_id"]))
    elif result.get("attempt_mode") == "mixed":
        st.info("本轮仅将尚未完成过的审核题计入学习记录；其余题目为复习练习。")
    if st.button("查看知识掌握图谱", key="introai_open_mastery_map_after_verification"):
        selected_concept_id = _completed_mastery_map_concept_id(result)
        if selected_concept_id is not None:
            st.session_state["introai_mastery_map_selected_concept"] = selected_concept_id
        request_scroll(
            st.session_state,
            target="mastery_map",
            event_id="verification-completion-mastery-map",
        )
        st.rerun()
    if st.button("重新开始诊断", key="introai_restart_dual_track_diagnostic"):
        advance_diagnostic_variant_round(st.session_state)
        clear_diagnostic_state(st.session_state)
        st.rerun()
    if st.button("返回课程问答（保留学习记录）", key="introai_return_to_qa"):
        clear_diagnostic_state(st.session_state, preserve_learning_outcome=True)
        st.session_state["introai_returned_to_qa"] = True
        request_scroll(
            st.session_state,
            target="qa_input",
            event_id="return-to-qa",
        )
        st.rerun()


def _completed_mastery_map_concept_id(result: Any) -> str | None:
    """Choose a reproducible updated node after verification completion.

    State integration may update more than one concept.  The map uses the
    first stable concept ID rather than claiming a non-existent unique primary.
    """
    if not isinstance(result, dict):
        return None
    state_update = result.get("state_update")
    updates = state_update.get("updates") if isinstance(state_update, dict) else None
    if not isinstance(updates, list):
        return None
    concept_ids = sorted(
        update.get("concept_id")
        for update in updates
        if isinstance(update, dict)
        and isinstance(update.get("concept_id"), str)
        and update["concept_id"]
    )
    return concept_ids[0] if concept_ids else None


def _record_completed_verification_summary(st: Any, result: dict[str, Any]) -> None:
    """Keep a completed verification trace while clearing only transient UI state."""
    summary = _formal_evidence_summary(result)
    if not isinstance(summary, dict):
        return
    summaries = st.session_state.get("introai_completed_verification_summaries")
    if not isinstance(summaries, list):
        summaries = []
    snapshot = deepcopy(summary)
    if not summaries or summaries[-1] != snapshot:
        summaries.append(snapshot)
    st.session_state["introai_completed_verification_summaries"] = summaries


def _get_learner_state_persistence_service(st: Any) -> Any:
    service = st.session_state.get("introai_learner_state_persistence_service")
    if service is not None:
        return service
    configured_path = st.session_state.get("introai_state_db_path")
    db_path = configured_path if isinstance(configured_path, Path) else None
    service = build_learner_state_persistence_service(root=ROOT, db_path=db_path)
    st.session_state["introai_learner_state_persistence_service"] = service
    return service


def _current_learner_id(st: Any) -> str:
    learner_id = st.session_state.get("introai_learner_id")
    if not isinstance(learner_id, str) or not learner_id:
        learner_id, _ = resolve_learner_id(st.query_params)
        st.session_state["introai_learner_id"] = learner_id
    return learner_id


def _exposure_workflow_kwargs(st: Any) -> dict[str, str]:
    """Pass learner identity only when real profile state has been initialized."""
    learner_id = st.session_state.get("introai_learner_id")
    if isinstance(learner_id, str) and learner_id:
        return {"learner_id": learner_id}
    if hasattr(st, "query_params"):
        return {"learner_id": _current_learner_id(st)}
    # Small offline UI fakes from earlier releases intentionally omit profiles.
    return {}


def _exposed_template_ids(st: Any) -> set[str]:
    """Load only this profile's minimal reviewed-template exposure keys."""
    if not _exposure_workflow_kwargs(st):
        return set()
    try:
        exposures = _get_learner_state_persistence_service(st).reviewed_template_exposures(
            learner_id=_current_learner_id(st)
        )
    except (AppServiceError, LearnerStatePersistenceError):
        st.session_state["introai_persistence_warning"] = (
            "学习记录暂时无法持久保存；本次会话仍会避免重复计入同一道题。"
        )
        return set()
    return set(exposures) if isinstance(exposures, dict) else set()


def _plan_is_practice_only(st: Any, template_ids: list[Any]) -> bool:
    if not isinstance(template_ids, list) or not template_ids:
        return False
    exposed = _exposed_template_ids(st)
    return all(isinstance(template_id, str) and template_id in exposed for template_id in template_ids)


def _queue_completed_persistence(st: Any, result: dict[str, Any]) -> None:
    summary = _formal_evidence_summary(result)
    if not isinstance(summary, dict):
        return
    fingerprint = json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    pending = st.session_state.get("introai_pending_persistence")
    if isinstance(pending, dict) and pending.get("fingerprint") == fingerprint:
        return
    st.session_state["introai_pending_persistence"] = {
        "event_id": str(uuid.uuid4()),
        "fingerprint": fingerprint,
        "summary": deepcopy(summary),
    }


def _formal_evidence_summary(result: Any) -> dict[str, Any] | None:
    """Return only policy-approved formal evidence, with legacy test fallback."""
    if not isinstance(result, dict) or result.get("practice_only") is True:
        return None
    summary = result.get("formal_evidence_summary")
    if isinstance(summary, dict):
        return summary
    if not isinstance(result.get("state_update"), dict):
        return None
    verification = result.get("verification")
    legacy_summary = verification.get("summary") if isinstance(verification, dict) else None
    return legacy_summary if isinstance(legacy_summary, dict) else None


def _flush_pending_persistence(st: Any) -> None:
    pending = st.session_state.get("introai_pending_persistence")
    state = st.session_state.get("introai_learner_state")
    if not isinstance(pending, dict) or not isinstance(state, dict):
        return
    try:
        _get_learner_state_persistence_service(st).save_completed(
            learner_id=_current_learner_id(st),
            learner_state=state,
            diagnostic_summary=pending["summary"],
            event_id=pending["event_id"],
        )
    except (AppServiceError, LearnerStatePersistenceError, KeyError, TypeError):
        _log_persistence_failure("save_failed", "save")
        st.session_state["introai_persistence_warning"] = "本次状态未能持久保存，当前会话中的学习记录仍可继续使用。"
        return
    st.session_state.pop("introai_pending_persistence", None)
    st.session_state.pop("introai_persistence_warning", None)


def _log_persistence_failure(error: Any, stage: str) -> None:
    """Log only a bounded local failure category, never state or prompt data."""
    category = type(error).__name__ if isinstance(error, BaseException) else str(error)
    _LOGGER.warning("learner_state_persistence_failure stage=%s category=%s", stage, category[:80])


def _render_diagnostic_flash(st: Any, flash: dict[str, Any]) -> None:
    """Render one sanitized diagnostic evaluation after a workflow rerun."""
    coverage_score = flash.get("coverage_score", flash.get("score", 0.0))
    if flash.get("type") == "success":
        if flash.get("moved_to_next_step") and flash.get("next_step"):
            st.success(f"回答通过，已进入第 {flash['next_step']} 步。覆盖度：{coverage_score:.2f}")
        else:
            st.success(f"回答通过。覆盖度：{coverage_score:.2f}")
    elif flash.get("unresolved"):
        st.warning(DIAGNOSTIC_UNRESOLVED_MESSAGE)
    else:
        st.warning(f"本次回答未通过。覆盖度：{coverage_score:.2f}")
    if flash.get("assisted_practice"):
        if flash.get("assistance_level") == "reveal":
            st.info(
                "练习复述通过。由于本次作答发生在参考答案展示后，"
                "掌握度更新仍依据展示答案前的独立作答表现。"
            )
        else:
            st.info(
                "本次作答在针对性提示后完成。掌握度更新仍依据提示前的独立作答表现。"
            )
    teaching_feedback = flash.get("teaching_feedback")
    matched_labels = flash.get("matched_labels", [])
    if matched_labels:
        st.success("已确认要点：" + "；".join(matched_labels))
    semantic_supported_labels = flash.get("semantic_supported_labels", [])
    if semantic_supported_labels:
        st.info("系统识别到你可能表达了：" + "；".join(semantic_supported_labels))
    missing_labels = flash.get("missing_labels", [])
    if missing_labels:
        st.info("还需要说明：" + "；".join(missing_labels))
    clarifying_question = flash.get("clarifying_question")
    if isinstance(clarifying_question, str) and clarifying_question:
        st.info(clarifying_question)
    misconception_feedback = flash.get("misconception_feedback", [])
    if misconception_feedback:
        for item in misconception_feedback:
            st.warning("需要纠正：" + item)
    if isinstance(teaching_feedback, dict):
        feedback_items = [
            item
            for item in teaching_feedback.get("messages", [])
            if item not in misconception_feedback
            and not item.startswith("还需要说明：")
        ]
    else:
        feedback_items = [
            item
            for item in flash.get("feedback", [])
            if item not in misconception_feedback
            and not item.startswith("还需要说明：")
        ]
    for feedback in feedback_items:
        st.info(feedback)
    if isinstance(teaching_feedback, dict):
        model_answer = teaching_feedback.get("model_answer")
        explanation = teaching_feedback.get("explanation")
        if isinstance(model_answer, str) and model_answer:
            st.subheader("参考答案")
            st.write(model_answer)
        if isinstance(explanation, str) and explanation:
            st.subheader("解析")
            st.write(explanation)
    developer_trace = flash.get("developer_trace")
    if isinstance(developer_trace, dict):
        with st.expander("本次评分开发者详情", expanded=False):
            st.json(
                {
                    "正确要点覆盖度": developer_trace.get("coverage_score"),
                    "掌握度证据分数": developer_trace.get("mastery_score"),
                    "评分来源": developer_trace.get("assessment_source"),
                    "语义状态": developer_trace.get("semantic_status"),
                    "语义置信度": developer_trace.get("semantic_confidence"),
                    "语义判定": developer_trace.get("semantic_judgments"),
                }
            )
            with st.expander("原始评分 trace", expanded=False):
                st.json(developer_trace)


def _render_completed_diagnostic(st: Any, result: dict) -> None:
    _render_scroll_anchor(st, "diagnostic_completion")
    st.success("诊断已完成。")
    diagnostic = result["diagnostic"]
    summary = diagnostic.get("summary", {})
    st.write(
        f"通过步骤：{summary.get('passed_steps', 0)} / {summary.get('total_steps', 0)}，"
        f"未解决步骤：{summary.get('unresolved_steps', 0)}"
    )
    state_update = result.get("state_update")
    if isinstance(state_update, dict):
        st.subheader("掌握度更新")
        data = _get_app_data(st)
        rows = update_rows(state_update, data["knowledge_data"])
        if rows:
            st.dataframe(
                [
                    {
                        "知识点": row["title_zh"],
                        "更新后掌握度": row["new_mastery"],
                    }
                    for row in rows
                ],
                hide_index=True,
                width="stretch",
            )
            with st.expander("开发者详情", expanded=False):
                st.json(_developer_update_rows(rows))
                with st.expander("原始内部 JSON", expanded=False):
                    st.json(rows)
        misconception_ids = state_update.get("added_misconception_ids", [])
        if misconception_ids:
            st.subheader("本轮新观察到的 misconception")
            for misconception_id in misconception_ids:
                st.write(f"- {misconception_label(misconception_id)}")
        recommendation = state_update.get("recommendation")
        st.subheader("下一步推荐")
        if recommendation and recommendation.get("concept_id"):
            st.write(_concept_label(st, recommendation["concept_id"]))
            if recommendation.get("reason"):
                st.caption(recommendation["reason"])
        else:
            st.write("当前没有额外推荐。")
    if st.button("重新开始诊断", key="introai_restart_diagnostic"):
        advance_diagnostic_variant_round(st.session_state)
        clear_diagnostic_state(st.session_state)
        st.rerun()


def _get_qa_service(st: Any):
    if "introai_qa_service" not in st.session_state:
        adapter = _get_shared_adapter(st, required=False)
        if adapter is None:
            adapter = _UnavailableQAAdapter(
                st.session_state.get("introai_shared_deepseek_configuration_error")
            )
        st.session_state["introai_qa_service"] = build_question_answer_service(
            root=ROOT, adapter=adapter, **_module_service_kwargs(st)
        )
    return st.session_state["introai_qa_service"]


def _get_diagnostic_handoff_service(st: Any):
    """Cache the deterministic reviewed-template planner for the UI session."""
    if "introai_diagnostic_handoff_service" not in st.session_state:
        module_kwargs = _module_service_kwargs(st)
        st.session_state["introai_diagnostic_handoff_service"] = (
            build_diagnostic_handoff_service(root=ROOT)
            if not module_kwargs
            else build_diagnostic_handoff_service(root=ROOT, **module_kwargs)
        )
    return st.session_state["introai_diagnostic_handoff_service"]


def _get_diagnostic_workflow(st: Any):
    if "introai_diagnostic_workflow" not in st.session_state:
        adapter = _get_shared_adapter(st, required=False)
        semantic_adjudicator = (
            DiagnosticSemanticAdjudicator(adapter=adapter) if adapter is not None else None
        )
        st.session_state["introai_diagnostic_workflow"] = build_diagnostic_workflow(
            root=ROOT,
            semantic_adjudicator=semantic_adjudicator,
            **_module_service_kwargs(st),
        )
    return st.session_state["introai_diagnostic_workflow"]


def _get_dual_track_diagnostic_workflow(st: Any):
    """Return the Streamlit-facing dual-track workflow with one shared adapter."""
    if "introai_dual_track_diagnostic_workflow" not in st.session_state:
        adapter = _get_shared_adapter(st, required=False)
        semantic_adjudicator = (
            DiagnosticSemanticAdjudicator(adapter=adapter) if adapter is not None else None
        )
        st.session_state["introai_dual_track_diagnostic_workflow"] = (
            build_dual_track_diagnostic_workflow(
                root=ROOT,
                semantic_adjudicator=semantic_adjudicator,
                exposure_policy=build_reviewed_template_exposure_policy(
                    root=ROOT,
                    persistence_service=_get_learner_state_persistence_service(st),
                ),
                **_module_service_kwargs(st),
            )
        )
    return st.session_state["introai_dual_track_diagnostic_workflow"]


def _get_shared_adapter(st: Any, *, required: bool):
    """Create one session-scoped adapter; diagnostics remain offline if absent."""
    if "introai_shared_deepseek_adapter" in st.session_state:
        return st.session_state["introai_shared_deepseek_adapter"]
    from introai_tutor.deepseek_adapter import DeepSeekAdapter

    try:
        adapter = DeepSeekAdapter.from_env()
    except DeepSeekConfigurationError as error:
        if required:
            raise
        st.session_state["introai_shared_deepseek_configuration_error"] = error
        return None
    st.session_state["introai_shared_deepseek_adapter"] = adapter
    return adapter


class _UnavailableQAAdapter:
    """Deferred adapter failure so local diagnostic routing remains available."""

    def __init__(self, error: Any) -> None:
        self._error = (
            error
            if isinstance(error, DeepSeekConfigurationError)
            else DeepSeekConfigurationError("DeepSeek configuration is unavailable.")
        )

    def complete_json(self, **_: Any) -> dict[str, Any]:
        raise self._error


def _developer_update_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Present state-update traces with stable Chinese labels before raw JSON."""
    selection_reasons = {
        "last_unassisted_observation": "最后一次未受教学帮助影响的作答",
        "no_unassisted_observation_no_mastery_update": "没有独立作答证据，未更新掌握度",
    }
    assistance_labels = {
        "none": "无帮助",
        "hint": "提示后作答",
        "scaffold": "回答框架后作答",
        "clarification": "澄清问题后作答",
        "reveal": "参考答案后作答",
    }
    return [
        {
            "知识点": row.get("title_zh"),
            "旧掌握度": row.get("old_mastery"),
            "原始作答分数": row.get("observation_scores"),
            "作答帮助级别": [
                assistance_labels.get(level, "未提供")
                for level in row.get("observation_assistance_levels", [])
            ],
            "最终采用的独立信号": row.get("selected_signal"),
            "信号选择原因": selection_reasons.get(
                row.get("selection_reason"), "未提供"
            ),
            "更新后掌握度": row.get("new_mastery"),
        }
        for row in rows
    ]


def _get_app_data(st: Any) -> dict:
    module_id = _selected_module_id(st)
    cached = st.session_state.get("introai_app_data")
    if not isinstance(cached, dict) or cached.get("module", {}).get("module_id") != module_id:
        st.session_state["introai_app_data"] = load_module_app_package(
            ROOT, module_id=module_id
        )
    return st.session_state["introai_app_data"]


def _selected_module_id(st: Any) -> str | None:
    """Return the selected module ID, allowing registry default resolution."""
    value = st.session_state.get(_SELECTED_MODULE_KEY)
    return value if isinstance(value, str) and value else None


def _module_service_kwargs(st: Any) -> dict[str, str]:
    """Avoid changing legacy Search service-call signatures unnecessarily."""
    module_id = _selected_module_id(st)
    return {"module_id": module_id} if module_id is not None else {}


def _log_qa_failure(error: BaseException, stage: str) -> None:
    """Log only bounded operational metadata; never prompts, keys, or chunks."""
    correlation_id = getattr(error, "correlation_id", None) or uuid.uuid4().hex[:12]
    failure_stage = getattr(error, "failure_stage", None) or stage
    failure_kind = getattr(error, "failure_kind", None) or "internal_application_error"
    # Unknown local exceptions may embed untrusted values.  Keep their type
    # and correlation ID, but do not turn their arbitrary message into a log.
    raw_message = str(error) if isinstance(error, _PUBLIC_ERRORS) else "redacted"
    message = _SECRET_LOG_PATTERN.sub(r"\1[REDACTED]", raw_message)
    message = " ".join(message.split())[:180]
    _LOGGER.warning(
        "freeform QA failure stage=%s kind=%s correlation_id=%s exception=%s message=%s",
        failure_stage,
        failure_kind,
        correlation_id,
        type(error).__name__,
        message,
    )


def _friendly_error(error: BaseException, *, correlation_id: str | None = None) -> str:
    kind = getattr(error, "failure_kind", None)
    if kind == "model_configuration" or isinstance(error, DeepSeekConfigurationError):
        return "课程自由问答服务当前未正确配置。审核诊断和知识掌握图谱仍可使用。"
    if kind in {
        "upstream_timeout",
        "upstream_connection",
        "upstream_rate_limited",
        "upstream_server_error",
    }:
        return "模型服务暂时不可用。你的问题已保留，学习记录未受影响。"
    if kind == "invalid_model_response":
        return "模型本次返回的内容无法安全解析。本次未写入学习记录，请重新尝试。"
    if isinstance(error, DeepSeekConfigurationError):
        return "自由问答尚未配置 DeepSeek API；诊断学习仍可正常使用。"
    if isinstance(error, (DeepSeekRequestError, DeepSeekResponseError)):
        return "自由问答服务暂时不可用，请稍后重试；诊断学习仍可正常使用。"
    if isinstance(error, AppServiceError):
        return str(error)
    if isinstance(error, (QuestionUnderstandingError, GroundedAnswerError, TutorServiceError)):
        suffix = f"问题编号：{correlation_id}。" if correlation_id else ""
        return f"系统暂时无法完成本次处理。学习记录未受影响。{suffix}"
    if isinstance(
        error,
        (
            DiagnosticTutorError,
            DiagnosticStateIntegrationError,
            DiagnosticFeedbackError,
            DiagnosticSemanticAdjudicationError,
            DiagnosticWorkflowError,
        ),
    ):
        return "诊断学习暂时无法完成，请重新开始诊断。"
    return "操作暂时无法完成，请稍后重试。"


if __name__ == "__main__":  # pragma: no cover - Streamlit executes this file
    main()
