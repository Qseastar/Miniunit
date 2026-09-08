"""Orchestrate a deterministic diagnostic session and its state update."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from introai_tutor.diagnostic_feedback import build_teaching_feedback


class DiagnosticWorkflowError(ValueError):
    """Raised when workflow dependencies or public inputs are invalid."""


class DiagnosticWorkflowService:
    """Run the legacy open diagnostic as formative-only feedback.

    Mastery evidence now belongs exclusively to reviewed verification templates.
    This class remains available for callers that need the existing open-ended
    session and teaching feedback, but it cannot cross the P5B boundary.
    """

    def __init__(self, *, diagnostic_service, state_integration_service) -> None:
        start = getattr(diagnostic_service, "start", None)
        submit = getattr(diagnostic_service, "submit", None)
        apply = getattr(state_integration_service, "apply", None)
        if not callable(start) or not callable(submit):
            raise DiagnosticWorkflowError(
                "diagnostic_service must provide callable start and submit methods."
            )
        if not callable(apply):
            raise DiagnosticWorkflowError(
                "state_integration_service must provide a callable apply method."
            )
        self._diagnostic_service = diagnostic_service
        self._state_integration_service = state_integration_service

    def start(
        self, *, track_id: str = "bfs_equal_cost_ucs", variant_round: int = 0
    ) -> dict[str, Any]:
        """Start one diagnostic session and defer state integration."""
        _validate_track_id(track_id)
        _validate_variant_round(variant_round)
        diagnostic_result = self._diagnostic_service.start(
            track_id=track_id, variant_round=variant_round
        )
        if not isinstance(diagnostic_result, dict):
            raise DiagnosticWorkflowError("diagnostic_service.start must return a dict.")
        return {
            "purpose": "formative",
            "evidence_eligible": False,
            "diagnostic": deepcopy(diagnostic_result),
            "state_update": None,
            "teaching_feedback": None,
        }

    def submit(
        self,
        *,
        session: dict,
        answer: str,
        learner_state: dict,
    ) -> dict[str, Any]:
        """Submit one answer and integrate state only after completion."""
        if not isinstance(session, dict):
            raise DiagnosticWorkflowError("session must be a dict.")
        if not isinstance(answer, str) or not answer.strip():
            raise DiagnosticWorkflowError("answer must be a non-empty string.")
        if not isinstance(learner_state, dict):
            raise DiagnosticWorkflowError("learner_state must be a dict.")

        # P5A receives a copy so even a faulty injected service cannot mutate
        # the caller's session. The workflow invokes it exactly once.
        diagnostic_result = self._diagnostic_service.submit(
            session=deepcopy(session),
            answer=answer,
        )
        if not isinstance(diagnostic_result, dict):
            raise DiagnosticWorkflowError("diagnostic_service.submit must return a dict.")

        diagnostic_for_return = deepcopy(diagnostic_result)
        teaching_feedback = self._build_teaching_feedback(
            diagnostic_result=diagnostic_result,
            learner_state=learner_state,
        )
        pending_assistance = _pending_assistance_from_feedback(
            teaching_feedback=teaching_feedback,
            evaluation=diagnostic_result.get("evaluation"),
        )
        if pending_assistance is not None:
            _mark_pending_assistance(diagnostic_for_return, pending_assistance)
        if diagnostic_result.get("status") != "completed":
            return {
                "purpose": "formative",
                "evidence_eligible": False,
                "diagnostic": diagnostic_for_return,
                "state_update": None,
                "teaching_feedback": teaching_feedback,
            }
        return {
            "purpose": "formative",
            "evidence_eligible": False,
            "diagnostic": diagnostic_for_return,
            "state_update": None,
            "teaching_feedback": teaching_feedback,
        }

    def current_question(self, *, session: dict) -> dict[str, Any]:
        """Recover the current question from authoritative diagnostic session state."""
        if not isinstance(session, dict):
            raise DiagnosticWorkflowError("session must be a dict.")
        getter = getattr(self._diagnostic_service, "current_question", None)
        if not callable(getter):
            raise DiagnosticWorkflowError(
                "diagnostic_service must provide a callable current_question method."
            )
        question = getter(session=deepcopy(session))
        if not isinstance(question, dict):
            raise DiagnosticWorkflowError(
                "diagnostic_service.current_question must return a dict."
            )
        return deepcopy(question)

    def _build_teaching_feedback(
        self, *, diagnostic_result: dict[str, Any], learner_state: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build retry guidance only when P5A supplied complete safe context."""
        evaluation = diagnostic_result.get("evaluation")
        if not isinstance(evaluation, dict) or evaluation.get("passed") is not False:
            return None
        required = {
            "question_id",
            "concept_ids",
            "score",
            "attempts_used",
            "max_attempts",
            "feedback",
        }
        if not required <= set(evaluation):
            # This preserves the original minimal dependency contract for
            # injected legacy/fake diagnostic services. The real P5A service
            # always provides this context.
            return None

        teaching_support = None
        resolver = getattr(self._diagnostic_service, "get_teaching_support", None)
        if callable(resolver):
            teaching_support = resolver(question_id=evaluation["question_id"])
        return build_teaching_feedback(
            score=evaluation["score"],
            concept_ids=evaluation["concept_ids"],
            learner_state=deepcopy(learner_state),
            attempts_used=evaluation["attempts_used"],
            max_attempts=evaluation["max_attempts"],
            assessment_feedback=evaluation["feedback"],
            teaching_support=teaching_support,
            needs_clarification=evaluation.get("needs_clarification", False),
            clarifying_question=evaluation.get("clarifying_question"),
        )


