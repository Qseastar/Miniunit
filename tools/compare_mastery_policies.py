"""P6b offline comparison of transparent mastery aggregation policies.

RESEARCH_ONLY / NOT_PRODUCTION_POLICY
--------------------------------------
This module compares policy behaviour after the existing formal-evidence gate.
It never opens a user database, changes application state, reads environment
configuration, or calls a network service.  The production application must
not import this module.

The policies below are descriptive research baselines, not claims about true
student knowledge and not candidates automatically selected for deployment.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from itertools import product, permutations
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
# Direct ``python tools/compare_mastery_policies.py`` execution puts only the
# tools directory on sys.path.  Add the repository root solely so the P6
# helper can be imported for temporary, integration-faithful trajectories.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.app_services import load_initial_learner_state
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.learner_state_repository import SCHEMA_VERSION
from introai_tutor.recommend import recommend_next_concept


DEFAULT_OUTPUT = Path("/tmp/introai_p6b_policy_comparison.json")

RESEARCH_ONLY = True
NOT_PRODUCTION_POLICY = True
CURRENT_ALPHA = 0.35
RECOMMENDATION_THRESHOLD = 0.6
P3_ALPHA_FLOOR = 0.10

P0 = "CURRENT_FIXED_STEP"
P1 = "EQUAL_WEIGHT_EMPIRICAL_MEAN"
P2 = "PRIOR_REGULARIZED_BERNOULLI"
P3 = "COUNT_DECAYED_STEP"
POLICY_IDS = (P0, P1, P2, P3)


def _signals(signals: Iterable[float]) -> tuple[float, ...]:
    """Validate an offline, already-eligible formal signal sequence."""
    normalized: list[float] = []
    for index, value in enumerate(signals):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"signal at index {index} must be a finite number in [0, 1].")
        number = float(value)
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise ValueError(f"signal at index {index} must be a finite number in [0, 1].")
        normalized.append(number)
    return tuple(normalized)


def _alpha(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite number in [0, 1].")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be a finite number in [0, 1].")
    return number


def current_fixed_step(
    signals: Iterable[float], *, alpha: float = CURRENT_ALPHA, initial_mastery: float = 0.0
) -> tuple[float, ...]:
    """REFERENCE_REIMPLEMENTATION_FOR_COMPARISON_ONLY of the P6 formula.

    The production formula remains owned by ``DiagnosticStateIntegrationService``.
    This small numerical reference is isolated here solely because production
    integration also validates summaries, gates assistance, and calls the real
    recommender.  P6b tests compare representative sequential events against
    the production service before using this reference in policy simulations.
    """
    alpha = _alpha(alpha, "alpha")
    mastery = _alpha(initial_mastery, "initial_mastery")
    trajectory = [mastery]
    for signal in _signals(signals):
        mastery = max(0.0, min(1.0, (1.0 - alpha) * mastery + alpha * signal))
        trajectory.append(mastery)
    return tuple(trajectory)


def equal_weight_empirical_mean(signals: Iterable[float]) -> tuple[float, ...]:
    """Order-invariant empirical mean, with 0.0 only as a display start."""
    sequence = _signals(signals)
    trajectory = [0.0]
    total = 0.0
    for index, signal in enumerate(sequence, start=1):
        total += signal
        trajectory.append(total / index)
    return tuple(trajectory)


def prior_regularized_bernoulli(
    signals: Iterable[float], *, prior_a: float = 1.0, prior_b: float = 1.0
) -> tuple[float, ...]:
    """Transparent Beta-Bernoulli-style accumulator; not Bayesian tracing."""
    prior_a = _positive_finite(prior_a, "prior_a")
    prior_b = _positive_finite(prior_b, "prior_b")
    sequence = _signals(signals)
    successes = 0.0
    trajectory = [prior_a / (prior_a + prior_b)]
    for index, signal in enumerate(sequence, start=1):
        successes += signal
        trajectory.append((prior_a + successes) / (prior_a + prior_b + index))
    return tuple(trajectory)


def count_decayed_step(
    signals: Iterable[float], *, base_alpha: float = CURRENT_ALPHA, alpha_floor: float = P3_ALPHA_FLOOR
) -> tuple[float, ...]:
    """A distinct bounded, recency-aware, count-decayed recursive baseline.

    ``alpha_n = max(alpha_floor, base_alpha / sqrt(n))``.  It starts with the
    current production alpha, decreases as independent evidence accumulates,
    and retains an explicit small recency floor.  It is therefore neither an
    empirical mean nor a Beta posterior mean; its constants are transparent
    comparison settings, not fitted parameters.
    """
    base_alpha = _alpha(base_alpha, "base_alpha")
    alpha_floor = _alpha(alpha_floor, "alpha_floor")
    if alpha_floor > base_alpha:
        raise ValueError("alpha_floor must not exceed base_alpha.")
    mastery = 0.0
    trajectory = [mastery]
    for count, signal in enumerate(_signals(signals), start=1):
        step = max(alpha_floor, base_alpha / math.sqrt(count))
        mastery = max(0.0, min(1.0, (1.0 - step) * mastery + step * signal))
        trajectory.append(mastery)
    return tuple(trajectory)


def _positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a positive finite number.")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a positive finite number.")
    return number


def policy_trajectory(policy_id: str, signals: Iterable[float]) -> tuple[float, ...]:
    """Return one deterministic trajectory for a named P6b policy."""
    if policy_id == P0:
        return current_fixed_step(signals)
    if policy_id == P1:
        return equal_weight_empirical_mean(signals)
    if policy_id == P2:
        return prior_regularized_bernoulli(signals)
    if policy_id == P3:
        return count_decayed_step(signals)
    raise ValueError(f"Unknown research policy: {policy_id}")


def compare_sequence(signals: Iterable[float]) -> dict[str, dict[str, Any]]:
    """Compare all P6b policies for one already eligible signal sequence."""
    sequence = _signals(signals)
    result: dict[str, dict[str, Any]] = {}
    for policy_id in POLICY_IDS:
        trajectory = policy_trajectory(policy_id, sequence)
        deltas = [abs(after - before) for before, after in zip(trajectory, trajectory[1:])]
        result[policy_id] = {
            "trajectory": list(trajectory),
            "final_mastery": trajectory[-1],
            "max_single_step_delta": max(deltas, default=0.0),
            "mean_absolute_step_delta": sum(deltas) / len(deltas) if deltas else 0.0,
            "threshold_crossings": _threshold_crossings(trajectory),
            "final_threshold_side": "at_or_above" if trajectory[-1] >= RECOMMENDATION_THRESHOLD else "below",
        }
    return result


def enumerate_binary_sequences(max_length: int = 6) -> list[tuple[float, ...]]:
    """Return every binary sequence from length one through ``max_length``."""
    if isinstance(max_length, bool) or not isinstance(max_length, int) or max_length < 1:
        raise ValueError("max_length must be a positive integer.")
    return [tuple(float(item) for item in row) for size in range(1, max_length + 1) for row in product((0, 1), repeat=size)]


def exhaustive_sequence_study(max_length: int = 6) -> list[dict[str, Any]]:
    """Policy-isolated exhaustive study for the 2^1 + ... + 2^N alphabet."""
    rows = []
    for sequence in enumerate_binary_sequences(max_length):
        rows.append(
            {
                "sequence": list(sequence),
                "sequence_length": len(sequence),
                "correct_count": int(sum(sequence)),
                "incorrect_count": len(sequence) - int(sum(sequence)),
                "comparison": compare_sequence(sequence),
            }
        )
    return rows


def order_sensitivity_study(max_length: int = 6) -> dict[str, Any]:
    """Enumerate unique permutations for equal evidence multisets."""
    by_length: dict[str, Any] = {}
    focus = ((1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 1.0, 0.0, 0.0), (1.0, 1.0, 1.0, 0.0, 0.0, 0.0))
    focus_rows: list[dict[str, Any]] = []
    for length in range(2, max_length + 1):
        groups = []
        ranges: dict[str, list[float]] = {policy_id: [] for policy_id in POLICY_IDS}
        for successes in range(1, length):
            base = (1.0,) * successes + (0.0,) * (length - successes)
            variants = sorted(set(permutations(base)))
            policy_ranges: dict[str, dict[str, float]] = {}
            for policy_id in POLICY_IDS:
                finals = [policy_trajectory(policy_id, variant)[-1] for variant in variants]
                minimum, maximum = min(finals), max(finals)
                policy_ranges[policy_id] = {
                    "min_final_mastery": minimum,
                    "max_final_mastery": maximum,
                    "order_sensitivity_range": maximum - minimum,
                    "permutation_std": _population_std(finals),
                }
                ranges[policy_id].append(maximum - minimum)
            groups.append({"successes": successes, "failures": length - successes, "permutation_count": len(variants), "policies": policy_ranges})
        by_length[str(length)] = {
            "groups": groups,
            "policy_summary": {
                policy_id: {
                    "max_order_sensitivity_range": max(values, default=0.0),
                    "mean_order_sensitivity_range": sum(values) / len(values) if values else 0.0,
                }
                for policy_id, values in ranges.items()
            },
        }
    for multiset in focus:
        variants = sorted(set(permutations(multiset)))
        focus_rows.append(
            {
                "multiset": list(multiset),
                "first_permutation": list(variants[0]),
                "last_permutation": list(variants[-1]),
                "policies": {
                    policy_id: {
                        "min_final_mastery": min(policy_trajectory(policy_id, value)[-1] for value in variants),
                        "max_final_mastery": max(policy_trajectory(policy_id, value)[-1] for value in variants),
                    }
                    for policy_id in POLICY_IDS
                },
            }
        )
    return {"by_length": by_length, "focus_multisets": focus_rows}


def responsiveness_study() -> list[dict[str, Any]]:
    cases = [
        ((0.0, 0.0, 0.0), 1.0),
        ((1.0, 1.0, 1.0), 0.0),
        ((0.0, 0.0, 0.0, 0.0, 0.0), 1.0),
        ((1.0, 1.0, 1.0, 1.0, 1.0), 0.0),
    ]
    rows = []
    for history, new_signal in cases:
        row: dict[str, Any] = {"history": list(history), "new_signal": new_signal, "deltas": {}}
        for policy_id in POLICY_IDS:
            before = policy_trajectory(policy_id, history)[-1]
            after = policy_trajectory(policy_id, history + (new_signal,))[-1]
            row["deltas"][policy_id] = {"before": before, "after": after, "delta": after - before}
        rows.append(row)
    return rows


def stability_study() -> list[dict[str, Any]]:
    sequences = ((1, 0, 1, 0, 1, 0), (0, 1, 0, 1, 0, 1), (1, 1, 0, 0, 1, 0))
    rows = []
    for raw_sequence in sequences:
        sequence = tuple(float(value) for value in raw_sequence)
        comparison = compare_sequence(sequence)
        rows.append(
            {
                "sequence": list(sequence),
                "policies": {
                    policy_id: {
                        "final_mastery": data["final_mastery"],
                        "max_absolute_delta": data["max_single_step_delta"],
                        "mean_absolute_delta": data["mean_absolute_step_delta"],
                        "threshold_crossings": data["threshold_crossings"],
                    }
                    for policy_id, data in comparison.items()
                },
            }
        )
    return rows


def sparse_and_long_run_study() -> dict[str, Any]:
    sparse_sequences = ((1,), (0,), (1, 1), (0, 0), (1, 0), (0, 1))
    sparse = [{"sequence": list(sequence), "comparison": compare_sequence(sequence)} for sequence in sparse_sequences]
    long = []
    for sequence in ((1.0,) * 10, (0.0,) * 10):
        long.append({"sequence": list(sequence), "comparison": compare_sequence(sequence)})
    return {"sparse": sparse, "long_homogeneous": long}


def fixed_alpha_sensitivity() -> dict[str, Any]:
    values = (0.2, CURRENT_ALPHA, 0.5)
    sequences = ((1.0,), (0.0,), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0, 0.0, 0.0))
    return {
        "alphas": list(values),
        "sequences": [
            {
                "sequence": list(sequence),
                "trajectories": {str(alpha): list(current_fixed_step(sequence, alpha=alpha)) for alpha in values},
            }
            for sequence in sequences
        ],
        "order_range_for_1100": {
            str(alpha): _permutation_range(lambda row: current_fixed_step(row, alpha=alpha)[-1], (1.0, 1.0, 0.0, 0.0))
            for alpha in values
        },
    }


def beta_prior_sensitivity() -> dict[str, Any]:
    priors = ((1.0, 1.0), (2.0, 2.0))
    sequences = ((1.0,), (0.0,), (1.0, 1.0), (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0,) * 10)
    return {
        "priors": [list(prior) for prior in priors],
        "sequences": [
            {
                "sequence": list(sequence),
                "trajectories": {
                    f"Beta({int(a)},{int(b)})": list(prior_regularized_bernoulli(sequence, prior_a=a, prior_b=b))
                    for a, b in priors
                },
            }
            for sequence in sequences
        ],
    }


def recommendation_for_mastery(
    *, root: Path, target_concept_id: str, target_mastery: float, prerequisite_mastery: dict[str, float] | None = None
) -> str | None:
    """Invoke the unmodified production recommender on a synthetic state."""
    target_mastery = _alpha(target_mastery, "target_mastery")
    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
    concept_ids = [point["id"] for point in knowledge["knowledge_points"]]
    if target_concept_id not in concept_ids:
        raise ValueError(f"Unknown target concept: {target_concept_id}")
    state = load_initial_learner_state(root)
    state["mastery"] = {concept_id: 1.0 for concept_id in concept_ids}
    state["mastery"][target_concept_id] = target_mastery
    for concept_id, mastery in (prerequisite_mastery or {}).items():
        if concept_id not in state["mastery"]:
            raise ValueError(f"Unknown prerequisite concept: {concept_id}")
        state["mastery"][concept_id] = _alpha(mastery, "prerequisite mastery")
    result = recommend_next_concept(knowledge, state)
    return result.get("concept_id") if isinstance(result, dict) else None


def recommendation_threshold_study(root: Path = ROOT, max_length: int = 6) -> dict[str, Any]:
    """Use the real recommendation function for all threshold comparisons."""
    rows = []
    target = "breadth_first_search"
    for sequence in enumerate_binary_sequences(max_length):
        masteries = {policy_id: policy_trajectory(policy_id, sequence)[-1] for policy_id in POLICY_IDS}
        recommendations = {
            policy_id: recommendation_for_mastery(root=root, target_concept_id=target, target_mastery=value)
            for policy_id, value in masteries.items()
        }
        threshold_sides = {policy_id: value >= RECOMMENDATION_THRESHOLD for policy_id, value in masteries.items()}
        if len(set(threshold_sides.values())) > 1:
            rows.append({"sequence": list(sequence), "masteries": masteries, "threshold_sides": threshold_sides, "recommendations": recommendations})
    return {
        "target_concept_id": target,
        "tested_sequence_count": len(enumerate_binary_sequences(max_length)),
        "threshold_disagreement_count": len(rows),
        "recommendation_disagreement_count": sum(len(set(row["recommendations"].values())) > 1 for row in rows),
        "minimal_cases": rows[:10],
        "all_cases": rows,
        "recommendation_function": "introai_tutor.recommend.recommend_next_concept",
    }


def prerequisite_sensitive_study(root: Path = ROOT) -> list[dict[str, Any]]:
    """Show real prerequisite backtracking under policy-induced threshold sides."""
    edges = (
        ("frontier_and_explored_set", "breadth_first_search"),
        ("breadth_first_search", "completeness_optimality_complexity"),
        ("uniform_cost_search", "informed_search_and_heuristics"),
    )
    rows = []
    for prerequisite, dependent in edges:
        policy_rows = {}
        for policy_id in POLICY_IDS:
            prerequisite_mastery = policy_trajectory(policy_id, (1.0,))[-1]
            recommendation = recommendation_for_mastery(
                root=root,
                target_concept_id=dependent,
                target_mastery=0.0,
                prerequisite_mastery={prerequisite: prerequisite_mastery},
            )
            policy_rows[policy_id] = {
                "prerequisite_mastery_from_single_correct": prerequisite_mastery,
                "dependent_mastery": 0.0,
                "recommendation": recommendation,
            }
        rows.append({"prerequisite": prerequisite, "dependent": dependent, "policies": policy_rows})
    return rows


def high_value_counterfactuals(root: Path = ROOT) -> list[dict[str, Any]]:
    """Twenty controlled pairs: one named factor varies per comparison."""
    pairs = [
        ("CF01_order_10_vs_01", "order", (1.0, 0.0), (0.0, 1.0)),
        ("CF02_order_110_vs_011", "order", (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)),
        ("CF03_order_1100_vs_0011", "order", (1.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 1.0)),
        ("CF04_order_111000_vs_000111", "order", (1.0, 1.0, 1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)),
        ("CF05_count_1_vs_11", "independent_evidence_count", (1.0,), (1.0, 1.0)),
        ("CF06_count_0_vs_00", "independent_evidence_count", (0.0,), (0.0, 0.0)),
        ("CF07_latest_0001_vs_0000", "latest_evidence", (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)),
        ("CF08_latest_1110_vs_1111", "latest_evidence", (1.0, 1.0, 1.0, 0.0), (1.0, 1.0, 1.0, 1.0)),
        ("CF09_late_000001_vs_000000", "latest_evidence", (0.0, 0.0, 0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        ("CF10_late_111110_vs_111111", "latest_evidence", (1.0, 1.0, 1.0, 1.0, 1.0, 0.0), (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)),
        ("CF11_balance_10_vs_11", "one_failure_to_success", (1.0, 0.0), (1.0, 1.0)),
        ("CF12_balance_01_vs_00", "one_success_to_failure", (0.0, 1.0), (0.0, 0.0)),
        ("CF13_contradiction_1010_vs_0101", "order", (1.0, 0.0, 1.0, 0.0), (0.0, 1.0, 0.0, 1.0)),
        ("CF14_history_101_vs_1011", "additional_correct", (1.0, 0.0, 1.0), (1.0, 0.0, 1.0, 1.0)),
        ("CF15_history_101_vs_1010", "additional_incorrect", (1.0, 0.0, 1.0), (1.0, 0.0, 1.0, 0.0)),
        ("CF16_sparse_1_vs_0", "single_evidence_outcome", (1.0,), (0.0,)),
        ("CF17_sparse_11_vs_00", "two_evidence_outcome", (1.0, 1.0), (0.0, 0.0)),
        ("CF18_equal_count_110_vs_101", "order", (1.0, 1.0, 0.0), (1.0, 0.0, 1.0)),
        ("CF19_equal_count_001_vs_010", "order", (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
        ("CF20_equal_count_11100_vs_00111", "order", (1.0, 1.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 1.0, 1.0)),
    ]
    rows = []
    for case_id, factor, left, right in pairs:
        left_data, right_data = compare_sequence(left), compare_sequence(right)
        rows.append(
            {
                "case_id": case_id,
                "changed_factor": factor,
                "left_sequence": list(left),
                "right_sequence": list(right),
                "policies": {
                    policy_id: {
                        "left_mastery": left_data[policy_id]["final_mastery"],
                        "right_mastery": right_data[policy_id]["final_mastery"],
                        "mastery_delta": right_data[policy_id]["final_mastery"] - left_data[policy_id]["final_mastery"],
                        "left_recommendation": recommendation_for_mastery(root=root, target_concept_id="breadth_first_search", target_mastery=left_data[policy_id]["final_mastery"]),
                        "right_recommendation": recommendation_for_mastery(root=root, target_concept_id="breadth_first_search", target_mastery=right_data[policy_id]["final_mastery"]),
                    }
                    for policy_id in POLICY_IDS
                },
            }
        )
    return rows


def integration_faithful_trajectories(root: Path = ROOT) -> list[dict[str, Any]]:
    """Drive real templates/gates in temporary SQLite before comparison.

    This intentionally proves only the connection between real evidence
    eligibility and the isolated policy input.  It does not turn synthetic
    binary sequences into an end-to-end learner simulation.
    """
    # Imported lazily to keep normal mathematical use free of persistence setup.
    from tools.audit_learner_state import _correct_answer, _template_rows, _wrong_answer, run_session

    rows = _template_rows(root)
    bfs_a = rows["verify_bfs_frontier_choice_v1"]
    bfs_b = rows["verify_bfs_equal_cost_condition_v1"]
    scenarios = (
        ("A_two_independent_correct", (("verify_bfs_frontier_choice_v1", [_correct_answer(bfs_a)], "none"), ("verify_bfs_equal_cost_condition_v1", [_correct_answer(bfs_b)], "none"))),
        ("B_correct_then_completed_incorrect", (("verify_bfs_frontier_choice_v1", [_correct_answer(bfs_a)], "none"), ("verify_bfs_equal_cost_condition_v1", [_wrong_answer(bfs_b), _wrong_answer(bfs_b)], "hint"))),
        ("C_completed_incorrect_then_correct", (("verify_bfs_frontier_choice_v1", [_wrong_answer(bfs_a), _wrong_answer(bfs_a)], "hint"), ("verify_bfs_equal_cost_condition_v1", [_correct_answer(bfs_b)], "none"))),
        ("D_same_template_repeat", (("verify_bfs_frontier_choice_v1", [_correct_answer(bfs_a)], "none"), ("verify_bfs_frontier_choice_v1", [_correct_answer(bfs_a)], "none"))),
        ("E_hint_and_reveal", (("verify_bfs_frontier_choice_v1", [_wrong_answer(bfs_a), _correct_answer(bfs_a)], "hint"), ("verify_bfs_equal_cost_condition_v1", [], "reveal"))),
    )
    output = []
    with TemporaryDirectory(prefix="introai-p6b-") as directory:
        for scenario_index, (scenario_id, steps) in enumerate(scenarios):
            database = Path(directory) / f"{scenario_index}.sqlite3"
            learner_id = f"p6b_synthetic_{scenario_index}"
            snapshots = []
            formal_signals: list[float] = []
            for step_index, (template_id, answers, assistance) in enumerate(steps):
                _, snapshot = run_session(
                    root=root,
                    database=database,
                    learner_id=learner_id,
                    template_id=template_id,
                    answer_sequence=answers,
                    trajectory_id=scenario_id,
                    step_index=step_index,
                    assistance=assistance,
                )
                snapshots.append({
                    "template_id": snapshot.template_id,
                    "formal_or_practice_only": snapshot.formal_or_practice_only,
                    "assistance_provenance": snapshot.assistance_provenance,
                    "selected_signal": snapshot.selected_signal,
                    "state_update_present": snapshot.state_update_present,
                    "post_mastery": snapshot.post_mastery,
                })
                if snapshot.state_update_present and snapshot.selected_signal is not None:
                    formal_signals.append(float(snapshot.selected_signal))
            output.append({
                "scenario_id": scenario_id,
                "steps": snapshots,
                "formal_eligible_signal_sequence": formal_signals,
                "policy_isolated_comparison": compare_sequence(formal_signals),
            })
    return output


def policy_property_matrix() -> list[dict[str, str]]:
    return [
        {"policy": P0, "order_invariance": "LOW", "recency_responsiveness": "HIGH", "sparse_data_conservatism": "HIGH", "long_run_stability": "MEDIUM", "contradictory_evidence_stability": "LOW", "interpretability": "HIGH", "parameter_dependence": "ONE_FIXED_ALPHA", "recommendation_stability": "LOW_NEAR_THRESHOLD", "current_implementation_compatibility": "EXACT_CURRENT"},
        {"policy": P1, "order_invariance": "HIGH", "recency_responsiveness": "LOW_AFTER_MORE_EVIDENCE", "sparse_data_conservatism": "LOW", "long_run_stability": "HIGH", "contradictory_evidence_stability": "HIGH", "interpretability": "HIGH", "parameter_dependence": "NONE", "recommendation_stability": "HIGH_FOR_PERMUTATIONS", "current_implementation_compatibility": "RESEARCH_ONLY"},
        {"policy": P2, "order_invariance": "HIGH", "recency_responsiveness": "LOW_AFTER_MORE_EVIDENCE", "sparse_data_conservatism": "MEDIUM", "long_run_stability": "HIGH", "contradictory_evidence_stability": "HIGH", "interpretability": "HIGH", "parameter_dependence": "EXPLICIT_SYMMETRIC_PRIOR", "recommendation_stability": "HIGH_FOR_PERMUTATIONS", "current_implementation_compatibility": "RESEARCH_ONLY"},
        {"policy": P3, "order_invariance": "LOW_BUT_DECAYS", "recency_responsiveness": "MEDIUM", "sparse_data_conservatism": "HIGH", "long_run_stability": "MEDIUM", "contradictory_evidence_stability": "MEDIUM", "interpretability": "MEDIUM_HIGH", "parameter_dependence": "BASE_ALPHA_AND_FLOOR", "recommendation_stability": "MEDIUM_NEAR_THRESHOLD", "current_implementation_compatibility": "RESEARCH_ONLY"},
    ]


def current_inventory(root: Path = ROOT) -> dict[str, int]:
    """Derive the P6b baseline from the real registry and derived manifest."""
    from tools.verification_benchmark import build_manifest

    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
    manifest = build_manifest(root=root)
    return {
        "production_template_count": len(manifest["production"]),
        "active_candidate_count": len(manifest["candidates"]),
        "blocked_slot_count": len(manifest["blocked_slots"]),
        "concept_count": len(knowledge["knowledge_points"]),
        "sqlite_schema_version": SCHEMA_VERSION,
    }


def run_study(root: Path = ROOT) -> dict[str, Any]:
    """Run the complete deterministic P6b comparison into a serializable report."""
    exhaustive = exhaustive_sequence_study()
    return {
        "study": "P6b Learner-State Aggregation Policy Comparative Study",
        "research_only": True,
        "not_production_policy": True,
        "inventory": current_inventory(root),
        "configuration": {
            "current_alpha": CURRENT_ALPHA,
            "recommendation_threshold": RECOMMENDATION_THRESHOLD,
            "p3_alpha_floor": P3_ALPHA_FLOOR,
            "binary_sequence_max_length": 6,
            "binary_sequence_count": len(exhaustive),
            "data_boundary": "synthetic eligible independent formal signals; temporary SQLite only for integration-faithful gate checks",
        },
        "integration_faithful_trajectories": integration_faithful_trajectories(root),
        "exhaustive_sequences": exhaustive,
        "order_sensitivity": order_sensitivity_study(),
        "responsiveness": responsiveness_study(),
        "stability": stability_study(),
        "sparse_and_long_run": sparse_and_long_run_study(),
        "fixed_alpha_sensitivity": fixed_alpha_sensitivity(),
        "beta_prior_sensitivity": beta_prior_sensitivity(),
        "recommendation_threshold": recommendation_threshold_study(root),
        "prerequisite_sensitive_cases": prerequisite_sensitive_study(root),
        "counterfactuals": high_value_counterfactuals(root),
        "policy_property_matrix": policy_property_matrix(),
    }


def write_report(path: Path = DEFAULT_OUTPUT, root: Path = ROOT) -> dict[str, Any]:
    report = run_study(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _threshold_crossings(trajectory: tuple[float, ...]) -> int:
    return sum((before < RECOMMENDATION_THRESHOLD) != (after < RECOMMENDATION_THRESHOLD) for before, after in zip(trajectory, trajectory[1:]))


def _population_std(values: list[float]) -> float:
    if not values:
        return 0.0
    average = sum(values) / len(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))


def _permutation_range(fn: Callable[[tuple[float, ...]], float], multiset: tuple[float, ...]) -> float:
    values = [fn(item) for item in set(permutations(multiset))]
    return max(values) - min(values)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the offline P6b mastery-policy comparison.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = write_report(args.output)
    threshold = report["recommendation_threshold"]
    print(json.dumps({
        "output": str(args.output),
        "binary_sequence_count": report["configuration"]["binary_sequence_count"],
        "threshold_disagreement_count": threshold["threshold_disagreement_count"],
        "recommendation_disagreement_count": threshold["recommendation_disagreement_count"],
    }, ensure_ascii=False, indent=2))
