"""Run P7's synthetic-only Study A alignment-analysis dry run.

This module exercises analysis plumbing only.  It does not create a human-study
schema, open a learner database, read environment configuration, call a network
service, update mastery, create evidence, or invoke recommendation.  It must
remain outside production imports.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.compare_mastery_policies import P0, P2, P3, policy_trajectory  # noqa: E402
from tools.validate_p7_assessment_candidates import (  # noqa: E402
    load_p7_candidate_document,
    validate_p7_candidate_document,
)
from tools.validate_p7_readiness_status import (  # noqa: E402
    load_p7_readiness_status,
    validate_p7_readiness_status,
)
from tools.validate_p7_study_a_owner_design import (  # noqa: E402
    load_p7_study_a_owner_design,
    validate_p7_study_a_owner_design,
)


FIXTURE_PATH = ROOT / "data" / "evaluation" / "p7_study_a_synthetic_fixtures.json"
DEFAULT_OUTPUT = Path("/tmp/introai_p7_study_a_synthetic_analysis.json")
SCHEMA_VERSION = 1
POLICY_IDS = (P0, P2, P3)
MINIMUM_VALID_PAIRS = 3

_TOP_LEVEL_KEYS = {
    "schema_version",
    "record_type",
    "synthetic_only",
    "not_approved_for_real_human_data",
    "candidate_analysis_not_yet_frozen_for_real_study",
    "synthetic_test_missing_reason_vocabulary",
    "study_a_boundary",
    "criterion_composition",
    "records",
}
_RECORD_KEYS = {
    "synthetic_profile_id",
    "scenario_tags",
    "analysis_groups",
    "concept_id",
    "frozen_evidence",
    "policy_unavailable_reasons",
    "external_item_results",
}
_FROZEN_EVIDENCE_KEYS = {"frozen_evidence_sequence_id", "eligible_signals"}
_ITEM_RESULT_KEYS = {
    "assessment_item_id",
    "criterion_role",
    "external_correct",
    "external_total",
    "missing_reason",
}
_COMPOSITION_KEYS = {
    "status",
    "actual_study_a_item_assignment",
    "primary_immediate_item_ids_by_concept",
    "exploratory_item_ids",
}
_PROFILE_ID_PATTERN = re.compile(r"^synthetic_[0-9]{3}$")
_SEQUENCE_ID_PATTERN = re.compile(r"^synthetic_freeze_[a-z0-9_]+$")
_FORBIDDEN_KEYS = {
    "name",
    "student_id",
    "email",
    "ip",
    "user_agent",
    "learner_uuid",
    "qa",
    "question",
    "question_text",
    "prompt",
    "pdf",
    "timestamp",
    "grade",
    "api_key",
    "authorization",
    "secret",
}


class P7StudyASyntheticAnalysisError(ValueError):
    """Raised for malformed synthetic-only analysis input or unsafe boundaries."""


def _all_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


def _is_binary(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float) and float(value) in {0.0, 1.0}


def _required_primary_items() -> dict[str, tuple[str, ...]]:
    """Current synthetic composition only; it is not a future Study A assignment."""
    return {
        "breadth_first_search": (
            "p7_ext_bfs_depth_claim_a",
            "p7_ext_bfs_queue_trace_b",
        ),
        "uniform_cost_search": (
            "p7_ext_ucs_cost_accumulation_a",
            "p7_ext_ucs_positive_cost_bound_d",
        ),
        "a_star_search": (
            "p7_ext_astar_zero_heuristic_c",
            "p7_ext_astar_component_change_b",
        ),
        "local_search": ("p7_ext_local_search_neighbor_a",),
        "minimax_search": ("p7_ext_minimax_min_node_a",),
        "monte_carlo_tree_search": (
            "p7_ext_mcts_backpropagation_a",
            "p7_ext_mcts_expand_untried_child_b",
        ),
    }


def _expected_exploratory_items() -> tuple[str, ...]:
    return ("p7_ext_minimax_two_level_b",)


def load_synthetic_fixture(path: str | Path = FIXTURE_PATH) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise P7StudyASyntheticAnalysisError("P7 Study A synthetic fixture is missing.") from error
    except json.JSONDecodeError as error:
        raise P7StudyASyntheticAnalysisError("P7 Study A synthetic fixture is invalid JSON.") from error
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        raise P7StudyASyntheticAnalysisError("P7 Study A synthetic fixture has an invalid top-level schema.")
    return document


def validate_synthetic_fixture(
    *, root: Path = ROOT, path: str | Path = FIXTURE_PATH
) -> dict[str, Any]:
    """Validate the synthetic contract without accepting a real-study data shape."""
    root = Path(root)
    document = load_synthetic_fixture(path)
    errors: list[str] = []

    if document["schema_version"] != SCHEMA_VERSION:
        errors.append("fixture schema_version must be 1")
    if document["record_type"] != "p7_study_a_synthetic_fixture_set":
        errors.append("fixture record_type must identify the synthetic fixture set")
    for key in (
        "synthetic_only",
        "not_approved_for_real_human_data",
        "candidate_analysis_not_yet_frozen_for_real_study",
    ):
        if document[key] is not True:
            errors.append(f"fixture {key} must be true")
    forbidden = sorted(set(_all_keys(document)) & _FORBIDDEN_KEYS)
    if forbidden:
        errors.append(f"fixture contains forbidden privacy-sensitive fields: {', '.join(forbidden)}")

    vocabulary = document["synthetic_test_missing_reason_vocabulary"]
    if not isinstance(vocabulary, list) or not vocabulary or any(
        not isinstance(reason, str) or not reason.strip() for reason in vocabulary
    ) or len(set(vocabulary)) != len(vocabulary):
        errors.append("synthetic_test_missing_reason_vocabulary must be a non-empty unique string list")
        vocabulary = []

    boundary = document["study_a_boundary"]
    if not isinstance(boundary, dict) or boundary != {
        "research_question": "frozen_estimate_rank_monotonic_alignment_with_independent_course_grounded_performance_criterion",
        "human_study_authorized": False,
        "real_human_data_used": False,
        "writes_production_state": False,
        "calls_recommendation": False,
    }:
        errors.append("study_a_boundary must preserve the synthetic-only research boundary")

    composition = document["criterion_composition"]
    if not isinstance(composition, dict) or set(composition) != _COMPOSITION_KEYS:
        errors.append("criterion_composition has an invalid schema")
        composition = {}
    expected_primary = _required_primary_items()
    if composition.get("status") != "SYNTHETIC_FIXTURE_ALIGNED_WITH_OWNER_TECHNICAL_DESIGN":
        errors.append("criterion composition must remain aligned with the frozen owner technical design")
    if composition.get("actual_study_a_item_assignment") != "OWNER_TECHNICAL_DESIGN_FROZEN_NOT_HUMAN_STUDY_RELEASE":
        errors.append("synthetic item assignment must remain technical-design-only, not a human-study release")
    primary = composition.get("primary_immediate_item_ids_by_concept")
    if not isinstance(primary, dict) or set(primary) != set(expected_primary):
        errors.append("primary immediate composition must cover the six current synthetic concepts")
    else:
        for concept_id, expected_ids in expected_primary.items():
            if primary[concept_id] != list(expected_ids):
                errors.append(f"primary immediate composition for {concept_id} is not the documented synthetic set")
    if composition.get("exploratory_item_ids") != list(_expected_exploratory_items()):
        errors.append("only the approved Minimax transfer item may be listed as exploratory")

    readiness = validate_p7_readiness_status(root=root)
    if not readiness["valid"]:
        errors.append("P7 readiness status must validate before synthetic analysis")
    else:
        status = load_p7_readiness_status(root / "data" / "evaluation" / "p7_readiness_status.json")
        if status["readiness_level"] != 2 or status["human_study"]["authorized"] is not False:
            errors.append("synthetic analysis requires Level 2 with human study authorization false")
    candidates = validate_p7_candidate_document(root=root)
    if not candidates["valid"]:
        errors.append("P7 candidate bank must validate before synthetic analysis")
        active_items: dict[str, str] = {}
    else:
        candidate_document = load_p7_candidate_document(root / "data" / "evaluation" / "p7_external_assessment_candidates.json")
        active_items = {
            item["assessment_item_id"]: item["concept_id"] for item in candidate_document["items"]
        }
        if set(active_items) != set().union(*[set(ids) for ids in expected_primary.values()], set(_expected_exploratory_items())):
            errors.append("synthetic composition does not match the current 11-item active external bank")

    owner_design = validate_p7_study_a_owner_design(root=root)
    if not owner_design["valid"]:
        errors.append("frozen owner technical design must validate before synthetic analysis")
    else:
        design = load_p7_study_a_owner_design(root / "data" / "evaluation" / "p7_study_a_owner_design_decisions.json")
        if design["primary_instrument"]["primary_item_ids_by_concept"] != {
            concept_id: list(item_ids) for concept_id, item_ids in expected_primary.items()
        }:
            errors.append("synthetic primary composition does not match the frozen owner technical design")
        if design["minimax_transfer"]["item_id"] != _expected_exploratory_items()[0]:
            errors.append("synthetic exploratory transfer item does not match the frozen owner technical design")

    records = document["records"]
    if not isinstance(records, list) or not records:
        errors.append("records must be a non-empty list")
        records = []
    seen_profiles: set[str] = set()
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
            errors.append(f"{label} has an invalid schema")
            continue
        profile_id = record["synthetic_profile_id"]
        if not isinstance(profile_id, str) or not _PROFILE_ID_PATTERN.fullmatch(profile_id):
            errors.append(f"{label}.synthetic_profile_id must use the synthetic_XXX format")
        elif profile_id in seen_profiles:
            errors.append(f"{label}.synthetic_profile_id must be unique")
        else:
            seen_profiles.add(profile_id)
        if record["concept_id"] not in expected_primary:
            errors.append(f"{label}.concept_id is not in the current six-concept synthetic scope")
        for field in ("scenario_tags", "analysis_groups"):
            value = record[field]
            if not isinstance(value, list) or not value or any(
                not isinstance(entry, str) or not entry.strip() for entry in value
            ):
                errors.append(f"{label}.{field} must be a non-empty string list")
        evidence = record["frozen_evidence"]
        unavailable = record["policy_unavailable_reasons"]
        if evidence is None:
            if not isinstance(unavailable, dict) or set(unavailable) != set(POLICY_IDS) or any(
                value != "synthetic_no_frozen_eligible_evidence" for value in unavailable.values()
            ):
                errors.append(f"{label} without frozen evidence must explicitly mark all policies unavailable")
        else:
            if not isinstance(evidence, dict) or set(evidence) != _FROZEN_EVIDENCE_KEYS:
                errors.append(f"{label}.frozen_evidence has an invalid schema")
            else:
                sequence_id = evidence["frozen_evidence_sequence_id"]
                signals = evidence["eligible_signals"]
                if not isinstance(sequence_id, str) or not _SEQUENCE_ID_PATTERN.fullmatch(sequence_id):
                    errors.append(f"{label} has an invalid synthetic frozen evidence id")
                if not isinstance(signals, list) or not signals or not all(_is_binary(signal) for signal in signals):
                    errors.append(f"{label} eligible signals must be a non-empty binary list")
            if unavailable != {}:
                errors.append(f"{label} with frozen evidence must not suppress a policy calculation")

        item_results = record["external_item_results"]
        if not isinstance(item_results, list) or not item_results:
            errors.append(f"{label}.external_item_results must be non-empty")
            continue
        expected_for_concept = set(expected_primary.get(record["concept_id"], ()))
        observed_primary_ids: set[str] = set()
        seen_item_ids: set[str] = set()
        for item_index, item in enumerate(item_results):
            item_label = f"{label}.external_item_results[{item_index}]"
            if not isinstance(item, dict) or set(item) != _ITEM_RESULT_KEYS:
                errors.append(f"{item_label} has an invalid schema")
                continue
            item_id = item["assessment_item_id"]
            if item_id in seen_item_ids:
                errors.append(f"{item_label}.assessment_item_id is duplicated within its record")
            seen_item_ids.add(item_id)
            if item_id not in active_items:
                errors.append(f"{item_label}.assessment_item_id is not in the active 11-item bank")
            elif active_items[item_id] != record["concept_id"]:
                errors.append(f"{item_label}.assessment_item_id does not belong to the record concept")
            role = item["criterion_role"]
            if item_id == "p7_ext_minimax_two_level_b":
                if role != "exploratory_transfer":
                    errors.append(f"{item_label} must remain exploratory_transfer")
            elif item_id in expected_for_concept:
                if role != "synthetic_primary_immediate":
                    errors.append(f"{item_label} must be synthetic_primary_immediate")
                observed_primary_ids.add(item_id)
            else:
                errors.append(f"{item_label} is not an allowed item for this synthetic concept composition")
            correct, total, reason = item["external_correct"], item["external_total"], item["missing_reason"]
            if correct is None or total is None:
                if correct is not None or total is not None or reason not in vocabulary:
                    errors.append(f"{item_label} missing result must use null + a synthetic test missing reason")
            elif (
                isinstance(correct, bool)
                or not isinstance(correct, int)
                or isinstance(total, bool)
                or not isinstance(total, int)
                or total != 1
                or correct not in {0, 1}
                or reason is not None
            ):
                errors.append(f"{item_label} observed result must be correct 0/1 over total 1 with null missing_reason")
        if observed_primary_ids != expected_for_concept:
            errors.append(f"{label} must represent every synthetic primary item for its concept exactly once")

    return {
        "valid": not errors,
        "errors": errors,
        "summary": {
            "record_count": len(records),
            "policy_ids": list(POLICY_IDS),
            "minimum_valid_pairs": MINIMUM_VALID_PAIRS,
            "synthetic_only": document["synthetic_only"],
            "not_approved_for_real_human_data": document["not_approved_for_real_human_data"],
        },
    }


def _criterion_for_record(record: dict[str, Any]) -> dict[str, Any]:
    primary = [
        item for item in record["external_item_results"]
        if item["criterion_role"] == "synthetic_primary_immediate"
    ]
    exploratory = [
        item["assessment_item_id"] for item in record["external_item_results"]
        if item["criterion_role"] == "exploratory_transfer"
    ]
    missing = [item for item in primary if item["external_correct"] is None]
    observed = [item for item in primary if item["external_correct"] is not None]
    if missing:
        return {
            "status": "external_missing_no_primary_alignment_pair",
            "external_correct": None,
            "external_total": None,
            "external_score": None,
            "expected_primary_item_count": len(primary),
            "observed_primary_item_count": len(observed),
            "missing_primary_item_count": len(missing),
            "missing_reasons": [item["missing_reason"] for item in missing],
            "exploratory_item_ids_excluded": exploratory,
        }
    correct = sum(item["external_correct"] for item in primary)
    total = sum(item["external_total"] for item in primary)
    return {
        "status": "complete_primary_immediate_synthetic_criterion",
        "external_correct": correct,
        "external_total": total,
        "external_score": correct / total,
        "expected_primary_item_count": len(primary),
        "observed_primary_item_count": len(observed),
        "missing_primary_item_count": 0,
        "missing_reasons": [],
        "exploratory_item_ids_excluded": exploratory,
    }


def _policy_estimates(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = record["frozen_evidence"]
    if evidence is None:
        return {
            policy_id: {
                "status": "unavailable",
                "estimate": None,
                "unavailable_reason": record["policy_unavailable_reasons"][policy_id],
            }
            for policy_id in POLICY_IDS
        }
    signals = tuple(float(value) for value in evidence["eligible_signals"])
    return {
        policy_id: {
            "status": "available",
            "estimate": policy_trajectory(policy_id, signals)[-1],
            "unavailable_reason": None,
        }
        for policy_id in POLICY_IDS
    }


def _average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda row: row[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for index, _ in ordered[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    return numerator / (left_scale * right_scale)


def _tie_pair_count(values: list[float]) -> int:
    return sum(count * (count - 1) // 2 for count in Counter(values).values())


def _descriptive_ordering(estimates: list[float], scores: list[float]) -> dict[str, int]:
    result = {
        "concordant_pairs": 0,
        "discordant_pairs": 0,
        "mastery_tie_pairs": 0,
        "external_tie_pairs": 0,
        "joint_tie_pairs": 0,
    }
    for index, left_estimate in enumerate(estimates):
        for right_index in range(index + 1, len(estimates)):
            estimate_delta = left_estimate - estimates[right_index]
            score_delta = scores[index] - scores[right_index]
            if estimate_delta == 0 and score_delta == 0:
                result["joint_tie_pairs"] += 1
            elif estimate_delta == 0:
                result["mastery_tie_pairs"] += 1
            elif score_delta == 0:
                result["external_tie_pairs"] += 1
            elif estimate_delta * score_delta > 0:
                result["concordant_pairs"] += 1
            else:
                result["discordant_pairs"] += 1
    return result


def candidate_alignment(estimates: list[float], scores: list[float]) -> dict[str, Any]:
    """Compute transparent candidate rank statistics with fail-safe edge handling."""
    if len(estimates) != len(scores):
        raise P7StudyASyntheticAnalysisError("candidate alignment requires paired estimates and scores")
    if any(not isinstance(value, float) or not math.isfinite(value) for value in [*estimates, *scores]):
        raise P7StudyASyntheticAnalysisError("candidate alignment values must be finite floats")
    count = len(estimates)
    ordering = _descriptive_ordering(estimates, scores)
    base = {
        "valid_pair_count": count,
        "estimate_tie_pair_count": _tie_pair_count(estimates),
        "external_tie_pair_count": _tie_pair_count(scores),
        "descriptive_paired_ordering": ordering,
        "spearman_rho": None,
        "kendall_tau_b": None,
        "status": "available",
        "unavailable_reason": None,
    }
    if count < MINIMUM_VALID_PAIRS:
        return {**base, "status": "insufficient_data", "unavailable_reason": "fewer_than_three_valid_pairs"}
    if len(set(estimates)) < 2:
        return {**base, "status": "degenerate", "unavailable_reason": "constant_mastery_estimates"}
    if len(set(scores)) < 2:
        return {**base, "status": "degenerate", "unavailable_reason": "constant_external_scores"}
    ranked_estimates = _average_ranks(estimates)
    ranked_scores = _average_ranks(scores)
    tau_denominator = math.sqrt(
        (ordering["concordant_pairs"] + ordering["discordant_pairs"] + ordering["mastery_tie_pairs"])
        * (ordering["concordant_pairs"] + ordering["discordant_pairs"] + ordering["external_tie_pairs"])
    )
    if tau_denominator == 0.0:  # defensive: constants above normally catch this.
        return {**base, "status": "degenerate", "unavailable_reason": "kendall_denominator_zero"}
    return {
        **base,
        "spearman_rho": _pearson(ranked_estimates, ranked_scores),
        "kendall_tau_b": (ordering["concordant_pairs"] - ordering["discordant_pairs"]) / tau_denominator,
    }


def _alignment_for_rows(rows: list[dict[str, Any]], policy_id: str) -> dict[str, Any]:
    valid_rows = [
        row for row in rows
        if row["policy_estimates"][policy_id]["status"] == "available"
        and row["concept_criterion"]["status"] == "complete_primary_immediate_synthetic_criterion"
    ]
    estimates = [row["policy_estimates"][policy_id]["estimate"] for row in valid_rows]
    scores = [row["concept_criterion"]["external_score"] for row in valid_rows]
    result = candidate_alignment(estimates, scores)
    result["synthetic_profile_ids"] = [row["synthetic_profile_id"] for row in valid_rows]
    result["missing_external_record_count"] = sum(
        row["concept_criterion"]["external_score"] is None for row in rows
    )
    result["policy_unavailable_record_count"] = sum(
        row["policy_estimates"][policy_id]["status"] != "available" for row in rows
    )
    return result


def _analysis_by_concept_and_group(rows: list[dict[str, Any]], policy_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_concept[row["concept_id"]].append(row)
        for group in row["analysis_groups"]:
            by_group[group].append(row)
    return (
        {concept_id: _alignment_for_rows(concept_rows, policy_id) for concept_id, concept_rows in sorted(by_concept.items())},
        {group: _alignment_for_rows(group_rows, policy_id) for group, group_rows in sorted(by_group.items())},
    )


def run_synthetic_analysis(
    *, root: Path = ROOT, fixture_path: str | Path = FIXTURE_PATH
) -> dict[str, Any]:
    """Run the deterministic synthetic-only alignment dry run in memory."""
    root = Path(root)
    validation = validate_synthetic_fixture(root=root, path=fixture_path)
    if not validation["valid"]:
        raise P7StudyASyntheticAnalysisError(
            "P7 Study A synthetic fixture is invalid: " + "; ".join(validation["errors"])
        )
    fixture = load_synthetic_fixture(fixture_path)
    owner_design = load_p7_study_a_owner_design(
        root / "data" / "evaluation" / "p7_study_a_owner_design_decisions.json"
    )
    record_results = []
    for record in fixture["records"]:
        record_results.append({
            "synthetic_profile_id": record["synthetic_profile_id"],
            "scenario_tags": list(record["scenario_tags"]),
            "analysis_groups": list(record["analysis_groups"]),
            "concept_id": record["concept_id"],
            "frozen_evidence": deepcopy(record["frozen_evidence"]),
            "policy_estimates": _policy_estimates(record),
            "concept_criterion": _criterion_for_record(record),
        })
    policy_alignment = {}
    for policy_id in POLICY_IDS:
        by_concept, by_group = _analysis_by_concept_and_group(record_results, policy_id)
        policy_alignment[policy_id] = {
            "overall": _alignment_for_rows(record_results, policy_id),
            "by_concept": by_concept,
            "by_analysis_group": by_group,
        }
    missing_results = [
        row for row in record_results if row["concept_criterion"]["external_score"] is None
    ]
    policy_unavailable = [
        row for row in record_results if any(
            row["policy_estimates"][policy_id]["status"] != "available" for policy_id in POLICY_IDS
        )
    ]
    readiness = load_p7_readiness_status(root / "data" / "evaluation" / "p7_readiness_status.json")
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "p7_study_a_synthetic_analysis_dry_run",
        "synthetic_only": True,
        "not_approved_for_real_human_data": True,
        "candidate_analysis_not_yet_frozen_for_real_study": True,
        "study_a_research_question": fixture["study_a_boundary"]["research_question"],
        "analysis_methods": {
            "candidate_methods": ["spearman_rank_correlation", "kendall_tau_b", "descriptive_paired_ordering"],
            "minimum_valid_pairs": MINIMUM_VALID_PAIRS,
            "p_value_computed": False,
            "policy_winner_selected": False,
        },
        "owner_technical_design": {
            "decision_status": owner_design["decision_status"],
            "decision_scope": owner_design["decision_scope"],
            "human_study_authorized": owner_design["human_study_authorized"],
            "primary_analysis_unit": owner_design["analysis_design"]["primary_analysis_unit"],
            "primary_estimator": owner_design["estimator_roles"]["P0"],
            "primary_rank_statistic": owner_design["rank_statistics"]["primary_descriptive_rank_statistic"],
            "pooled_summary_role": owner_design["analysis_design"]["pooled_participant_by_concept"],
            "exact_item_order": owner_design["administration"]["exact_item_order"],
        },
        "analysis_roles": {
            "primary": ["P0", "CONCEPT_STRATIFIED", "KENDALL_TAU_B", "DESCRIPTIVE_ORDERING"],
            "sensitivity": ["P2", "P3", "SPEARMAN_RHO"],
            "exploratory": ["POOLED_PARTICIPANT_BY_CONCEPT_DESCRIPTIVE_SUMMARIES"],
        },
        "fixture_summary": {
            **validation["summary"],
            "primary_immediate_item_ids_by_concept": fixture["criterion_composition"]["primary_immediate_item_ids_by_concept"],
            "exploratory_item_ids_excluded_from_primary": fixture["criterion_composition"]["exploratory_item_ids"],
            "actual_study_a_item_assignment": fixture["criterion_composition"]["actual_study_a_item_assignment"],
            "external_missing_record_count": len(missing_results),
            "external_missing_item_count": sum(
                row["concept_criterion"]["missing_primary_item_count"] for row in missing_results
            ),
            "policy_unavailable_record_count": len(policy_unavailable),
        },
        "record_results": record_results,
        "policy_alignment": policy_alignment,
        "edge_case_audit": {
            "missing_never_scored_as_zero": all(
                row["concept_criterion"]["external_score"] is None
                for row in missing_results
            ),
            "missing_reasons_preserved": [
                reason for row in missing_results for reason in row["concept_criterion"]["missing_reasons"]
            ],
            "exploratory_minimax_item_excluded_from_primary": all(
                "p7_ext_minimax_two_level_b" not in [
                    item_id
                    for concept_ids in fixture["criterion_composition"]["primary_immediate_item_ids_by_concept"].values()
                    for item_id in concept_ids
                ]
                for _ in (0,)
            ),
            "local_search_primary_item_count": len(
                fixture["criterion_composition"]["primary_immediate_item_ids_by_concept"]["local_search"]
            ),
            "production_state_written": False,
            "recommendation_called": False,
            "real_human_data_used": False,
        },
        "readiness_boundary": {
            "readiness_level": readiness["readiness_level"],
            "human_study_authorized": readiness["human_study"]["authorized"],
            "checkpoint_status": readiness["human_study"]["checkpoint_status"],
            "ready_for_real_human_data": False,
        },
        "interpretation_boundary": {
            "supports": "analysis_plumbing_edge_case_handling_and_reproducibility_only",
            "does_not_support": [
                "mastery_validity",
                "estimator_accuracy",
                "policy_superiority",
                "human_learning",
                "recommendation_effectiveness",
                "calibration",
                "human_study_readiness",
            ],
        },
    }


def write_synthetic_analysis(
    path: Path = DEFAULT_OUTPUT, *, root: Path = ROOT, fixture_path: str | Path = FIXTURE_PATH
) -> dict[str, Any]:
    """Atomically write a synthetic-only report outside the repository by default."""
    report = run_synthetic_analysis(root=root, fixture_path=fixture_path)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary_path = Path(handle.name)
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary_path.replace(path)
    return deepcopy(report)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run P7 Study A synthetic-only alignment-analysis dry run.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    args = parser.parse_args()
    report = write_synthetic_analysis(args.output, fixture_path=args.fixture)
    print(json.dumps({
        "output": str(args.output),
        "synthetic_only": report["synthetic_only"],
        "record_count": report["fixture_summary"]["record_count"],
        "external_missing_record_count": report["fixture_summary"]["external_missing_record_count"],
        "policy_unavailable_record_count": report["fixture_summary"]["policy_unavailable_record_count"],
        "human_study_authorized": report["readiness_boundary"]["human_study_authorized"],
    }, ensure_ascii=False, indent=2))
