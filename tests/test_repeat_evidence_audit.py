"""Real composition canaries for the reviewed-template repeat-evidence policy."""

from __future__ import annotations

from pathlib import Path
import json

import pytest

from introai_tutor.app_services import (
    build_diagnostic_handoff_service,
    build_dual_track_diagnostic_workflow,
    build_learner_state_persistence_service,
    build_reviewed_template_exposure_policy,
    load_initial_learner_state,
)


ROOT = Path(__file__).resolve().parents[1]
LEARNER_A = "11111111-1111-4111-8111-111111111111"
LEARNER_B = "22222222-2222-4222-8222-222222222222"
UCS_TEMPLATE = "verify_ucs_min_g_choice_v1"
P5B_TEMPLATE_IDS = (
    "verify_local_search_final_state_focus_v1",
    "verify_hill_climbing_stop_at_local_best_v1",
    "verify_simulated_annealing_worse_successor_v1",
    "verify_evolutionary_search_parent_cycle_v1",
    "verify_minimax_max_min_value_choice_v1",
    "verify_alpha_beta_prune_when_bounds_cross_v1",
    "verify_mcts_four_stage_order_v1",
    "verify_ucb_upper_bound_selection_v1",
)


def _production_template(template_id):
    templates = json.loads(
        (ROOT / "data" / "diagnostic_templates.json").read_text(encoding="utf-8")
    )["templates"]
    return next(item for item in templates if item["id"] == template_id)


def _correct_answer(template_id):
    template = _production_template(template_id)
    return template["expected_answer"]["choice_id"]


def _submitted_correct_answer(template_id):
    template = _production_template(template_id)
    expected = template["expected_answer"]
    if template["deterministic_scorer"] == "single_choice_v1":
        return expected["choice_id"]
    if template["deterministic_scorer"] == "multiple_choice_v1":
        return list(expected["choice_ids"])
    raise AssertionError("test helper needs an explicit answer shape for this scorer")


def _composition(tmp_path):
    persistence = build_learner_state_persistence_service(
        root=ROOT, db_path=tmp_path / "repeat-policy.sqlite3"
    )
    policy = build_reviewed_template_exposure_policy(
        root=ROOT, persistence_service=persistence
    )
    workflow = build_dual_track_diagnostic_workflow(
        root=ROOT, exposure_policy=policy
    )
    return persistence, workflow


def _state(persistence, learner_id):
    return persistence.restore(
        learner_id=learner_id, empty_state=load_initial_learner_state(ROOT)
    )["learner_state"]


def _start(workflow, learner_id, template_id=UCS_TEMPLATE):
    template = _production_template(template_id)
    return workflow.start_quick_verification(
        concept_ids=[template["concept_ids"][0]],
        intent=template["eligible_intents"][0],
        template_ids=[template_id],
        learner_id=learner_id,
    )


def _complete(workflow, learner_id, learner_state, template_id=UCS_TEMPLATE, answer="A"):
    started = _start(workflow, learner_id, template_id)
    return workflow.submit_verification(
        session=started["session"],
        answer=answer,
        submitted_template_id=template_id,
        learner_state=learner_state,
        learner_id=learner_id,
    )


def test_first_formal_then_immediate_repeats_are_practice_only(tmp_path):
    persistence, workflow = _composition(tmp_path)
    initial = _state(persistence, LEARNER_A)

    first = _complete(workflow, LEARNER_A, initial)
    first_state = first["state_update"]["learner_state"]
    assert first["attempt_mode"] == "formal"
    assert first["mastery_eligible"] is True
    assert first_state["mastery"]["uniform_cost_search"] == pytest.approx(0.35)
    persistence.save_completed(
        learner_id=LEARNER_A,
        learner_state=first_state,
        diagnostic_summary=first["formal_evidence_summary"],
        event_id="formal-event-1",
    )

    restarted_workflow = build_dual_track_diagnostic_workflow(
        root=ROOT,
        exposure_policy=build_reviewed_template_exposure_policy(
            root=ROOT, persistence_service=persistence
        ),
    )
    repeats = [_complete(restarted_workflow, LEARNER_A, first_state) for _ in range(3)]
    assert all(result["attempt_mode"] == "practice_only" for result in repeats)
    assert all(result["practice_only"] is True for result in repeats)
    assert all(result["state_update"] is None for result in repeats)
    assert all(result["evidence_eligible"] is False for result in repeats)
    assert all(result["recommendation"] is None for result in repeats)
    assert persistence.reviewed_template_exposures(learner_id=LEARNER_A).keys() == {UCS_TEMPLATE}

    restored = persistence.restore(
        learner_id=LEARNER_A, empty_state=load_initial_learner_state(ROOT)
    )
    assert restored["learner_state"]["mastery"]["uniform_cost_search"] == pytest.approx(0.35)
    assert len(restored["learner_state"]["learning_evidence"]) == 1


