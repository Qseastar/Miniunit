"""Run P7's synthetic-only, privacy-minimized study-pipeline dry run.

This is not a human study runner.  It uses the existing P6b integration-faithful
temporary evidence traces, freezes their eligible signals, computes research
policies offline, and exports only synthetic metadata plus closed external-item
scores.  It never writes production learner state, exposure, recommendation,
or a non-temporary database.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import secrets
import string
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.compare_mastery_policies import P0, P1, P2, P3, compare_sequence, integration_faithful_trajectories  # noqa: E402
from tools.validate_p7_assessment_candidates import validate_p7_candidate_document  # noqa: E402


SCHEMA_VERSION = 1
DEFAULT_OUTPUT = Path("/tmp/introai_p7_synthetic_study_export.json")
STUDY_ID = "introai_p7_synthetic_dry_run"
_PARTICIPANT_ALPHABET = string.ascii_uppercase + string.digits
_EXPORTED_POLICY_IDS = (P0, P2, P3)


class P7SyntheticStudyError(ValueError):
    """Raised for malformed synthetic-only study input."""


@dataclass(frozen=True)
class FrozenEvidenceSequence:
    """Immutable research snapshot after the existing formal-evidence gate."""

    frozen_evidence_sequence_id: str
    concept_id: str
    eligible_signals: tuple[float, ...]
    evidence_window: str = "study_session_selected_concepts_completed_formal_only"


def generate_participant_code() -> str:
    """Generate a random, non-identifying code for a future human protocol.

    The function is not connected to learner UUIDs, accounts, names, e-mail or
    persistence.  Synthetic dry runs intentionally use a fixed visibly
    synthetic code instead.
    """
    suffix = "".join(secrets.choice(_PARTICIPANT_ALPHABET) for _ in range(6))
    return f"R7-{suffix}"


def freeze_eligible_evidence(
    *, sequence_id: str, concept_id: str, signals: Iterable[float]
) -> FrozenEvidenceSequence:
    if not isinstance(sequence_id, str) or not sequence_id.strip():
        raise P7SyntheticStudyError("frozen_evidence_sequence_id must be a non-empty string.")
    if not isinstance(concept_id, str) or not concept_id.strip():
        raise P7SyntheticStudyError("concept_id must be a non-empty string.")
    values: list[float] = []
    for index, signal in enumerate(signals):
        if isinstance(signal, bool) or not isinstance(signal, int | float) or float(signal) not in {0.0, 1.0}:
            raise P7SyntheticStudyError(f"eligible signal at index {index} must be 0.0 or 1.0.")
        values.append(float(signal))
    if not values:
        raise P7SyntheticStudyError("a frozen formal evidence sequence must be non-empty.")
    return FrozenEvidenceSequence(
        frozen_evidence_sequence_id=sequence_id.strip(),
        concept_id=concept_id.strip(),
        eligible_signals=tuple(values),
    )


def policy_estimates(frozen: FrozenEvidenceSequence) -> dict[str, float]:
    comparison = compare_sequence(frozen.eligible_signals)
    return {policy_id: comparison[policy_id]["final_mastery"] for policy_id in _EXPORTED_POLICY_IDS}


def _reference_policy_estimate(frozen: FrozenEvidenceSequence) -> float:
    return compare_sequence(frozen.eligible_signals)[P1]["final_mastery"]


def _external_result(
    *, assessment_item_id: str, phase: str, score: float | None, missing_reason: str | None = None
) -> dict[str, Any]:
    if phase not in {"immediate", "delayed", "transfer"}:
        raise P7SyntheticStudyError("assessment_phase must be immediate, delayed or transfer.")
    if not isinstance(assessment_item_id, str) or not assessment_item_id.strip():
        raise P7SyntheticStudyError("assessment_item_id must be non-empty.")
    if score is None:
        if missing_reason not in {
            "participant_stopped_before_external_assessment",
            "delayed_session_missing",
            "concept_assessment_not_administered",
        }:
            raise P7SyntheticStudyError("missing external assessment requires a recognized missing_reason.")
    elif isinstance(score, bool) or not isinstance(score, int | float) or float(score) not in {0.0, 1.0}:
        raise P7SyntheticStudyError("external assessment score must be 0.0, 1.0 or null.")
    elif missing_reason is not None:
        raise P7SyntheticStudyError("observed external assessment cannot carry missing_reason.")
    return {
        "assessment_item_id": assessment_item_id.strip(),
        "assessment_phase": phase,
        "external_assessment_score": None if score is None else float(score),
        "missing_reason": missing_reason,
    }


def _gate_sequences() -> dict[str, list[float]]:
    """Reuse P6b's real temporary gate traces; do not recreate their logic."""
    rows = {row["scenario_id"]: row for row in integration_faithful_trajectories(ROOT)}
    return {
        "strong": list(rows["A_two_independent_correct"]["formal_eligible_signal_sequence"]),
        "weak": list(rows["E_hint_and_reveal"]["formal_eligible_signal_sequence"]),
        "contradictory_recent_failure": list(rows["B_correct_then_completed_incorrect"]["formal_eligible_signal_sequence"]),
        "contradictory_recent_success": list(rows["C_completed_incorrect_then_correct"]["formal_eligible_signal_sequence"]),
        "repeat_excluded": list(rows["D_same_template_repeat"]["formal_eligible_signal_sequence"]),
    }


