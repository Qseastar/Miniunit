"""Application service connecting validated learner domain state to SQLite."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from introai_tutor.knowledge import validate_knowledge_points
from introai_tutor.learner import validate_learner_state
from introai_tutor.learner_state_repository import (
    LearnerStatePersistenceError,
    SQLiteLearnerStateRepository,
)


class LearnerStatePersistenceService:
    """Validate restored state while leaving mastery and evidence policy unchanged."""

    def __init__(
        self,
        *,
        repository: SQLiteLearnerStateRepository,
        knowledge_data: dict[str, Any],
        valid_template_ids: set[str],
    ) -> None:
        if not isinstance(repository, SQLiteLearnerStateRepository):
            raise LearnerStatePersistenceError("repository must be SQLiteLearnerStateRepository.")
        validate_knowledge_points(knowledge_data)
        if not isinstance(valid_template_ids, set) or not all(
            isinstance(item, str) and item for item in valid_template_ids
        ):
            raise LearnerStatePersistenceError("valid_template_ids must be a non-empty set.")
        self._repository = repository
        self._knowledge_data = deepcopy(knowledge_data)
        self._concept_ids = {
            item["id"] for item in knowledge_data["knowledge_points"]
        }
        self._template_ids = set(valid_template_ids)

    @property
    def repository(self) -> SQLiteLearnerStateRepository:
        return self._repository

    def restore(self, *, learner_id: str, empty_state: dict[str, Any]) -> dict[str, Any]:
        """Create or restore an anonymous profile; never recover UI transient state."""
        validate_learner_state(empty_state, self._knowledge_data)
        loaded = self._repository.load_profile(learner_id)
        if loaded is None:
            state = deepcopy(empty_state)
            state["student_id"] = learner_id
            self._repository.save_profile(learner_id=learner_id, learner_state=state)
            return {
                "learner_state": state,
                "completed_summaries": [],
                "warnings": [],
                "created": True,
            }

        state = deepcopy(loaded.learner_state)
        warnings = list(loaded.warnings)
        unknown_concepts = set(state["mastery"]) - self._concept_ids
        if unknown_concepts:
            for concept_id in sorted(unknown_concepts):
                state["mastery"].pop(concept_id, None)
            warnings.append("部分未知知识点记录未恢复。")
        valid_summaries: list[dict[str, Any]] = []
        for summary in loaded.completed_summaries:
            template_ids = [item["template_id"] for item in summary["steps"]]
            if not all(template_id in self._template_ids for template_id in template_ids):
                warnings.append("一条引用未知审核题的记录未恢复。")
                continue
            valid_summaries.append(deepcopy(summary))
        state["learning_evidence"] = [
            item for item in state["learning_evidence"]
            if isinstance(item, dict) and all(template_id in self._template_ids for template_id in item.get("template_ids", []))
        ]
        try:
            validate_learner_state(state, self._knowledge_data)
        except ValueError as error:
            raise LearnerStatePersistenceError(
                f"Recovered learner state is invalid: {error}"
            ) from None
        return {
            "learner_state": state,
            "completed_summaries": valid_summaries,
            "warnings": warnings,
            "created": False,
        }

    def save_completed(
        self,
        *,
        learner_id: str,
        learner_state: dict[str, Any],
        diagnostic_summary: dict[str, Any],
        event_id: str,
    ) -> bool:
        """Persist only a completed, reviewed verification after domain update."""
        validate_learner_state(learner_state, self._knowledge_data)
        _validate_summary_templates(diagnostic_summary, self._template_ids)
        return self._repository.append_evidence(
            learner_id=learner_id,
            learner_state=learner_state,
            completed_summary=diagnostic_summary,
            event_id=event_id,
        )

    def clear(self, *, learner_id: str) -> None:
        self._repository.clear_profile(learner_id)

    def reviewed_template_exposures(self, *, learner_id: str) -> dict[str, dict[str, str]]:
        """Return valid reviewed-template exposure metadata for one profile."""
        exposures = self._repository.reviewed_template_exposures(learner_id)
        return {
            template_id: deepcopy(metadata)
            for template_id, metadata in exposures.items()
            if template_id in self._template_ids
        }

    def claim_template_exposure(
        self, *, learner_id: str, template_id: str, reason: str
    ) -> bool:
        """Persist one first-exposure claim; ``True`` means it already existed."""
        if template_id not in self._template_ids:
            raise LearnerStatePersistenceError("reviewed template exposure is unknown.")
        return self._repository.claim_reviewed_template_exposure(
            learner_id=learner_id, template_id=template_id, reason=reason
        )


def _validate_summary_templates(summary: Any, valid_template_ids: set[str]) -> None:
    if not isinstance(summary, dict):
        raise LearnerStatePersistenceError("diagnostic_summary must be an object.")
    if summary.get("purpose") != "mastery_verification" or summary.get("evidence_eligible") is not True:
        raise LearnerStatePersistenceError("diagnostic_summary is not accepted reviewed evidence.")
    if summary.get("status") != "completed":
        raise LearnerStatePersistenceError("diagnostic_summary must be completed.")
    steps = summary.get("step_results")
    if not isinstance(steps, list):
        raise LearnerStatePersistenceError("diagnostic_summary.step_results is invalid.")
    for step in steps:
        if not isinstance(step, dict) or step.get("question_id") not in valid_template_ids:
            raise LearnerStatePersistenceError("diagnostic_summary references an unknown template.")
