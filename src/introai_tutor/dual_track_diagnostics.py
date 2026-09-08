"""Application workflow separating formative dialogue from mastery evidence."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


FORMATIVE_STATUS_LABELS = {
    "understood": "已理解",
    "partially_understood": "部分理解",
    "unclear": "需要澄清",
    "likely_misconception": "可能存在误解",
}


class DualTrackDiagnosticError(ValueError):
    """Raised when a dual-track diagnostic request violates its workflow."""


class DualTrackDiagnosticWorkflowService:
    """Keep open formative work structurally incapable of updating mastery."""

    def __init__(
        self,
        *,
        formative_service: Any | None,
        template_selection_service: Any,
        verification_service: Any,
        state_integration_service: Any,
        exposure_policy: Any | None = None,
        template_concept_ids: dict[str, list[str]] | None = None,
    ) -> None:
        if formative_service is not None:
            _require_methods(formative_service, ("start", "submit", "skip_current"), "formative_service")
        _require_methods(template_selection_service, ("select",), "template_selection_service")
        _require_methods(
            verification_service,
            (
                "start", "submit", "current_question", "choose_hint_retry",
                "request_reveal", "acknowledge_reveal", "current_reveal",
            ),
            "verification_service",
        )
        _require_methods(state_integration_service, ("apply",), "state_integration_service")
        if exposure_policy is not None:
            _require_methods(exposure_policy, ("classify", "claim"), "exposure_policy")
        if template_concept_ids is not None:
            if not isinstance(template_concept_ids, dict) or not all(
                isinstance(template_id, str)
                and isinstance(concept_ids, list)
                and concept_ids
                and all(isinstance(concept_id, str) and concept_id for concept_id in concept_ids)
                for template_id, concept_ids in template_concept_ids.items()
            ):
                raise DualTrackDiagnosticError("template_concept_ids is invalid.")
        self._formative_service = formative_service
        self._selector = template_selection_service
        self._verification_service = verification_service
        self._state_integration_service = state_integration_service
        self._exposure_policy = exposure_policy
        self._template_concept_ids = deepcopy(template_concept_ids or {})

    def start(self, *, track_id: str = "bfs_equal_cost_ucs", variant_round: int = 0) -> dict[str, Any]:
        if self._formative_service is None:
            raise DualTrackDiagnosticError("This module has no configured formative diagnostic track.")
        _non_empty(track_id, "track_id")
        if isinstance(variant_round, bool) or not isinstance(variant_round, int) or variant_round < 0:
            raise DualTrackDiagnosticError("variant_round must be a non-negative integer.")
        raw = self._formative_service.start(track_id=track_id, variant_round=variant_round)
        _result_dict(raw, "formative_service.start")
        raw_session = raw.get("session")
        if not isinstance(raw_session, dict):
            raise DualTrackDiagnosticError("formative_service.start must return a session dict.")
        return self._formative_result(raw=raw, session={"phase": "formative", "formative_session": deepcopy(raw_session), "track_id": track_id})

    def submit_formative(self, *, session: dict[str, Any], answer: str) -> dict[str, Any]:
        if self._formative_service is None:
            raise DualTrackDiagnosticError("This module has no configured formative diagnostic track.")
        if not isinstance(answer, str) or not answer.strip():
            raise DualTrackDiagnosticError("answer must be a non-empty string.")
        state = self._validate_dual_session(session, expected_phase="formative")
        raw = self._formative_service.submit(session=deepcopy(state["formative_session"]), answer=answer)
        _result_dict(raw, "formative_service.submit")
        raw_session = raw.get("session")
        if not isinstance(raw_session, dict):
            raise DualTrackDiagnosticError("formative_service.submit must return a session dict.")
        if raw.get("status") == "completed":
            return self._formative_result(
                raw=raw,
                session={
                    "phase": "verification_ready",
                    "formative_session": deepcopy(raw_session),
                    "track_id": state["track_id"],
                },
                formative_completed=True,
            )
        return self._formative_result(
            raw=raw,
            session={"phase": "formative", "formative_session": deepcopy(raw_session), "track_id": state["track_id"]},
        )

    def continue_formative(self, *, session: dict[str, Any]) -> dict[str, Any]:
        """Skip one optional formative prompt without creating evidence."""
        if self._formative_service is None:
            raise DualTrackDiagnosticError("This module has no configured formative diagnostic track.")
        state = self._validate_dual_session(session, expected_phase="formative")
        raw = self._formative_service.skip_current(
            session=deepcopy(state["formative_session"])
        )
        _result_dict(raw, "formative_service.skip_current")
        raw_session = raw.get("session")
        if not isinstance(raw_session, dict):
            raise DualTrackDiagnosticError(
                "formative_service.skip_current must return a session dict."
            )
        if raw.get("status") == "completed":
            return self._formative_result(
                raw=raw,
                session={
                    "phase": "verification_ready",
                    "formative_session": deepcopy(raw_session),
                    "track_id": state["track_id"],
                },
                formative_completed=True,
            )
        return self._formative_result(
            raw=raw,
            session={
                "phase": "formative",
                "formative_session": deepcopy(raw_session),
                "track_id": state["track_id"],
            },
        )

    def start_quick_verification(
        self,
        *,
        concept_ids: list[str],
        intent: str = "diagnostic_request",
        template_ids: list[str] | None = None,
        learner_id: str | None = None,
    ) -> dict[str, Any]:
        """Start reviewed verification directly, without open formative work.

        ``template_ids`` may only narrow the reviewed templates selected for
        the given concepts and intent.  It is deliberately revalidated here:
        a UI/session value cannot inject unrelated or unreviewed templates.
        """
        return self._start_selected_verification(
            formative_session={},
            track_id="quick_verification",
            concept_ids=concept_ids,
            intent=intent,
            template_ids=template_ids,
            learner_id=learner_id,
        )

    def start_verification(
        self,
        *,
        session: dict[str, Any],
        concept_ids: list[str],
        intent: str = "diagnostic_request",
        learner_id: str | None = None,
    ) -> dict[str, Any]:
        state = self._validate_dual_session(session, expected_phase="verification_ready")
        return self._start_selected_verification(
            formative_session=state["formative_session"],
            track_id=state["track_id"],
            concept_ids=concept_ids,
            intent=intent,
            template_ids=None,
            learner_id=learner_id,
        )

    def _start_selected_verification(
        self,
        *,
        formative_session: dict[str, Any],
        track_id: str,
        concept_ids: list[str],
        intent: str,
        template_ids: list[str] | None,
        learner_id: str | None,
    ) -> dict[str, Any]:
        selected = self._selector.select(concept_ids=deepcopy(concept_ids), intent=intent)
        if not isinstance(selected, list):
            raise DualTrackDiagnosticError("template_selection_service must return a list.")
        if not selected:
            return {
                "phase": "verification_unavailable",
                "verification_available": False,
                "purpose": "formative",
                "evidence_eligible": False,
                "formative_completed": True,
                "formative": None,
                "verification": None,
                "session": {
                    "phase": "verification_unavailable",
                    "formative_session": deepcopy(formative_session),
                    "track_id": track_id,
                },
                "state_update": None,
                "recommendation": None,
                "message": "当前没有可用的掌握度验证题，本次结果仅作为学习反馈。",
            }
        selected_ids = [item.get("id") for item in selected]
        if not all(isinstance(item, str) and item for item in selected_ids):
            raise DualTrackDiagnosticError("template_selection_service returned invalid templates.")
        if template_ids is None:
            selected_mode_data = self._classify_template_modes(
                learner_id=learner_id, template_ids=selected_ids
            )
            verified_template_ids = sorted(
                selected_ids,
                key=lambda template_id: (
                    selected_mode_data["modes"][template_id] == "practice_only",
                    selected_ids.index(template_id),
                ),
            )
            mode_data = {
                "modes": {
                    template_id: selected_mode_data["modes"][template_id]
                    for template_id in verified_template_ids
                },
                "exposed_before": {
                    template_id: selected_mode_data["exposed_before"][template_id]
                    for template_id in verified_template_ids
                },
                "persistence_degraded": selected_mode_data["persistence_degraded"],
            }
        else:
            verified_template_ids = _validate_planned_template_ids(
                template_ids=template_ids, selectable_template_ids=selected_ids
            )
            mode_data = self._classify_template_modes(
                learner_id=learner_id, template_ids=verified_template_ids
            )
        raw = self._verification_service.start(template_ids=verified_template_ids)
        _result_dict(raw, "verification_service.start")
        verification_session = raw.get("session")
        if not isinstance(verification_session, dict):
            raise DualTrackDiagnosticError("verification_service.start must return a session dict.")
        return {
            "phase": "verification",
            "verification_available": True,
            "purpose": "mastery_verification",
            "evidence_eligible": True,
            "formative_completed": True,
            "formative": None,
            "verification": deepcopy(raw),
            "session": {
                "phase": "verification",
                "formative_session": deepcopy(formative_session),
                "verification_session": deepcopy(verification_session),
                "track_id": track_id,
                **self._start_policy_session_fields(
                    mode_data=mode_data, learner_id=learner_id
                ),
            },
            "state_update": None,
            **_eligibility_fields(mode_data),
        }

    def submit_verification(
        self,
        *,
        session: dict[str, Any],
        answer: Any,
        submitted_template_id: str,
        learner_state: dict[str, Any],
        learner_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(learner_state, dict):
            raise DualTrackDiagnosticError("learner_state must be a dict.")
        state = self._validate_dual_session(session, expected_phase="verification")
        self._claim_current_template(
            state=state,
            template_id=submitted_template_id,
            learner_id=learner_id,
            reason="formal_answer_submitted",
        )
        raw = self._verification_service.submit(
            session=deepcopy(state["verification_session"]),
            answer=answer,
            submitted_template_id=submitted_template_id,
        )
        _result_dict(raw, "verification_service.submit")
        verification_session = raw.get("session")
        if not isinstance(verification_session, dict):
            raise DualTrackDiagnosticError("verification_service.submit must return a session dict.")
        if raw.get("status") != "completed":
            return {
                "phase": "verification",
                "verification_available": True,
                "purpose": "mastery_verification",
                "evidence_eligible": True,
                "formative_completed": True,
                "formative": None,
                "verification": deepcopy(raw),
                "session": {
                    "phase": "verification",
                    "formative_session": deepcopy(state["formative_session"]),
                    "verification_session": deepcopy(verification_session),
                    "track_id": state["track_id"],
                    **_verification_policy_session_fields(state),
                },
                "state_update": None,
                **_eligibility_fields(_mode_data_from_state(state)),
            }
        summary = raw.get("summary")
        if not isinstance(summary, dict):
            raise DualTrackDiagnosticError("Completed verification must provide a summary.")
        if summary.get("evidence_eligible") is not True:
            raise DualTrackDiagnosticError("Only evidence-eligible verification may update learner state.")
        formal_summary = self._formal_summary(summary=summary, state=state)
        state_update = None
        if formal_summary is not None:
            state_update = self._state_integration_service.apply(
                learner_state=deepcopy(learner_state), diagnostic_summary=deepcopy(formal_summary)
            )
        result = {
            "phase": "completed",
            "verification_available": True,
            "purpose": "mastery_verification",
            "evidence_eligible": formal_summary is not None,
            "formative_completed": True,
            "formative": None,
            "verification": deepcopy(raw),
            "session": {
                "phase": "completed",
                "formative_session": deepcopy(state["formative_session"]),
                "verification_session": deepcopy(verification_session),
                "track_id": state["track_id"],
                **_verification_policy_session_fields(state),
            },
            "state_update": deepcopy(state_update),
            "formal_evidence_summary": deepcopy(formal_summary),
            "recommendation": (
                deepcopy(state_update.get("recommendation"))
                if isinstance(state_update, dict) else None
            ),
            **_eligibility_fields(_mode_data_from_state(state)),
        }
        return result

    def choose_verification_hint_retry(
        self, *, session: dict[str, Any], template_id: str, learner_id: str | None = None
    ) -> dict[str, Any]:
        state = self._validate_dual_session(session, expected_phase="verification")
        self._claim_current_template(
            state=state, template_id=template_id, learner_id=learner_id, reason="hint_used"
        )
        raw = self._verification_service.choose_hint_retry(
            session=deepcopy(state["verification_session"]), template_id=template_id
        )
        return self._verification_in_progress_result(state, raw, "choose_hint_retry")

    def request_verification_reveal(
        self, *, session: dict[str, Any], template_id: str, learner_id: str | None = None
    ) -> dict[str, Any]:
        state = self._validate_dual_session(session, expected_phase="verification")
        self._claim_current_template(
            state=state, template_id=template_id, learner_id=learner_id, reason="answer_revealed"
        )
        raw = self._verification_service.request_reveal(
            session=deepcopy(state["verification_session"]), template_id=template_id
        )
        return self._verification_in_progress_result(state, raw, "request_reveal")

    def acknowledge_verification_reveal(
        self, *, session: dict[str, Any], template_id: str, learner_state: dict[str, Any], learner_id: str | None = None
    ) -> dict[str, Any]:
        if not isinstance(learner_state, dict):
            raise DualTrackDiagnosticError("learner_state must be a dict.")
        state = self._validate_dual_session(session, expected_phase="verification")
        raw = self._verification_service.acknowledge_reveal(
            session=deepcopy(state["verification_session"]), template_id=template_id
        )
        _result_dict(raw, "verification_service.acknowledge_reveal")
        verification_session = raw.get("session")
        if not isinstance(verification_session, dict):
            raise DualTrackDiagnosticError(
                "verification_service.acknowledge_reveal must return a session dict."
            )
        if raw.get("status") != "completed":
            return self._verification_in_progress_result(
                state, raw, "acknowledge_reveal"
            )
        summary = raw.get("summary")
        if not isinstance(summary, dict) or summary.get("evidence_eligible") is not True:
            raise DualTrackDiagnosticError(
                "Completed verification reveal must provide evidence-eligible summary."
            )
        formal_summary = self._formal_summary(summary=summary, state=state)
        state_update = None
        if formal_summary is not None:
            state_update = self._state_integration_service.apply(
                learner_state=deepcopy(learner_state), diagnostic_summary=deepcopy(formal_summary)
            )
        return {
            "phase": "completed", "verification_available": True,
            "purpose": "mastery_verification", "evidence_eligible": formal_summary is not None,
            "formative_completed": True, "formative": None,
            "verification": deepcopy(raw),
            "session": {
                "phase": "completed",
                "formative_session": deepcopy(state["formative_session"]),
                "verification_session": deepcopy(verification_session),
                "track_id": state["track_id"],
                **_verification_policy_session_fields(state),
            },
            "state_update": deepcopy(state_update),
            "formal_evidence_summary": deepcopy(formal_summary),
            "recommendation": (
                deepcopy(state_update.get("recommendation"))
                if isinstance(state_update, dict) else None
            ),
            **_eligibility_fields(_mode_data_from_state(state)),
        }

    def current_verification_question(self, *, session: dict[str, Any]) -> dict[str, Any]:
        """Rebuild the complete current question from the authoritative session."""
        state = self._validate_dual_session(session, expected_phase="verification")
        question = self._verification_service.current_question(
            session=deepcopy(state["verification_session"])
        )
        if not isinstance(question, dict):
            raise DualTrackDiagnosticError(
                "verification_service.current_question must return a dict."
            )
        current_template_id = state["verification_session"].get("current_template_id")
        if question.get("template_id") != current_template_id:
            raise DualTrackDiagnosticError(
                "verification question does not match the current session template."
            )
        return deepcopy(question)

    def current_verification_reveal(self, *, session: dict[str, Any]) -> dict[str, Any]:
        state = self._validate_dual_session(session, expected_phase="verification")
        reveal = self._verification_service.current_reveal(
            session=deepcopy(state["verification_session"])
        )
        if not isinstance(reveal, dict) or reveal.get("template_id") != state[
            "verification_session"
        ].get("current_template_id"):
            raise DualTrackDiagnosticError("verification reveal does not match current session template.")
        return deepcopy(reveal)

    def _verification_in_progress_result(
        self, state: dict[str, Any], raw: Any, action: str
    ) -> dict[str, Any]:
        _result_dict(raw, f"verification_service.{action}")
        verification_session = raw.get("session")
        if not isinstance(verification_session, dict) or raw.get("status") != "in_progress":
            raise DualTrackDiagnosticError(
                f"verification_service.{action} must return an in-progress session."
            )
        return {
            "phase": "verification", "verification_available": True,
            "purpose": "mastery_verification", "evidence_eligible": True,
            "formative_completed": True, "formative": None,
            "verification": deepcopy(raw),
            "session": {
                "phase": "verification",
                "formative_session": deepcopy(state["formative_session"]),
                "verification_session": deepcopy(verification_session),
                "track_id": state["track_id"],
                **_verification_policy_session_fields(state),
            },
            "state_update": None,
            **_eligibility_fields(_mode_data_from_state(state)),
        }

    def _classify_template_modes(
        self, *, learner_id: str | None, template_ids: list[str]
    ) -> dict[str, Any]:
        if self._exposure_policy is None or learner_id is None:
            return {
                "modes": {template_id: "formal" for template_id in template_ids},
                "exposed_before": {template_id: False for template_id in template_ids},
                "persistence_degraded": False,
            }
        raw = self._exposure_policy.classify(
            learner_id=learner_id, template_ids=deepcopy(template_ids)
        )
        if not isinstance(raw, dict) or not isinstance(raw.get("template_decisions"), list):
            raise DualTrackDiagnosticError("exposure_policy.classify returned invalid data.")
        decisions = raw["template_decisions"]
        if [item.get("template_id") for item in decisions if isinstance(item, dict)] != template_ids:
            raise DualTrackDiagnosticError("exposure_policy decisions do not match selected templates.")
        modes: dict[str, str] = {}
        exposed_before: dict[str, bool] = {}
        for decision in decisions:
            if not isinstance(decision, dict):
                raise DualTrackDiagnosticError("exposure_policy returned an invalid decision.")
            template_id = decision["template_id"]
            mode = decision.get("attempt_mode")
            exposed = decision.get("template_exposed_before_attempt")
            if mode not in {"formal", "practice_only"} or not isinstance(exposed, bool):
                raise DualTrackDiagnosticError("exposure_policy returned an invalid template mode.")
            modes[template_id] = mode
            exposed_before[template_id] = exposed
        if not isinstance(raw.get("persistence_degraded"), bool):
            raise DualTrackDiagnosticError("exposure_policy returned invalid persistence state.")
        return {
            "modes": modes,
            "exposed_before": exposed_before,
            "persistence_degraded": raw["persistence_degraded"],
        }

    def _start_policy_session_fields(
        self, *, mode_data: dict[str, Any], learner_id: str | None
    ) -> dict[str, Any]:
        if self._exposure_policy is None or learner_id is None:
            return {}
        return {
            "verification_template_modes": deepcopy(mode_data["modes"]),
            "learner_id": learner_id,
        }

    def _claim_current_template(
        self,
        *,
        state: dict[str, Any],
        template_id: str,
        learner_id: str | None,
        reason: str,
    ) -> None:
        modes = _mode_data_from_state(state)["modes"]
        if modes.get(template_id) != "formal" or self._exposure_policy is None:
            return
        stored_learner_id = state.get("learner_id")
        effective_learner_id = learner_id if learner_id is not None else stored_learner_id
        if effective_learner_id is None:
            return
        claimed = self._exposure_policy.claim(
            learner_id=effective_learner_id, template_id=template_id, reason=reason
        )
        if not isinstance(claimed, dict) or not isinstance(claimed.get("persistence_degraded"), bool):
            raise DualTrackDiagnosticError("exposure_policy.claim returned invalid data.")
        # A fresh session stays formal after its own first claim.  This keeps
        # first wrong → hint/retry within one measurement under existing P5B
        # assistance rules. A separately started session is classified again.

    def _formal_summary(
        self, *, summary: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any] | None:
        modes = _mode_data_from_state(state)["modes"]
        formal_template_ids = [
            template_id
            for template_id in _mode_data_from_state(state)["modes"]
            if modes.get(template_id) == "formal"
        ]
        if not formal_template_ids:
            return None
        return _formal_evidence_summary(
            summary=summary,
            formal_template_ids=formal_template_ids,
            template_concept_ids=self._template_concept_ids,
        )

    def _formative_result(
        self, *, raw: dict[str, Any], session: dict[str, Any], formative_completed: bool = False
    ) -> dict[str, Any]:
        evaluation = raw.get("evaluation")
        formative = _formative_view(raw.get("question"), evaluation)
        return {
            "phase": "verification_ready" if formative_completed else "formative",
            "purpose": "formative",
            "evidence_eligible": False,
            "formative_completed": formative_completed,
            "formative": formative,
            "verification": None,
            "session": deepcopy(session),
            "state_update": None,
        }

    def _validate_dual_session(self, session: Any, *, expected_phase: str) -> dict[str, Any]:
        if not isinstance(session, dict):
            raise DualTrackDiagnosticError("session must be a dict.")
        phase = session.get("phase")
        if phase != expected_phase:
            raise DualTrackDiagnosticError(f"session must be in {expected_phase} phase.")
        if not isinstance(session.get("formative_session"), dict):
            raise DualTrackDiagnosticError("session.formative_session must be a dict.")
        _non_empty(session.get("track_id"), "session.track_id")
        if expected_phase == "verification" and not isinstance(session.get("verification_session"), dict):
            raise DualTrackDiagnosticError("session.verification_session must be a dict.")
        allowed = {"phase", "formative_session", "track_id"}
        if expected_phase == "verification":
            allowed.add("verification_session")
            optional = {"verification_template_modes", "learner_id"}
            if not set(session).issubset(allowed | optional):
                raise DualTrackDiagnosticError("session has an invalid schema.")
            modes = session.get("verification_template_modes")
            if modes is not None:
                template_ids = session["verification_session"].get("template_ids")
                if (
                    not isinstance(template_ids, list)
                    or not isinstance(modes, dict)
                    or set(modes) != set(template_ids)
                    or not all(value in {"formal", "practice_only"} for value in modes.values())
                ):
                    raise DualTrackDiagnosticError("session has invalid verification template modes.")
            learner_id = session.get("learner_id")
            if learner_id is not None and (not isinstance(learner_id, str) or not learner_id.strip()):
                raise DualTrackDiagnosticError("session learner_id is invalid.")
            return deepcopy(session)
        if set(session) != allowed:
            raise DualTrackDiagnosticError("session has an invalid schema.")
        return deepcopy(session)


def _validate_planned_template_ids(
    *, template_ids: Any, selectable_template_ids: list[str]
) -> list[str]:
    """Accept only a non-empty, non-duplicated subset of reviewed selection."""
    if not isinstance(template_ids, list) or not template_ids:
        raise DualTrackDiagnosticError("template_ids must be a non-empty list.")
    if len(template_ids) != len(set(template_ids)):
        raise DualTrackDiagnosticError("template_ids must not contain duplicates.")
    verified: list[str] = []
    for template_id in template_ids:
        if not isinstance(template_id, str) or not template_id.strip():
            raise DualTrackDiagnosticError("template_ids must contain non-empty strings.")
        if template_id not in selectable_template_ids:
            raise DualTrackDiagnosticError(
                "template_ids must be reviewed templates selected for the requested concepts."
            )
        verified.append(template_id)
    return verified


def _formative_view(question: Any, evaluation: Any) -> dict[str, Any]:
    """Project existing deterministic/semantic result into student-safe formative data."""
    if not isinstance(evaluation, dict):
        return {
            "question": deepcopy(question),
            "formative_status": None,
            "formative_status_label": None,
            "formative_feedback": [],
            "clarifying_question": None,
            "feedback_unavailable": False,
        }
    if evaluation.get("misconception_ids"):
        status = "likely_misconception"
    elif evaluation.get("passed") is True:
        status = "understood"
    elif evaluation.get("needs_clarification") is True:
        status = "unclear"
    elif evaluation.get("matched_labels"):
        status = "partially_understood"
    else:
        status = "unclear"
    feedback = []
    for key in ("misconception_feedback", "feedback"):
        for item in evaluation.get(key, []):
            if isinstance(item, str) and item.strip() and item not in feedback:
                feedback.append(item)
    return {
        "question": deepcopy(question),
        "formative_status": status,
        "formative_status_label": FORMATIVE_STATUS_LABELS[status],
        "formative_feedback": feedback,
        "clarifying_question": evaluation.get("clarifying_question"),
        # The adapter/schema reason is intentionally not exposed to students.
        # It only tells the UI to show its stable fallback wording.
        "feedback_unavailable": evaluation.get("semantic_status") == "rejected",
    }


def _require_methods(service: Any, methods: tuple[str, ...], name: str) -> None:
    if not all(callable(getattr(service, method, None)) for method in methods):
        raise DualTrackDiagnosticError(f"{name} must provide callable " + ", ".join(methods) + " methods.")


def _result_dict(value: Any, source: str) -> None:
    if not isinstance(value, dict):
        raise DualTrackDiagnosticError(f"{source} must return a dict.")


def _non_empty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DualTrackDiagnosticError(f"{name} must be a non-empty string.")


def _verification_policy_session_fields(state: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if "verification_template_modes" in state:
        fields["verification_template_modes"] = deepcopy(
            state["verification_template_modes"]
        )
    if "learner_id" in state:
        fields["learner_id"] = state["learner_id"]
    return fields


def _mode_data_from_state(state: dict[str, Any]) -> dict[str, Any]:
    modes = state.get("verification_template_modes")
    if not isinstance(modes, dict):
        template_ids = state.get("verification_session", {}).get("template_ids", [])
        if not isinstance(template_ids, list):
            template_ids = []
        if not template_ids:
            current_template_id = state.get("verification_session", {}).get(
                "current_template_id"
            )
            if isinstance(current_template_id, str) and current_template_id:
                template_ids = [current_template_id]
        modes = {
            template_id: "formal"
            for template_id in template_ids
            if isinstance(template_id, str) and template_id
        }
    return {
        "modes": deepcopy(modes),
        "exposed_before": {
            template_id: mode == "practice_only" for template_id, mode in modes.items()
        },
        "persistence_degraded": False,
    }


def _eligibility_fields(mode_data: dict[str, Any]) -> dict[str, Any]:
    modes = mode_data.get("modes", {})
    if not isinstance(modes, dict) or not modes:
        return {
            "attempt_mode": "formal",
            "evidence_eligible": True,
            "mastery_eligible": True,
            "practice_only": False,
            "template_attempt_modes": {},
            "template_exposed_before_attempt": {},
            "eligibility_reason": "template_not_previously_exposed",
            "exposure_persistence_degraded": False,
        }
    formal = [template_id for template_id, mode in modes.items() if mode == "formal"]
    practice = [template_id for template_id, mode in modes.items() if mode == "practice_only"]
    if formal and practice:
        attempt_mode, reason = "mixed", "contains_previously_exposed_templates"
    elif practice:
        attempt_mode, reason = "practice_only", "all_templates_previously_exposed"
    else:
        attempt_mode, reason = "formal", "template_not_previously_exposed"
    return {
        "attempt_mode": attempt_mode,
        "evidence_eligible": bool(formal),
        "mastery_eligible": bool(formal),
        "practice_only": not formal,
        "template_attempt_modes": deepcopy(modes),
        "template_exposed_before_attempt": deepcopy(mode_data.get("exposed_before", {})),
        "eligibility_reason": reason,
        "exposure_persistence_degraded": bool(mode_data.get("persistence_degraded", False)),
    }


def _formal_evidence_summary(
    *,
    summary: dict[str, Any],
    formal_template_ids: list[str],
    template_concept_ids: dict[str, list[str]],
) -> dict[str, Any]:
    """Project one completed mixed session to its formal-template evidence.

    The original verification summary remains untouched for feedback/history.
    This independent copy is the only object allowed to cross into P5B.
    """
    if not isinstance(summary.get("step_results"), list):
        # Compatibility for small injected service fakes; real verification
        # summaries always have the rich shape below.
        return deepcopy(summary)
    formal_ids = set(formal_template_ids)
    step_results = [
        deepcopy(step)
        for step in summary["step_results"]
        if isinstance(step, dict) and step.get("question_id") in formal_ids
    ]
    if len(step_results) != len(formal_template_ids):
        raise DualTrackDiagnosticError("verification summary does not match formal templates.")
    records = [
        deepcopy(record)
        for record in summary.get("observation_records", [])
        if isinstance(record, dict) and record.get("template_id") in formal_ids
    ]
    observations: dict[str, list[float]] = {}
    assistance: dict[str, list[bool]] = {}
    levels: dict[str, list[str]] = {}
    sources: dict[str, list[str | None]] = {}
    misconceptions: list[str] = []
    for record in records:
        concept_ids = record.get("concept_ids")
        if not isinstance(concept_ids, list):
            raise DualTrackDiagnosticError("verification observation record has invalid concepts.")
        for concept_id in concept_ids:
            observations.setdefault(concept_id, []).append(record["score"])
            assistance.setdefault(concept_id, []).append(record["assisted"])
            levels.setdefault(concept_id, []).append(record["assistance_level"])
            sources.setdefault(concept_id, []).append(record["assistance_source"])
        for misconception_id in record.get("misconception_ids", []):
            if misconception_id not in misconceptions:
                misconceptions.append(misconception_id)
    unobserved: list[str] = []
    for template_id in formal_template_ids:
        for concept_id in template_concept_ids.get(template_id, []):
            if concept_id not in observations and concept_id not in unobserved:
                unobserved.append(concept_id)
    projected = {
        "status": "completed",
        "purpose": "mastery_verification",
        "evidence_eligible": True,
        "track_id": summary.get("track_id", "reviewed_template_verification"),
        "total_steps": len(step_results),
        "passed_steps": sum(step.get("status") == "passed" for step in step_results),
        "unresolved_steps": sum(step.get("status") == "unresolved" for step in step_results),
        "concept_observations": observations,
        "concept_observation_assistance": assistance,
        "concept_observation_assistance_levels": levels,
        "concept_observation_assistance_sources": sources,
        "unobserved_concept_ids": unobserved,
        "misconception_ids": misconceptions,
        "observation_records": records,
        "step_results": step_results,
    }
    if not observations:
        projected["no_observation_reason"] = "all_revealed"
    return projected