def test_exhausted_independent_correct_templates_do_not_keep_blocking_next_formal_action(tmp_path):
    """A real composition trace for the evidence-ceiling counterexample."""
    first_template = "verify_search_problem_components_v1"
    second_template = "verify_path_cost_accumulation_v1"
    persistence, workflow = _composition(tmp_path)
    state = _state(persistence, LEARNER_A)

    first = _complete(
        workflow,
        LEARNER_A,
        state,
        template_id=first_template,
        answer=_submitted_correct_answer(first_template),
    )
    assert first["state_update"]["learner_state"]["mastery"]["search_problem_formulation"] == pytest.approx(0.35)
    assert first["recommendation"]["concept_id"] == "search_problem_formulation"
    # No refresh/reload occurs here: the second action must see the first
    # compact evidence record already present in the returned session state.
    state_after_first = first["state_update"]["learner_state"]
    assert state_after_first["learning_evidence"][0]["template_outcomes"] == [
        {
            "template_id": first_template,
            "status": "passed",
            "final_attempt_assistance_level": "none",
        }
    ]

    second = _complete(
        workflow,
        LEARNER_A,
        state_after_first,
        template_id=second_template,
        answer=_submitted_correct_answer(second_template),
    )
    state_after = second["state_update"]["learner_state"]

    assert state_after["mastery"]["search_problem_formulation"] == pytest.approx(0.5775)
    assert second["recommendation"]["concept_id"] == "state_space_and_operators"
    assert second["recommendation"]["evidence_status"] == "formal_evidence_available"
    assert second["recommendation"]["remaining_formal_evidence_opportunities"] == 1


@pytest.mark.parametrize("template_id", P5B_TEMPLATE_IDS)
def test_each_p5b_template_repeat_is_practice_only_after_first_formal_evidence(
    tmp_path, template_id
):
    """The exposure policy applies uniformly to every newly promoted template."""
    persistence, workflow = _composition(tmp_path)
    initial = _state(persistence, LEARNER_A)
    template = _production_template(template_id)
    concept_id = template["concept_ids"][0]

    first = _complete(
        workflow,
        LEARNER_A,
        initial,
        template_id=template_id,
        answer=_correct_answer(template_id),
    )
    assert first["attempt_mode"] == "formal"
    assert first["mastery_eligible"] is True
    assert first["state_update"]["learner_state"]["mastery"][concept_id] == pytest.approx(0.35)
    persistence.save_completed(
        learner_id=LEARNER_A,
        learner_state=first["state_update"]["learner_state"],
        diagnostic_summary=first["formal_evidence_summary"],
        event_id=f"formal-{template_id}",
    )

    repeat = _complete(
        workflow,
        LEARNER_A,
        first["state_update"]["learner_state"],
        template_id=template_id,
        answer=_correct_answer(template_id),
    )
    assert repeat["attempt_mode"] == "practice_only"
    assert repeat["practice_only"] is True
    assert repeat["state_update"] is None
    assert repeat["evidence_eligible"] is False


