from copy import deepcopy

import pytest

from introai_tutor.dual_track_diagnostics import (
    DualTrackDiagnosticError,
    DualTrackDiagnosticWorkflowService,
    _formative_view,
)


class _Formative:
    def start(self, **_kwargs):
        return {"status": "in_progress", "session": {"f": 0}, "question": {"id": "q1"}, "evaluation": None}

    def submit(self, *, session, answer):
        assert session == {"f": 0}
        assert answer == "answer"
        return {"status": "completed", "session": {"f": 1}, "question": None,
                "evaluation": {"passed": True, "matched_labels": ["BFS"], "misconception_ids": [], "feedback": ["good"], "needs_clarification": False, "clarifying_question": None},
                "summary": {"concept_observations": {"breadth_first_search": [1.0]}}}

    def skip_current(self, *, session):
        assert session == {"f": 0}
        return {"status": "completed", "session": {"f": 2}, "question": None,
                "evaluation": None, "summary": {"concept_observations": {}}}


class _Selector:
    def select(self, *, concept_ids, intent):
        assert concept_ids == ["breadth_first_search"] and intent == "diagnostic_request"
        return [{"id": "verify_one"}]


class _Verification:
    def start(self, *, template_ids):
        assert template_ids == ["verify_one"]
        return {"status": "in_progress", "session": {"v": 0, "current_template_id": "verify_one"}}

    def submit(self, *, session, answer, submitted_template_id):
        assert session == {"v": 0, "current_template_id": "verify_one"} and answer == "A" and submitted_template_id == "verify_one"
        return {"status": "completed", "session": {"v": 1}, "summary": {"evidence_eligible": True}}

    def current_question(self, *, session):
        assert session == {"v": 0, "current_template_id": "verify_one"}
        return {"template_id": "verify_one", "prompt": "question", "choices": []}

    def choose_hint_retry(self, **_kwargs):
        return {"status": "in_progress", "session": {"v": 0, "current_template_id": "verify_one"}}

    def request_reveal(self, **_kwargs):
        return {"status": "in_progress", "session": {"v": 0, "current_template_id": "verify_one"}}

    def acknowledge_reveal(self, **_kwargs):
        return {"status": "completed", "session": {"v": 1}, "summary": {"evidence_eligible": True}}

    def current_reveal(self, **_kwargs):
        return {"template_id": "verify_one"}


class _StructuredAnswerVerification(_Verification):
    def submit(self, *, session, answer, submitted_template_id):
        assert session == {"v": 0, "current_template_id": "verify_one"}
        assert answer == ["A", "C"]
        assert submitted_template_id == "verify_one"
        return {
            "status": "completed",
            "session": {"v": 1},
            "summary": {"evidence_eligible": True},
        }


class _Integration:
    def __init__(self): self.calls = []
    def apply(self, *, learner_state, diagnostic_summary):
        self.calls.append((deepcopy(learner_state), deepcopy(diagnostic_summary)))
        return {"learner_state": {"updated": True}, "recommendation": {"concept_id": "uniform_cost_search"}}


class _NoTemplates:
    def select(self, **_kwargs):
        return []


def test_formative_cannot_integrate_state_but_completed_verification_can():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(), template_selection_service=_Selector(),
        verification_service=_Verification(), state_integration_service=integration,
    )
    formative_done = workflow.submit_formative(session=workflow.start()["session"], answer="answer")

    assert formative_done["purpose"] == "formative"
    assert formative_done["evidence_eligible"] is False
    assert formative_done["formative_completed"] is True
    assert formative_done["state_update"] is None
    assert integration.calls == []

    verification = workflow.start_verification(session=formative_done["session"], concept_ids=["breadth_first_search"])
    completed = workflow.submit_verification(
        session=verification["session"], answer="A", submitted_template_id="verify_one",
        learner_state={"mastery": {}},
    )
    assert completed["purpose"] == "mastery_verification"
    assert completed["evidence_eligible"] is True
    assert completed["state_update"]["learner_state"] == {"updated": True}
    assert len(integration.calls) == 1
    with pytest.raises(DualTrackDiagnosticError, match="verification"):
        workflow.submit_verification(
            session=completed["session"], answer="A", submitted_template_id="verify_one",
            learner_state={}
        )
    assert len(integration.calls) == 1


