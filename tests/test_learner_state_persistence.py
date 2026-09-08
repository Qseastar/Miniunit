from copy import deepcopy
from pathlib import Path

import pytest

import app as streamlit_app

from introai_tutor.app_services import (
    build_dual_track_diagnostic_workflow,
    build_learner_state_persistence_service,
    load_initial_learner_state,
)
from introai_tutor.learner_state_repository import LearnerStatePersistenceError


ROOT = Path(__file__).resolve().parents[1]
LEARNER = "4ed2149c-6dd3-4a23-9c4d-94ea4edb63fd"


def _completed_summary():
    workflow = build_dual_track_diagnostic_workflow(root=ROOT)
    started = workflow.start_quick_verification(
        concept_ids=["uniform_cost_search"], intent="definition",
        template_ids=["verify_ucs_min_g_choice_v1"],
    )
    result = workflow.submit_verification(
        session=started["session"], answer="A", submitted_template_id="verify_ucs_min_g_choice_v1",
        learner_state=load_initial_learner_state(ROOT),
    )
    return result["state_update"]["learner_state"], result["verification"]["summary"]


def test_real_domain_state_round_trips_without_copying_mastery_formula(tmp_path):
    service = build_learner_state_persistence_service(root=ROOT, db_path=tmp_path / "state.sqlite3")
    state, summary = _completed_summary()
    service.save_completed(learner_id=LEARNER, learner_state=state, diagnostic_summary=summary, event_id="event-1")
    restored = service.restore(learner_id=LEARNER, empty_state=load_initial_learner_state(ROOT))
    assert restored["learner_state"]["mastery"] == state["mastery"]
    assert restored["learner_state"]["learning_evidence"]
    assert restored["learner_state"]["learning_evidence"][0]["template_outcomes"] == [
        {
            "template_id": "verify_ucs_min_g_choice_v1",
            "status": "passed",
            "final_attempt_assistance_level": "none",
        }
    ]
    assert restored["completed_summaries"]


def test_unknown_template_and_non_evidence_summary_fail_before_save(tmp_path):
    service = build_learner_state_persistence_service(root=ROOT, db_path=tmp_path / "state.sqlite3")
    state, summary = _completed_summary()
    bad = deepcopy(summary)
    bad["step_results"][0]["question_id"] = "unknown_template"
    with pytest.raises(LearnerStatePersistenceError, match="unknown template"):
        service.save_completed(learner_id=LEARNER, learner_state=state, diagnostic_summary=bad, event_id="event-1")
    assert service.repository.profile_exists(LEARNER) is False


class _SessionSt:
    def __init__(self, *, query, db_path):
        self.query_params = query
        self.session_state = {"introai_state_db_path": db_path}


def test_new_session_restores_profile_but_not_diagnostic_transient_state(tmp_path):
    path = tmp_path / "state.sqlite3"
    query = {"learner": LEARNER}
    first = _SessionSt(query=query, db_path=path)
    streamlit_app._ensure_learner_state(first)
    state, summary = _completed_summary()
    first.session_state["introai_learner_state"] = state
    first.session_state["introai_dual_track_result"] = {"phase": "verification"}
    service = first.session_state["introai_learner_state_persistence_service"]
    service.save_completed(
        learner_id=LEARNER, learner_state=state, diagnostic_summary=summary, event_id="event-1"
    )

    second = _SessionSt(query=query, db_path=path)
    streamlit_app._ensure_learner_state(second)
    assert second.session_state["introai_learner_state"]["mastery"] == state["mastery"]
    assert second.session_state["introai_completed_verification_summaries"]
    assert "introai_dual_track_result" not in second.session_state

    second.session_state["introai_learner_state_persistence_service"].clear(learner_id=LEARNER)
    third = _SessionSt(query=query, db_path=path)
    streamlit_app._ensure_learner_state(third)
    assert third.session_state["introai_learner_state"]["mastery"] == {}
