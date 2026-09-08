"""Composition root for module-bounded Streamlit services.

Each selected module supplies its own material, knowledge, and reviewed
template package. Learner-state persistence remains course-wide so global,
namespaced concept/template IDs can coexist without changing its schema.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from introai_tutor.course_modules import (
    CourseModuleError,
    aggregate_module_knowledge_data,
    aggregate_template_ids,
    load_all_course_module_data,
    load_course_module_data,
    load_course_module_registry,
    module_selector_options,
)
from introai_tutor.deterministic_diagnostic_request import DeterministicDiagnosticRequestParser
from introai_tutor.diagnostic_handoff import DiagnosticHandoffService
from introai_tutor.diagnostic_state_integration import DiagnosticStateIntegrationService
from introai_tutor.diagnostic_tutoring import DiagnosticTutorService
from introai_tutor.diagnostic_workflow import DiagnosticWorkflowService
from introai_tutor.dual_track_diagnostics import DualTrackDiagnosticWorkflowService
from introai_tutor.grounded_answering import GroundedAnswerService
from introai_tutor.learner import validate_learner_state
from introai_tutor.learner_state_persistence import LearnerStatePersistenceService
from introai_tutor.learner_state_repository import SQLiteLearnerStateRepository
from introai_tutor.question_understanding import (
    SEARCH_TOPIC_SELECTION_GUIDANCE,
    QuestionUnderstandingService,
)
from introai_tutor.recommend import build_evidence_aware_recommendation
from introai_tutor.reviewed_template_exposure import ReviewedTemplateExposurePolicy
from introai_tutor.template_selection import TemplateSelectionService
from introai_tutor.tutor_service import TutorService
from introai_tutor.verification_diagnostics import VerificationDiagnosticService


class AppServiceError(RuntimeError):
    """Raised when registered module data cannot be assembled safely."""


def load_app_data(root: Path, *, module_id: str | None = None) -> dict[str, Any]:
    """Load the legacy public data shape for one selected module.

    Extra package metadata intentionally stays internal so existing callers of
    the Search-only composition root remain source compatible.
    """
    data = _load_module_data(root, module_id=module_id)
    return {
        key: deepcopy(data[key])
        for key in ("knowledge_data", "course_data", "questions_data", "tracks_data")
    }


def _load_module_data(root: Path, *, module_id: str | None = None) -> dict[str, Any]:
    """Load one selected module package including registry metadata."""
    root = _validate_root(root)
    try:
        data = load_course_module_data(root, module_id)
        if data["questions_data"] is not None:
            DiagnosticTutorService(
                questions_data=data["questions_data"],
                tracks_data=data["tracks_data"],
                valid_concept_ids=_valid_concept_ids(data),
            )
        return deepcopy(data)
    except (CourseModuleError, ValueError) as error:
        raise AppServiceError(f"课程数据加载失败：{error}") from None


def load_module_app_package(root: Path, *, module_id: str | None = None) -> dict[str, Any]:
    """Load one module package including its reviewed registry metadata.

    The Streamlit composition root needs this module-aware representation.
    ``load_app_data`` deliberately retains its older narrow return shape for
    callers that only expect the Search reference data objects.
    """
    return _load_module_data(root, module_id=module_id)


def load_registered_module_options(root: Path) -> list[dict[str, str]]:
    """Return stable module IDs and display labels for the UI selector."""
    root = _validate_root(root)
    try:
        return module_selector_options(load_course_module_registry(root))
    except CourseModuleError as error:
        raise AppServiceError(f"课程模块注册加载失败：{error}") from None


def load_global_learning_catalog(root: Path) -> tuple[dict[str, Any], set[str]]:
    """Load all packages for learner-state validation and repeat protection."""
    root = _validate_root(root)
    try:
        bundles = load_all_course_module_data(root)
        return aggregate_module_knowledge_data(bundles), aggregate_template_ids(bundles)
    except CourseModuleError as error:
        raise AppServiceError(f"全课程学习目录加载失败：{error}") from None


def build_question_answer_service(
    *, root: Path, adapter: Any, module_id: str | None = None
) -> TutorService:
    """Build one module-bounded, injected-adapter QA service."""
    data = _load_module_data(root, module_id=module_id)
    try:
        scope = data["module"]["display_name_en"] + " course module"
        valid_concept_ids = _valid_concept_ids(data)
        misconception_ids, templates_data = _reviewed_template_inputs(data)
        selector = TemplateSelectionService(
            templates_data=templates_data,
            valid_concept_ids=valid_concept_ids,
            valid_misconception_ids=misconception_ids,
        )
        return TutorService(
            understanding_service=QuestionUnderstandingService(
                adapter=adapter,
                knowledge_data=data["knowledge_data"],
                course_scope_label=scope,
                topic_selection_guidance=(
                    SEARCH_TOPIC_SELECTION_GUIDANCE
                    if data["module"]["module_id"] == "search_algorithms"
                    else None
                ),
            ),
            answer_service=GroundedAnswerService(adapter=adapter, course_scope_label=scope),
            course_data=data["course_data"],
            valid_topic_ids=valid_concept_ids,
            diagnostic_plan_service=DiagnosticHandoffService(
                template_selection_service=selector
            ),
            deterministic_diagnostic_request_parser=DeterministicDiagnosticRequestParser(
                knowledge_data=data["knowledge_data"]
            ),
        )
    except ValueError as error:
        raise AppServiceError(f"自由问答服务初始化失败：{error}") from None


def build_diagnostic_workflow(
    *, root: Path, semantic_adjudicator: Any | None = None, module_id: str | None = None
) -> DiagnosticWorkflowService:
    """Build the legacy formative workflow for a module that registers one."""
    data = _load_module_data(root, module_id=module_id)
    if data["questions_data"] is None:
        raise AppServiceError("当前模块未配置开放式形成性诊断轨道。")
    try:
        valid_concept_ids = _valid_concept_ids(data)
        _, templates_data = _reviewed_template_inputs(data)
        global_knowledge, _ = load_global_learning_catalog(root)
        return DiagnosticWorkflowService(
            diagnostic_service=DiagnosticTutorService(
                questions_data=data["questions_data"],
                tracks_data=data["tracks_data"],
                valid_concept_ids=valid_concept_ids,
                semantic_adjudicator=semantic_adjudicator,
            ),
            state_integration_service=DiagnosticStateIntegrationService(
                knowledge_data=global_knowledge,
                recommendation_fn=build_evidence_aware_recommendation(
                    templates=templates_data["templates"]
                ),
            ),
        )
    except ValueError as error:
        raise AppServiceError(f"诊断服务初始化失败：{error}") from None


def build_dual_track_diagnostic_workflow(
    *,
    root: Path,
    semantic_adjudicator: Any | None = None,
    exposure_policy: ReviewedTemplateExposurePolicy | None = None,
    module_id: str | None = None,
) -> DualTrackDiagnosticWorkflowService:
    """Build module verification; formative dialogue is optional by registry."""
    data = _load_module_data(root, module_id=module_id)
    try:
        valid_concept_ids = _valid_concept_ids(data)
        misconception_ids, templates_data = _reviewed_template_inputs(data)
        formative_service = None
        if data["questions_data"] is not None:
            formative_service = DiagnosticTutorService(
                questions_data=data["questions_data"],
                tracks_data=data["tracks_data"],
                valid_concept_ids=valid_concept_ids,
                semantic_adjudicator=semantic_adjudicator,
            )
        global_knowledge, _ = load_global_learning_catalog(root)
        return DualTrackDiagnosticWorkflowService(
            formative_service=formative_service,
            template_selection_service=TemplateSelectionService(
                templates_data=templates_data,
                valid_concept_ids=valid_concept_ids,
                valid_misconception_ids=misconception_ids,
            ),
            verification_service=VerificationDiagnosticService(
                templates=templates_data["templates"]
            ),
            state_integration_service=DiagnosticStateIntegrationService(
                knowledge_data=global_knowledge,
                recommendation_fn=build_evidence_aware_recommendation(
                    templates=templates_data["templates"]
                ),
            ),
            exposure_policy=exposure_policy,
            template_concept_ids={
                item["id"]: list(item["concept_ids"])
                for item in templates_data["templates"]
            },
        )
    except ValueError as error:
        raise AppServiceError(f"双轨诊断服务初始化失败：{error}") from None


def build_diagnostic_handoff_service(
    *, root: Path, module_id: str | None = None
) -> DiagnosticHandoffService:
    """Build deterministic QA-to-reviewed-template planning for one module."""
    data = _load_module_data(root, module_id=module_id)
    try:
        valid_concept_ids = _valid_concept_ids(data)
        misconception_ids, templates_data = _reviewed_template_inputs(data)
        return DiagnosticHandoffService(
            template_selection_service=TemplateSelectionService(
                templates_data=templates_data,
                valid_concept_ids=valid_concept_ids,
                valid_misconception_ids=misconception_ids,
            )
        )
    except ValueError as error:
        raise AppServiceError(f"诊断规划服务初始化失败：{error}") from None


def load_initial_learner_state(root: Path) -> dict[str, Any]:
    """Return an empty, course-wide learner state without prefilled concepts."""
    root = _validate_root(root)
    try:
        knowledge_data, _ = load_global_learning_catalog(root)
        state = {
            "student_id": "streamlit_user",
            "course_id": knowledge_data["course"]["course_id"],
            "mastery": {},
            "misconceptions": [],
            "learning_evidence": [],
            "preferred_style": "visual_example",
        }
        validate_learner_state(state, knowledge_data)
        return deepcopy(state)
    except (ValueError, AppServiceError) as error:
        raise AppServiceError(f"学习者状态加载失败：{error}") from None


def build_learner_state_persistence_service(
    *, root: Path, db_path: Path | None = None
) -> LearnerStatePersistenceService:
    """Build one course-wide persistence boundary for all registered modules."""
    try:
        knowledge_data, template_ids = load_global_learning_catalog(root)
        return LearnerStatePersistenceService(
            repository=SQLiteLearnerStateRepository(db_path),
            knowledge_data=knowledge_data,
            valid_template_ids=template_ids,
        )
    except (ValueError, RuntimeError, AppServiceError) as error:
        raise AppServiceError(f"学习记录持久化服务初始化失败：{error}") from None


def build_reviewed_template_exposure_policy(
    *, root: Path, persistence_service: LearnerStatePersistenceService
) -> ReviewedTemplateExposurePolicy:
    """Build repeat-evidence protection over all registered reviewed templates."""
    if not isinstance(persistence_service, LearnerStatePersistenceService):
        raise AppServiceError("reviewed-template exposure requires learner-state persistence.")
    try:
        _, template_ids = load_global_learning_catalog(root)
        return ReviewedTemplateExposurePolicy(
            persistence_service=persistence_service,
            valid_template_ids=template_ids,
        )
    except (ValueError, AppServiceError) as error:
        raise AppServiceError(f"审核题重复证据策略初始化失败：{error}") from None


def _reviewed_template_inputs(data: dict[str, Any]) -> tuple[set[str] | None, dict[str, Any]]:
    misconceptions = data.get("misconception_ids")
    if misconceptions is not None:
        misconceptions = set(misconceptions)
    return misconceptions, deepcopy(data["templates_data"])


def _valid_concept_ids(data: dict[str, Any]) -> set[str]:
    return {point["id"] for point in data["knowledge_data"]["knowledge_points"]}


def _validate_root(root: Any) -> Path:
    if not isinstance(root, Path):
        raise AppServiceError("root must be a pathlib.Path.")
    if not root.is_dir():
        raise AppServiceError(f"项目目录不存在：{root}")
    return root