def run_synthetic_study(root: Path = ROOT) -> dict[str, Any]:
    """Create eight synthetic-only scenarios without a shadow learner state."""
    candidate_report = validate_p7_candidate_document(root=root)
    if not candidate_report["valid"]:
        raise P7SyntheticStudyError("P7 candidate assessment document is invalid.")
    sequences = _gate_sequences()
    scenarios = (
        ("S1", "strong_evidence_strong_external", "breadth_first_search", sequences["strong"], "p7_ext_bfs_queue_trace_b", "immediate", 1.0, None, []),
        ("S2", "weak_evidence_weak_external", "uniform_cost_search", sequences["weak"], "p7_ext_ucs_positive_cost_bound_d", "immediate", 0.0, None, []),
        ("S3", "contradictory_evidence_strong_external", "a_star_search", sequences["contradictory_recent_failure"], "p7_ext_astar_component_change_b", "immediate", 1.0, None, []),
        ("S4", "contradictory_evidence_weak_external", "local_search", sequences["contradictory_recent_success"], "p7_ext_local_search_neighbor_a", "immediate", 0.0, None, []),
        ("S5", "policy_threshold_disagreement", "breadth_first_search", [1.0], "p7_ext_bfs_depth_claim_a", "immediate", 1.0, None, []),
        ("S6", "assisted_and_repeat_excluded", "breadth_first_search", sequences["repeat_excluded"], "p7_ext_bfs_queue_trace_b", "immediate", 1.0, None, ["practice_only_repeat", "hint_assisted_correct", "reveal_without_observation"]),
        ("S7", "participant_stops_before_external", "minimax_search", [1.0], "p7_ext_minimax_min_node_a", "immediate", None, "participant_stopped_before_external_assessment", []),
        ("S8", "delayed_session_missing", "monte_carlo_tree_search", [0.0, 1.0], "p7_ext_mcts_backpropagation_a", "delayed", None, "delayed_session_missing", []),
    )
    records = []
    for index, (scenario_id, label, concept_id, signals, item_id, phase, score, missing_reason, excluded_events) in enumerate(scenarios, start=1):
        frozen = freeze_eligible_evidence(
            sequence_id=f"p7-synthetic-freeze-{scenario_id.lower()}",
            concept_id=concept_id,
            signals=signals,
        )
        records.append(
            {
                "event_sequence": index,
                "scenario_id": scenario_id,
                "scenario_label": label,
                "frozen_evidence": {
                    **asdict(frozen),
                    "eligible_signals": list(frozen.eligible_signals),
                    "excluded_event_categories": excluded_events,
                },
                "policy_estimates": policy_estimates(frozen),
                "reference_policy_estimates": {P1: _reference_policy_estimate(frozen)},
                "external_assessment": _external_result(
                    assessment_item_id=item_id,
                    phase=phase,
                    score=score,
                    missing_reason=missing_reason,
                ),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "synthetic": True,
        "study_id": STUDY_ID,
        "participant_code": "R7-SYN-001",
        "timestamp_policy": "event_sequence_only_no_wall_clock_timestamp",
        "policy_parameters_frozen": {
            P0: {"alpha": 0.35},
            P2: {"prior_a": 1.0, "prior_b": 1.0},
            P3: {"base_alpha": 0.35, "alpha_floor": 0.10, "rule": "max(0.10, 0.35/sqrt(n))"},
        },
        "candidate_bank_status": "pending_owner_review",
        "records": records,
        "research_boundary": {
            "external_assessment_writes_mastery": False,
            "external_assessment_creates_exposure": False,
            "recommendation_evaluated": False,
            "production_learner_state_written": False,
            "network_called": False,
            "real_participant_data_used": False,
        },
    }


def write_synthetic_export(path: Path = DEFAULT_OUTPUT, root: Path = ROOT) -> dict[str, Any]:
    report = run_synthetic_study(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return deepcopy(report)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run P7 synthetic-only study pipeline dry run.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = write_synthetic_export(args.output)
    print(json.dumps({
        "output": str(args.output),
        "synthetic": report["synthetic"],
        "scenario_count": len(report["records"]),
        "missing_external_count": sum(
            record["external_assessment"]["external_assessment_score"] is None
            for record in report["records"]
        ),
    }, ensure_ascii=False, indent=2))