def test_first_wrong_hint_and_reveal_create_exposure_without_independent_success(tmp_path):
    persistence, workflow = _composition(tmp_path)
    initial = _state(persistence, LEARNER_A)

    started = _start(workflow, LEARNER_A)
    wrong = workflow.submit_verification(
        session=started["session"], answer="B", submitted_template_id=UCS_TEMPLATE,
        learner_state=initial, learner_id=LEARNER_A,
    )
    hinted = workflow.choose_verification_hint_retry(
        session=wrong["session"], template_id=UCS_TEMPLATE, learner_id=LEARNER_A
    )
    hinted_done = workflow.submit_verification(
        session=hinted["session"], answer="A", submitted_template_id=UCS_TEMPLATE,
        learner_state=initial, learner_id=LEARNER_A,
    )
    update = hinted_done["state_update"]["updates"][0]
    assert update["observation_assistance"] == [False, True]
    assert update["selected_signal"] == 0.0
    assert _start(workflow, LEARNER_A)["practice_only"] is True

    other = _state(persistence, LEARNER_B)
    revealed = workflow.request_verification_reveal(
        session=_start(workflow, LEARNER_B)["session"],
        template_id=UCS_TEMPLATE,
        learner_id=LEARNER_B,
    )
    reveal_done = workflow.acknowledge_verification_reveal(
        session=revealed["session"], template_id=UCS_TEMPLATE,
        learner_state=other, learner_id=LEARNER_B,
    )
    assert reveal_done["state_update"]["updates"] == []
    assert _start(workflow, LEARNER_B)["practice_only"] is True


def test_profiles_and_distinct_templates_remain_independent_and_unseen_is_preferred(tmp_path):
    persistence, workflow = _composition(tmp_path)
    first = _complete(workflow, LEARNER_A, _state(persistence, LEARNER_A))
    assert _start(workflow, LEARNER_A)["practice_only"] is True
    assert _start(workflow, LEARNER_B)["practice_only"] is False

    handoff = build_diagnostic_handoff_service(root=ROOT)
    plan = handoff.plan(
        topic_ids=["breadth_first_search"],
        intent="diagnostic_request",
        max_templates=1,
        exposed_template_ids={"verify_bfs_frontier_choice_v1"},
    )
    assert plan["template_ids"] == ["verify_bfs_equal_cost_condition_v1"]
    assert first["state_update"] is not None


def test_same_event_id_is_idempotent_but_exposure_is_template_not_event_based(tmp_path):
    persistence, workflow = _composition(tmp_path)
    first = _complete(workflow, LEARNER_A, _state(persistence, LEARNER_A))
    state = first["state_update"]["learner_state"]
    summary = first["formal_evidence_summary"]
    assert persistence.save_completed(
        learner_id=LEARNER_A, learner_state=state, diagnostic_summary=summary,
        event_id="same-event",
    ) is False
    assert persistence.save_completed(
        learner_id=LEARNER_A, learner_state=state, diagnostic_summary=summary,
        event_id="same-event",
    ) is True
    repeat = _complete(workflow, LEARNER_A, state)
    assert repeat["practice_only"] is True
    assert repeat["state_update"] is None


def test_mixed_session_only_sends_unseen_template_observations_to_p5b(tmp_path):
    persistence, workflow = _composition(tmp_path)
    state = _state(persistence, LEARNER_A)
    persistence.claim_template_exposure(
        learner_id=LEARNER_A,
        template_id="verify_bfs_frontier_choice_v1",
        reason="formal_answer_submitted",
    )
    started = workflow.start_quick_verification(
        concept_ids=["breadth_first_search", "uniform_cost_search"],
        intent="diagnostic_request",
        template_ids=["verify_bfs_frontier_choice_v1", UCS_TEMPLATE],
        learner_id=LEARNER_A,
    )
    assert started["attempt_mode"] == "mixed"
    first = workflow.submit_verification(
        session=started["session"], answer="A",
        submitted_template_id="verify_bfs_frontier_choice_v1",
        learner_state=state, learner_id=LEARNER_A,
    )
    completed = workflow.submit_verification(
        session=first["session"], answer="A", submitted_template_id=UCS_TEMPLATE,
        learner_state=state, learner_id=LEARNER_A,
    )
    assert [step["question_id"] for step in completed["formal_evidence_summary"]["step_results"]] == [UCS_TEMPLATE]
    assert [update["concept_id"] for update in completed["state_update"]["updates"]] == ["uniform_cost_search"]
