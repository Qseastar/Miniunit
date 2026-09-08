"""Offline P6 learner-state measurement invariants.

These tests intentionally exercise the production composition over temporary
SQLite files.  They do not assert that a mastery value is psychometrically
valid; they assert the currently documented evidence semantics.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import pytest

from introai_tutor.app_services import (
    build_learner_state_persistence_service,
    build_reviewed_template_exposure_policy,
    load_initial_learner_state,
)
from introai_tutor.learner_state_repository import LearnerStatePersistenceError
from introai_tutor.verification_diagnostics import VerificationDiagnosticError, VerificationDiagnosticService
from tools.audit_learner_state import (
    _correct_answer,
    _services,
    _template_rows,
    _wrong_answer,
    production_inventory,
    run_session,
)


ROOT = Path(__file__).resolve().parents[1]
LEARNER_A = "synthetic_p6_a"
LEARNER_B = "synthetic_p6_b"
BFS_A = "verify_bfs_frontier_choice_v1"
BFS_B = "verify_bfs_equal_cost_condition_v1"
UCS = "verify_ucs_min_g_choice_v1"


def test_p6_inventory_uses_current_production_registry():
    inventory = production_inventory(ROOT)
    assert inventory["production_template_count"] == 28
    assert inventory["active_candidate_count"] == 0
    assert inventory["blocked_slot_count"] == 1
    assert inventory["concept_count"] == 26


def test_independent_correct_is_formal_positive_evidence(tmp_path):
    _, snapshot = run_session(
        root=ROOT,
        database=tmp_path / "formal.sqlite3",
        learner_id=LEARNER_A,
        template_id=UCS,
        answer_sequence=[_correct_answer(_template_rows(ROOT)[UCS])],
        trajectory_id="formal-correct",
    )
    assert snapshot.formal_or_practice_only == "formal"
    assert snapshot.assistance_provenance == "none"
    assert snapshot.selected_signal == pytest.approx(1.0)
    assert snapshot.post_mastery == pytest.approx(0.35)
    assert snapshot.mastery_delta > 0


def test_incorrect_after_retry_is_formal_zero_signal_not_positive(tmp_path):
    template = _template_rows(ROOT)[BFS_A]
    _, snapshot = run_session(
        root=ROOT,
        database=tmp_path / "incorrect.sqlite3",
        learner_id=LEARNER_A,
        template_id=BFS_A,
        answer_sequence=[_wrong_answer(template), _wrong_answer(template)],
        assistance="hint",
        trajectory_id="incorrect-after-retry",
    )
    assert snapshot.response_correctness == "incorrect"
    assert snapshot.selected_signal == pytest.approx(0.0)
    assert snapshot.post_mastery == pytest.approx(0.0)
    assert snapshot.state_update_present is True


def test_same_template_repeat_is_practice_only_and_does_not_update(tmp_path):
    template = _template_rows(ROOT)[BFS_A]
    database = tmp_path / "repeat.sqlite3"
    first = run_session(
        root=ROOT, database=database, learner_id=LEARNER_A, template_id=BFS_A,
        answer_sequence=[_correct_answer(template)], trajectory_id="repeat", step_index=0,
    )[1]
    repeat = run_session(
        root=ROOT, database=database, learner_id=LEARNER_A, template_id=BFS_A,
        answer_sequence=[_correct_answer(template)], trajectory_id="repeat", step_index=1,
    )[1]
    assert first.formal_or_practice_only == "formal"
    assert repeat.formal_or_practice_only == "practice_only"
    assert repeat.state_update_present is False
    assert repeat.mastery_delta == 0
    assert repeat.post_mastery == first.post_mastery


def test_hint_and_reveal_never_turn_assistance_into_independent_signal(tmp_path):
    template = _template_rows(ROOT)[BFS_A]
    _, hint = run_session(
        root=ROOT, database=tmp_path / "hint.sqlite3", learner_id=LEARNER_A,
        template_id=BFS_A,
        answer_sequence=[_wrong_answer(template), _correct_answer(template)],
        assistance="hint", trajectory_id="hint",
    )
    _, reveal = run_session(
        root=ROOT, database=tmp_path / "reveal.sqlite3", learner_id=LEARNER_A,
        template_id=BFS_A, answer_sequence=[], assistance="reveal", trajectory_id="reveal",
    )
    assert hint.assistance_provenance == "hint"
    assert hint.selected_signal == pytest.approx(0.0)
    assert hint.post_mastery == pytest.approx(0.0)
    assert reveal.response_correctness == "revealed_without_answer"
    assert reveal.selected_signal is None
    assert reveal.post_mastery == pytest.approx(0.0)


def test_different_templates_same_concept_add_a_second_formal_observation(tmp_path):
    rows = _template_rows(ROOT)
    database = tmp_path / "different-templates.sqlite3"
    first = run_session(
        root=ROOT, database=database, learner_id=LEARNER_A, template_id=BFS_A,
        answer_sequence=[_correct_answer(rows[BFS_A])], trajectory_id="two", step_index=0,
    )[1]
    second = run_session(
        root=ROOT, database=database, learner_id=LEARNER_A, template_id=BFS_B,
        answer_sequence=[_correct_answer(rows[BFS_B])], trajectory_id="two", step_index=1,
    )[1]
    assert first.formal_evidence_count == 1
    assert second.formal_evidence_count == 2
    assert second.formal_or_practice_only == "formal"
    assert second.selected_signal == pytest.approx(1.0)
    assert second.post_mastery == pytest.approx(0.5775)


def test_order_is_sensitive_by_the_existing_last_unassisted_signal_policy(tmp_path):
    rows = _template_rows(ROOT)
    first_db = tmp_path / "correct-wrong.sqlite3"
    correct = run_session(
        root=ROOT, database=first_db, learner_id=LEARNER_A, template_id=BFS_A,
        answer_sequence=[_correct_answer(rows[BFS_A])], trajectory_id="order", step_index=0,
    )[1]
    correct_wrong = run_session(
        root=ROOT, database=first_db, learner_id=LEARNER_A, template_id=BFS_B,
        answer_sequence=[_wrong_answer(rows[BFS_B]), _wrong_answer(rows[BFS_B])],
        assistance="hint", trajectory_id="order", step_index=1,
    )[1]

    second_db = tmp_path / "wrong-correct.sqlite3"
    wrong = run_session(
        root=ROOT, database=second_db, learner_id=LEARNER_B, template_id=BFS_A,
        answer_sequence=[_wrong_answer(rows[BFS_A]), _wrong_answer(rows[BFS_A])],
        assistance="hint", trajectory_id="order", step_index=0,
    )[1]
    wrong_correct = run_session(
        root=ROOT, database=second_db, learner_id=LEARNER_B, template_id=BFS_B,
        answer_sequence=[_correct_answer(rows[BFS_B])], trajectory_id="order", step_index=1,
    )[1]
    assert correct.post_mastery == pytest.approx(0.35)
    assert correct_wrong.post_mastery == pytest.approx(0.2275)
    assert wrong.post_mastery == pytest.approx(0.0)
    assert wrong_correct.post_mastery == pytest.approx(0.35)
    # This is a formula consequence, not an implementation promise of order
    # invariance; it is retained as a P6b measurement question.
    assert correct_wrong.post_mastery != wrong_correct.post_mastery


def test_learner_isolation_and_reset_clear_formal_evidence_and_exposure(tmp_path):
    database = tmp_path / "isolation.sqlite3"
    template = _template_rows(ROOT)[UCS]
    run_session(
        root=ROOT, database=database, learner_id=LEARNER_A, template_id=UCS,
        answer_sequence=[_correct_answer(template)], trajectory_id="a",
    )
    persistence = build_learner_state_persistence_service(root=ROOT, db_path=database)
    before_b = persistence.restore(learner_id=LEARNER_B, empty_state=load_initial_learner_state(ROOT))
    assert before_b["learner_state"]["mastery"] == {}
    assert before_b["completed_summaries"] == []
    persistence.clear(learner_id=LEARNER_A)
    after_a = persistence.restore(learner_id=LEARNER_A, empty_state=load_initial_learner_state(ROOT))
    assert after_a["learner_state"]["mastery"] == {}
    assert after_a["learner_state"]["learning_evidence"] == []
    policy = build_reviewed_template_exposure_policy(root=ROOT, persistence_service=persistence)
    assert policy.classify(learner_id=LEARNER_A, template_ids=[UCS])["template_decisions"][0]["practice_only"] is False


def test_deterministic_replay_and_malformed_inputs_fail_closed(tmp_path):
    rows = _template_rows(ROOT)
    one = run_session(
        root=ROOT, database=tmp_path / "replay1.sqlite3", learner_id=LEARNER_A,
        template_id=UCS, answer_sequence=[_correct_answer(rows[UCS])], trajectory_id="replay",
    )[1]
    two = run_session(
        root=ROOT, database=tmp_path / "replay2.sqlite3", learner_id=LEARNER_B,
        template_id=UCS, answer_sequence=[_correct_answer(rows[UCS])], trajectory_id="replay",
    )[1]
    assert one == two

    _, workflow = _services(ROOT, tmp_path / "malformed.sqlite3")
    with pytest.raises(ValueError):
        workflow.start_quick_verification(
            concept_ids=["uniform_cost_search"], intent="definition",
            template_ids=["blocked_or_unknown_template"], learner_id=LEARNER_A,
        )
    started = workflow.start_quick_verification(
        concept_ids=["uniform_cost_search"], intent="definition",
        template_ids=[UCS], learner_id=LEARNER_A,
    )
    with pytest.raises(VerificationDiagnosticError):
        workflow.submit_verification(
            session=started["session"], answer="not-a-choice", submitted_template_id=UCS,
            learner_state=load_initial_learner_state(ROOT), learner_id=LEARNER_A,
        )
    assert started["session"]["verification_session"]["history"] == []

    # Unsupported scorer payloads are rejected at the real scorer service
    # boundary rather than silently producing evidence.
    malformed = deepcopy(rows[UCS])
    malformed["deterministic_scorer"] = "unsupported_scorer"
    with pytest.raises(VerificationDiagnosticError, match="Unsupported"):
        VerificationDiagnosticService(templates=[malformed])


def test_duplicate_event_id_same_payload_is_idempotent_conflict_fails_closed(tmp_path):
    rows = _template_rows(ROOT)
    database = tmp_path / "events.sqlite3"
    persistence, workflow = _services(ROOT, database)
    initial = load_initial_learner_state(ROOT)
    started = workflow.start_quick_verification(
        concept_ids=["uniform_cost_search"], intent="definition", template_ids=[UCS], learner_id=LEARNER_A,
    )
    completed = workflow.submit_verification(
        session=started["session"], answer=_correct_answer(rows[UCS]), submitted_template_id=UCS,
        learner_state=initial, learner_id=LEARNER_A,
    )
    state = completed["state_update"]["learner_state"]
    summary = completed["formal_evidence_summary"]
    assert persistence.save_completed(learner_id=LEARNER_A, learner_state=state, diagnostic_summary=summary, event_id="p6-event") is False
    assert persistence.save_completed(learner_id=LEARNER_A, learner_state=state, diagnostic_summary=summary, event_id="p6-event") is True
    changed = deepcopy(summary)
    changed["step_results"][0]["status"] = "unresolved"
    with pytest.raises(LearnerStatePersistenceError):
        persistence.save_completed(learner_id=LEARNER_A, learner_state=state, diagnostic_summary=changed, event_id="p6-event")


def test_formative_assistance_levels_are_not_verification_evidence():
    with pytest.raises(ValueError, match="formative-only"):
        run_session(
            root=ROOT, database=Path("/tmp/unused-p6.sqlite3"), learner_id=LEARNER_A,
            template_id=BFS_A, answer_sequence=["A"], assistance="scaffold",
            trajectory_id="formative-only",
        )
