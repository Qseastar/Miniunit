"""High-value invariants for the isolated P6b policy comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from introai_tutor.app_services import load_initial_learner_state
from introai_tutor.diagnostic_state_integration import DiagnosticStateIntegrationService
from introai_tutor.knowledge import load_knowledge_points
from tools.compare_mastery_policies import (
    CURRENT_ALPHA,
    P0,
    P1,
    P2,
    P3,
    POLICY_IDS,
    compare_sequence,
    count_decayed_step,
    current_inventory,
    current_fixed_step,
    enumerate_binary_sequences,
    integration_faithful_trajectories,
    order_sensitivity_study,
    policy_trajectory,
    prior_regularized_bernoulli,
    recommendation_for_mastery,
    recommendation_threshold_study,
    run_study,
    write_report,
)
from tools.audit_learner_state import _services


ROOT = Path(__file__).resolve().parents[1]
BFS = "breadth_first_search"


def _summary(signal: float) -> dict:
    return {
        "status": "completed",
        "purpose": "mastery_verification",
        "evidence_eligible": True,
        "track_id": "p6b_reference",
        "total_steps": 1,
        "passed_steps": int(signal == 1.0),
        "unresolved_steps": int(signal != 1.0),
        "concept_observations": {BFS: [signal]},
        "concept_observation_assistance": {BFS: [False]},
        "concept_observation_assistance_levels": {BFS: ["none"]},
        "concept_observation_assistance_sources": {BFS: [None]},
        "unobserved_concept_ids": [],
        "misconception_ids": [],
        "step_results": [{
            "question_id": "p6b_reference",
            "status": "passed" if signal == 1.0 else "unresolved",
            "best_score": signal,
            "attempts": 1,
        }],
    }


@pytest.mark.parametrize("signals", [(1.0,), (0.0,), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0, 0.0)])
def test_p0_reference_matches_real_production_sequential_events(signals):
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    service = DiagnosticStateIntegrationService(knowledge_data=knowledge)
    state = load_initial_learner_state(ROOT)
    for signal in signals:
        state = service.apply(learner_state=state, diagnostic_summary=_summary(signal))["learner_state"]
    assert state["mastery"].get(BFS, 0.0) == pytest.approx(current_fixed_step(signals)[-1])


def test_p1_and_p2_are_strictly_order_invariant_but_p0_is_not():
    left, right = (1.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 1.0)
    assert policy_trajectory(P1, left)[-1] == policy_trajectory(P1, right)[-1]
    assert policy_trajectory(P2, left)[-1] == policy_trajectory(P2, right)[-1]
    assert policy_trajectory(P0, left)[-1] != policy_trajectory(P0, right)[-1]
    assert policy_trajectory(P3, left)[-1] != policy_trajectory(P3, right)[-1]


def test_all_policies_are_bounded_monotone_and_deterministic():
    for sequence in enumerate_binary_sequences(6):
        for policy_id in POLICY_IDS:
            trajectory = policy_trajectory(policy_id, sequence)
            assert all(0.0 <= value <= 1.0 for value in trajectory)
            assert trajectory == policy_trajectory(policy_id, sequence)
            if sequence:
                history = sequence[:-1]
                before = policy_trajectory(policy_id, history)[-1]
                after = trajectory[-1]
                if sequence[-1] == 1.0:
                    assert after >= before
                else:
                    assert after <= before


def test_p3_is_not_a_renamed_empirical_or_beta_mean():
    sequence = (1.0, 0.0, 1.0, 0.0)
    p3 = count_decayed_step(sequence)[-1]
    assert p3 != pytest.approx(policy_trajectory(P1, sequence)[-1])
    assert p3 != pytest.approx(policy_trajectory(P2, sequence)[-1])
    assert current_fixed_step((1.0,))[1] == pytest.approx(CURRENT_ALPHA)


def test_exhaustive_and_order_studies_cover_the_required_domain():
    assert len(enumerate_binary_sequences(6)) == 126
    order = order_sensitivity_study()
    assert set(order["by_length"]) == {"2", "3", "4", "5", "6"}
    assert order["by_length"]["6"]["policy_summary"][P0]["max_order_sensitivity_range"] > 0.0
    assert order["by_length"]["6"]["policy_summary"][P1]["max_order_sensitivity_range"] == pytest.approx(0.0)
    assert order["by_length"]["6"]["policy_summary"][P2]["max_order_sensitivity_range"] == pytest.approx(0.0)


def test_prior_sensitivity_is_explicit_and_order_invariant():
    signals = (1.0, 0.0, 1.0)
    reversed_signals = tuple(reversed(signals))
    assert prior_regularized_bernoulli(signals, prior_a=1, prior_b=1)[-1] == pytest.approx(
        prior_regularized_bernoulli(reversed_signals, prior_a=1, prior_b=1)[-1]
    )
    assert prior_regularized_bernoulli((1.0,), prior_a=1, prior_b=1)[-1] > prior_regularized_bernoulli((1.0,), prior_a=2, prior_b=2)[-1]


def test_real_recommendation_adapter_uses_current_recommender_boundary():
    assert recommendation_for_mastery(root=ROOT, target_concept_id=BFS, target_mastery=0.35) == BFS
    assert recommendation_for_mastery(root=ROOT, target_concept_id=BFS, target_mastery=0.60) is None
    report = recommendation_threshold_study(ROOT)
    assert report["recommendation_function"] == "introai_tutor.recommend.recommend_next_concept"
    assert report["threshold_disagreement_count"] >= 10
    assert report["recommendation_disagreement_count"] >= 10


def test_integration_faithful_gate_excludes_repeat_and_assistance_before_comparison():
    rows = {row["scenario_id"]: row for row in integration_faithful_trajectories(ROOT)}
    assert rows["A_two_independent_correct"]["formal_eligible_signal_sequence"] == [1.0, 1.0]
    assert rows["B_correct_then_completed_incorrect"]["formal_eligible_signal_sequence"] == [1.0, 0.0]
    assert rows["C_completed_incorrect_then_correct"]["formal_eligible_signal_sequence"] == [0.0, 1.0]
    assert rows["D_same_template_repeat"]["formal_eligible_signal_sequence"] == [1.0]
    assert rows["D_same_template_repeat"]["steps"][1]["formal_or_practice_only"] == "practice_only"
    assert rows["E_hint_and_reveal"]["formal_eligible_signal_sequence"] == [0.0]
    assert rows["E_hint_and_reveal"]["steps"][1]["selected_signal"] is None


def test_unknown_or_blocked_template_fails_closed_before_policy_input(tmp_path):
    _, workflow = _services(ROOT, tmp_path / "blocked.sqlite3")
    with pytest.raises(ValueError):
        workflow.start_quick_verification(
            concept_ids=["uniform_cost_search"],
            intent="definition",
            template_ids=["blocked_or_unknown_template"],
            learner_id="synthetic_p6b_blocked",
        )


def test_policy_tool_is_not_imported_by_production_or_app():
    source_paths = [ROOT / "app.py", *sorted((ROOT / "src" / "introai_tutor").glob("*.py"))]
    assert all("compare_mastery_policies" not in path.read_text(encoding="utf-8") for path in source_paths)


def test_study_writes_only_requested_temporary_artifact(tmp_path):
    output = tmp_path / "comparison.json"
    report = write_report(output, ROOT)
    assert output.is_file()
    assert report["research_only"] is True
    assert report["configuration"]["binary_sequence_count"] == 126
    assert report["inventory"]["production_template_count"] == 28
    assert report["inventory"]["active_candidate_count"] == 0
    assert report["inventory"]["blocked_slot_count"] == 1
    assert report["inventory"]["concept_count"] == 26


def test_inventory_is_derived_from_current_manifest_and_registry():
    assert current_inventory(ROOT) == {
        "production_template_count": 28,
        "active_candidate_count": 0,
        "blocked_slot_count": 1,
        "concept_count": 26,
        "sqlite_schema_version": 3,
    }


def test_full_study_has_counterfactuals_and_no_production_mutation():
    before = load_initial_learner_state(ROOT)
    report = run_study(ROOT)
    after = load_initial_learner_state(ROOT)
    assert len(report["counterfactuals"]) == 20
    assert before == after
    assert report["configuration"]["current_alpha"] == CURRENT_ALPHA