def _validate_track_id(track_id: Any) -> None:
    if not isinstance(track_id, str) or not track_id.strip():
        raise DiagnosticWorkflowError("track_id must be a non-empty string.")


def _validate_variant_round(variant_round: Any) -> None:
    if (
        isinstance(variant_round, bool)
        or not isinstance(variant_round, int)
        or variant_round < 0
    ):
        raise DiagnosticWorkflowError("variant_round must be a non-negative integer.")


def _pending_assistance_from_feedback(
    *, teaching_feedback: dict[str, Any] | None, evaluation: Any
) -> dict[str, str] | None:
    """Derive one bounded next-attempt provenance record from displayed help."""
    if teaching_feedback is None or not isinstance(evaluation, dict):
        return None
    if teaching_feedback.get("remaining_attempts") != 1 or evaluation.get("passed") is not False:
        return None
    mode = teaching_feedback.get("mode")
    if mode == "hint":
        return {"level": "hint", "source": "deterministic_feedback"}
    if mode == "scaffold":
        if evaluation.get("needs_clarification") is True:
            return {"level": "clarification", "source": "semantic_advisory"}
        return {"level": "scaffold", "source": "deterministic_feedback"}
    if (
        mode == "reveal"
        and isinstance(teaching_feedback.get("model_answer"), str)
        and teaching_feedback["model_answer"].strip()
        and isinstance(teaching_feedback.get("explanation"), str)
        and teaching_feedback["explanation"].strip()
    ):
        return {"level": "reveal", "source": "model_answer"}
    return None


def _mark_pending_assistance(
    diagnostic_result: dict[str, Any], pending_assistance: dict[str, str]
) -> None:
    """Mark only the next same-step retry; no help text enters the session."""
    if diagnostic_result.get("status") != "in_progress":
        raise DiagnosticWorkflowError(
            "A pending assistance retry must keep the diagnostic in progress."
        )
    session = diagnostic_result.get("session")
    if not isinstance(session, dict):
        raise DiagnosticWorkflowError("diagnostic result session must be a dict.")
    if "pending_assistance" in session or session.get("full_answer_revealed", False):
        raise DiagnosticWorkflowError("diagnostic result has an invalid pending assistance state.")
    if set(pending_assistance) != {"level", "source"}:
        raise DiagnosticWorkflowError("pending assistance has an invalid schema.")
    session["pending_assistance"] = deepcopy(pending_assistance)