def test_no_reviewed_template_becomes_safe_formative_only_unavailable_state():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(), template_selection_service=_NoTemplates(),
        verification_service=_Verification(), state_integration_service=integration,
    )
    formative_done = workflow.submit_formative(session=workflow.start()["session"], answer="answer")
    unavailable = workflow.start_verification(
        session=formative_done["session"], concept_ids=["breadth_first_search"]
    )

    assert unavailable["phase"] == "verification_unavailable"
    assert unavailable["verification_available"] is False
    assert unavailable["purpose"] == "formative"
    assert unavailable["evidence_eligible"] is False
    assert unavailable["state_update"] is None
    assert unavailable["recommendation"] is None
    assert integration.calls == []
    try:
        workflow.submit_verification(
            session=unavailable["session"], answer="A", submitted_template_id="verify_one",
            learner_state={}
        )
    except ValueError as error:
        assert "verification" in str(error)
    else:  # pragma: no cover - safety assertion
        raise AssertionError("verification_unavailable must not accept an answer")


def test_quick_verification_bypasses_formative_and_uses_reviewed_templates():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(), template_selection_service=_Selector(),
        verification_service=_Verification(), state_integration_service=integration,
    )

    result = workflow.start_quick_verification(concept_ids=["breadth_first_search"])

    assert result["phase"] == "verification"
    assert result["purpose"] == "mastery_verification"
    assert result["session"]["track_id"] == "quick_verification"
    assert result["session"]["formative_session"] == {}
    assert integration.calls == []


def test_verification_workflow_passes_structured_answer_to_injected_service():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(),
        template_selection_service=_Selector(),
        verification_service=_StructuredAnswerVerification(),
        state_integration_service=integration,
    )
    started = workflow.start_quick_verification(
        concept_ids=["breadth_first_search"]
    )
    answer = ["A", "C"]
    original = deepcopy(answer)

    completed = workflow.submit_verification(
        session=started["session"],
        answer=answer,
        submitted_template_id="verify_one",
        learner_state={"mastery": {}},
    )

    assert completed["phase"] == "completed"
    assert answer == original
    assert len(integration.calls) == 1


def test_current_verification_question_is_rebuilt_from_session_not_cached_result():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(), template_selection_service=_Selector(),
        verification_service=_Verification(), state_integration_service=integration,
    )
    verification = workflow.start_quick_verification(
        concept_ids=["breadth_first_search"]
    )
    # A caller may retain an obsolete result bundle, but rendering must ask the
    # service for the session's template bundle instead of using that cache.
    stale = deepcopy(verification)
    stale["verification"]["question"] = {"template_id": "stale", "prompt": "stale"}

    current = workflow.current_verification_question(session=stale["session"])

    assert current["template_id"] == "verify_one"
    assert current["prompt"] == "question"


def test_completed_reveal_acknowledgement_integrates_exactly_once():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(), template_selection_service=_Selector(),
        verification_service=_Verification(), state_integration_service=integration,
    )
    verification = workflow.start_quick_verification(
        concept_ids=["breadth_first_search"]
    )

    completed = workflow.acknowledge_verification_reveal(
        session=verification["session"], template_id="verify_one", learner_state={"mastery": {}}
    )

    assert completed["phase"] == "completed"
    assert len(integration.calls) == 1
    with pytest.raises(DualTrackDiagnosticError, match="verification"):
        workflow.acknowledge_verification_reveal(
            session=completed["session"], template_id="verify_one", learner_state={}
        )
    assert len(integration.calls) == 1


def test_continue_formative_is_evidence_ineligible_and_reaches_verification_ready():
    integration = _Integration()
    workflow = DualTrackDiagnosticWorkflowService(
        formative_service=_Formative(), template_selection_service=_Selector(),
        verification_service=_Verification(), state_integration_service=integration,
    )

    result = workflow.continue_formative(session=workflow.start()["session"])

    assert result["phase"] == "verification_ready"
    assert result["purpose"] == "formative"
    assert result["evidence_eligible"] is False
    assert result["state_update"] is None
    assert integration.calls == []


def test_rejected_semantic_feedback_is_projected_as_nonblocking_unavailable():
    view = _formative_view(
        {"id": "q1"},
        {
            "passed": False,
            "matched_labels": [],
            "misconception_ids": [],
            "feedback": [],
            "misconception_feedback": [],
            "needs_clarification": False,
            "clarifying_question": None,
            "semantic_status": "rejected",
        },
    )

    assert view["formative_status"] == "unclear"
    assert view["feedback_unavailable"] is True
