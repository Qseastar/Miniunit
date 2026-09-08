"""Validate the frozen P7 Study A owner technical-design record offline.

This validator checks only research-design consistency.  It never authorizes a
human study, creates participant data, imports production services, or writes
learner state.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_p7_assessment_candidates import (  # noqa: E402
    load_p7_candidate_document,
    validate_p7_candidate_document,
)
from tools.validate_p7_readiness_status import (  # noqa: E402
    load_p7_readiness_status,
    validate_p7_readiness_status,
)


DECISION_PATH = ROOT / "data" / "evaluation" / "p7_study_a_owner_design_decisions.json"
_TOP_LEVEL_KEYS = {
    "schema_version",
    "record_type",
    "decision_status",
    "decision_scope",
    "owner_decision_recorded",
    "human_study_authorized",
    "readiness_level",
    "study_a_boundary",
    "primary_instrument",
    "local_search",
    "minimax_transfer",
    "estimator_roles",
    "analysis_design",
    "rank_statistics",
    "missing_data",
    "administration",
    "version_freeze_contract",
    "reporting_hierarchy",
    "decisions",
    "pending_external_dependencies",
}
_PRIMARY_ITEMS_BY_CONCEPT = {
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
_EXCLUDED_TRANSFER_ID = "p7_ext_minimax_two_level_b"
_EXPECTED_DECISION_IDS = {f"OD-{index:02d}" for index in range(1, 11)}
_DEPENDENCY_STATUSES = {
    "ADVISOR_CONFIRMATION_REQUIRED",
    "INSTITUTIONAL_VERIFICATION_REQUIRED",
}


class P7StudyAOwnerDesignValidationError(ValueError):
    """Raised when the owner technical-design record is not valid JSON."""


def load_p7_study_a_owner_design(path: str | Path = DECISION_PATH) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise P7StudyAOwnerDesignValidationError("P7 Study A owner design record is missing.") from error
    except json.JSONDecodeError as error:
        raise P7StudyAOwnerDesignValidationError("P7 Study A owner design record is invalid JSON.") from error
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        raise P7StudyAOwnerDesignValidationError("P7 Study A owner design record has an invalid top-level schema.")
    return document


def _expected_primary_ids() -> set[str]:
    return {item_id for ids in _PRIMARY_ITEMS_BY_CONCEPT.values() for item_id in ids}


def _has_exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def validate_p7_study_a_owner_design(
    *, root: Path = ROOT, path: str | Path = DECISION_PATH
) -> dict[str, Any]:
    """Return a fail-closed consistency report for the frozen owner decisions."""
    root = Path(root)
    document = load_p7_study_a_owner_design(path)
    errors: list[str] = []

    if document["schema_version"] != 1:
        errors.append("schema_version must be 1")
    if document["record_type"] != "p7_study_a_owner_technical_design_decisions":
        errors.append("record_type is invalid")
    if document["decision_status"] != "OWNER_TECHNICAL_DESIGN_FROZEN":
        errors.append("decision_status must be OWNER_TECHNICAL_DESIGN_FROZEN")
    if document["decision_scope"] != "STUDY_A_TECHNICAL_DESIGN_ONLY":
        errors.append("decision_scope must remain STUDY_A_TECHNICAL_DESIGN_ONLY")
    if document["owner_decision_recorded"] is not True:
        errors.append("owner_decision_recorded must be true")
    if document["human_study_authorized"] is not False:
        errors.append("human_study_authorized must remain false")
    if document["readiness_level"] != 2:
        errors.append("readiness_level must remain 2")

    readiness = validate_p7_readiness_status(root=root)
    candidate_report = validate_p7_candidate_document(root=root)
    status = load_p7_readiness_status(root / "data" / "evaluation" / "p7_readiness_status.json")
    candidate_document = load_p7_candidate_document(
        root / "data" / "evaluation" / "p7_external_assessment_candidates.json"
    )
    if not readiness["valid"]:
        errors.append("P7 readiness status must validate")
    elif status["readiness_level"] != 2 or status["human_study"]["authorized"] is not False:
        errors.append("readiness status must remain Level 2 with human authorization false")
    if not candidate_report["valid"]:
        errors.append("P7 external candidate bank must validate")
    active_items = {item["assessment_item_id"]: item["concept_id"] for item in candidate_document["items"]}
    if len(active_items) != 11 or len(candidate_document["study_scope"]["selected_concept_ids"]) != 6:
        errors.append("current external bank must remain 11 items across 6 concepts")

    boundary = document["study_a_boundary"]
    if not _has_exact_keys(boundary, {"research_question", "study_b_recommendation_intervention", "forbidden_claims"}):
        errors.append("study_a_boundary schema is invalid")
    else:
        if boundary["research_question"] != (
            "frozen_estimate_rank_monotonic_alignment_with_independent_course_grounded_performance_criterion"
        ):
            errors.append("study research question is invalid")
        if boundary["study_b_recommendation_intervention"] != "SEPARATE_NOT_IN_SCOPE":
            errors.append("Study B must remain separate")
        if not isinstance(boundary["forbidden_claims"], list) or not boundary["forbidden_claims"]:
            errors.append("forbidden claims must be a non-empty list")

    primary = document["primary_instrument"]
    if not _has_exact_keys(primary, {
        "status", "primary_item_ids_by_concept", "primary_item_count", "reporting_structure",
        "cross_concept_pooled_summary_role", "limitations",
    }):
        errors.append("primary_instrument schema is invalid")
    else:
        expected_mapping = {key: list(value) for key, value in _PRIMARY_ITEMS_BY_CONCEPT.items()}
        if primary["status"] != "OWNER_TECHNICAL_DESIGN_FROZEN":
            errors.append("primary instrument must be frozen")
        if primary["primary_item_ids_by_concept"] != expected_mapping:
            errors.append("primary instrument IDs must match the approved 10-item manifest exactly")
        if primary["primary_item_count"] != 10:
            errors.append("primary instrument must contain exactly 10 items")
        if primary["reporting_structure"] != "CONCEPT_SPECIFIC_CONCEPT_STRATIFIED":
            errors.append("primary reporting must remain concept-specific concept-stratified")
        if primary["cross_concept_pooled_summary_role"] != "EXPLORATORY_ONLY":
            errors.append("pooled cross-concept summary must remain exploratory only")
        if not isinstance(primary["limitations"], list) or "LOCAL_SEARCH_CORRECT_OVER_1" not in primary["limitations"]:
            errors.append("Local Search measurement-resolution limitation must be retained")
    primary_ids = _expected_primary_ids()
    if not primary_ids <= set(active_items):
        errors.append("frozen primary instrument must contain only active external items")
    if _EXCLUDED_TRANSFER_ID in primary_ids:
        errors.append("Minimax transfer must not enter the primary instrument")

    local = document["local_search"]
    if not _has_exact_keys(local, {
        "status", "primary_item_id", "external_concept_performance", "representation_slot_status",
        "second_replacement_item",
    }) or local != {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "primary_item_id": "p7_ext_local_search_neighbor_a",
        "external_concept_performance": "CORRECT_OVER_1",
        "representation_slot_status": "LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE",
        "second_replacement_item": "NOT_CREATED",
    }:
        errors.append("Local Search frozen design is invalid")

    transfer = document["minimax_transfer"]
    if not _has_exact_keys(transfer, {"status", "item_id", "historical_role", "study_a_administration", "primary_item_id"}) or transfer != {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "item_id": _EXCLUDED_TRANSFER_ID,
        "historical_role": "TRANSFER_EXPLORATORY_ONLY",
        "study_a_administration": "NOT_ADMINISTERED_IN_PRIMARY_STUDY_A",
        "primary_item_id": "p7_ext_minimax_min_node_a",
    }:
        errors.append("Minimax transfer boundary is invalid")

    estimators = document["estimator_roles"]
    if not _has_exact_keys(estimators, {"status", "P0", "P1", "P2", "P3", "p0_formula", "p2_definition", "p3_definition", "policy_winner_selection"}):
        errors.append("estimator_roles schema is invalid")
    elif {key: estimators[key] for key in ("status", "P0", "P1", "P2", "P3", "policy_winner_selection")} != {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "P0": "PRIMARY_ESTIMATOR",
        "P1": "MATHEMATICAL_REFERENCE_ONLY",
        "P2": "PRESPECIFIED_SENSITIVITY_ESTIMATOR",
        "P3": "PRESPECIFIED_SENSITIVITY_ESTIMATOR",
        "policy_winner_selection": "FORBIDDEN",
    }:
        errors.append("estimator roles are invalid")

    analysis = document["analysis_design"]
    if not _has_exact_keys(analysis, {"status", "primary_analysis_unit", "primary_supporting_description", "pooled_participant_by_concept", "learner_level_cross_concept_aggregation", "cross_concept_weighting_rule"}) or {
        key: analysis.get(key) for key in ("status", "primary_analysis_unit", "primary_supporting_description", "pooled_participant_by_concept", "learner_level_cross_concept_aggregation", "cross_concept_weighting_rule")
    } != {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "primary_analysis_unit": "CONCEPT_STRATIFIED",
        "primary_supporting_description": "DESCRIPTIVE_ORDERING",
        "pooled_participant_by_concept": "EXPLORATORY_ONLY",
        "learner_level_cross_concept_aggregation": "NOT_ADOPTED_FOR_PRIMARY",
        "cross_concept_weighting_rule": "NOT_OWNER_APPROVED",
    }:
        errors.append("analysis design is invalid")

    ranks = document["rank_statistics"]
    if not _has_exact_keys(ranks, {"status", "primary_descriptive_rank_statistic", "prespecified_sensitivity_statistic", "descriptive_ordering_required", "required_counts", "minimum_valid_pairs_semantics"}) or {
        key: ranks.get(key) for key in ("status", "primary_descriptive_rank_statistic", "prespecified_sensitivity_statistic", "descriptive_ordering_required", "minimum_valid_pairs_semantics")
    } != {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "primary_descriptive_rank_statistic": "KENDALL_TAU_B",
        "prespecified_sensitivity_statistic": "SPEARMAN_RHO",
        "descriptive_ordering_required": True,
        "minimum_valid_pairs_semantics": "COMPUTATION_SAFETY_ONLY_NOT_SAMPLE_SIZE_OR_POWER",
    }:
        errors.append("rank-statistic roles are invalid")
    elif set(ranks["required_counts"]) != {
        "concordant_count", "discordant_count", "mastery_tie_count", "external_tie_count",
        "joint_tie_count", "valid_pair_count", "missing_count",
    }:
        errors.append("required descriptive counts are incomplete")

    missing = document["missing_data"]
    if not _has_exact_keys(missing, {"status", "missing_value", "missing_is_zero", "technical_missing_reason_vocabulary", "withdrawal_data_handling", "advisor_dependencies", "institutional_dependencies"}):
        errors.append("missing_data schema is invalid")
    else:
        required_reasons = {
            "instrument_not_administered", "participant_nonresponse", "technical_failure",
            "estimate_unavailable_no_eligible_evidence", "protocol_deviation", "other_controlled_reason",
        }
        if missing["status"] != "OWNER_TECHNICAL_DESIGN_FROZEN" or missing["missing_value"] is not None or missing["missing_is_zero"] is not False:
            errors.append("missing null semantics are invalid")
        if set(missing["technical_missing_reason_vocabulary"]) != required_reasons:
            errors.append("technical missing reason vocabulary is invalid")
        if missing["withdrawal_data_handling"] != "INSTITUTIONAL_VERIFICATION_REQUIRED":
            errors.append("withdrawal handling must remain institutionally unresolved")
        if not missing["advisor_dependencies"] or not missing["institutional_dependencies"]:
            errors.append("missing-data external dependencies must remain explicit")

    administration = document["administration"]
    if not _has_exact_keys(administration, {"status", "all_participants_receive_same_primary_items", "partial_administration", "participant_specific_subset", "balanced_incomplete_block", "primary_item_attempts", "immediate_replay_as_independent_criterion", "order_policy", "exact_item_order", "exact_order_dependencies"}):
        errors.append("administration schema is invalid")
    elif {
        key: administration.get(key) for key in ("status", "all_participants_receive_same_primary_items", "partial_administration", "participant_specific_subset", "balanced_incomplete_block", "primary_item_attempts", "immediate_replay_as_independent_criterion", "order_policy", "exact_item_order")
    } != {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "all_participants_receive_same_primary_items": True,
        "partial_administration": "NOT_ADOPTED",
        "participant_specific_subset": "NOT_ADOPTED",
        "balanced_incomplete_block": "NOT_ADOPTED",
        "primary_item_attempts": "SINGLE_ATTEMPT",
        "immediate_replay_as_independent_criterion": False,
        "order_policy": "OWNER_APPROVED_FIXED_PREGENERATED_CONSISTENT_ORDER",
        "exact_item_order": "PENDING_PRE_STUDY_FREEZE",
    } or set(administration["exact_order_dependencies"]) != _DEPENDENCY_STATUSES:
        errors.append("administration freeze or exact-order boundary is invalid")

    contract = document["version_freeze_contract"]
    if not _has_exact_keys(contract, {"status", "human_study_release", "required_evidence", "required_artifacts_before_any_real_study"}):
        errors.append("version freeze contract schema is invalid")
    elif contract["status"] != "TECHNICAL_DESIGN_FREEZE" or contract["human_study_release"] != "NOT_HUMAN_STUDY_RELEASE":
        errors.append("version freeze must remain technical-design only")
    elif set(contract["required_evidence"]) != {"commit_hash", "manifest", "sha256_checksum", "procedure_version", "analysis_version"}:
        errors.append("version freeze evidence contract is incomplete")

    reporting = document["reporting_hierarchy"]
    if not _has_exact_keys(reporting, {"status", "primary", "sensitivity", "exploratory", "not_reported_for_current_study_a", "required_limitations"}):
        errors.append("reporting hierarchy schema is invalid")
    else:
        if reporting["status"] != "OWNER_TECHNICAL_DESIGN_FROZEN":
            errors.append("reporting hierarchy must be frozen")
        if set(reporting["primary"]) != {
            "CONCEPT_LEVEL_CONCEPT_STRATIFIED_REPORTING", "P0_MASTERY_ESTIMATE", "KENDALL_TAU_B",
            "DESCRIPTIVE_ORDERING_TIES_VALID_N_MISSING_SUMMARIES",
        }:
            errors.append("primary reporting hierarchy is invalid")
        if set(reporting["sensitivity"]) != {"P2", "P3", "SPEARMAN_RHO"}:
            errors.append("sensitivity reporting hierarchy is invalid")
        if reporting["exploratory"] != ["POOLED_PARTICIPANT_BY_CONCEPT_VISUALIZATION_AND_DESCRIPTIVE_SUMMARIES"]:
            errors.append("exploratory reporting hierarchy is invalid")
        if set(reporting["not_reported_for_current_study_a"]) != {"DELAYED_RETENTION_CLAIM", "MINIMAX_TRANSFER_RESULT"}:
            errors.append("delayed and transfer boundaries are invalid")

    decisions = document["decisions"]
    if not isinstance(decisions, list) or {entry.get("decision_id") for entry in decisions if isinstance(entry, dict)} != _EXPECTED_DECISION_IDS or len(decisions) != 10:
        errors.append("OD-01 through OD-10 must exist exactly once")
    else:
        for entry in decisions:
            if not _has_exact_keys(entry, {"decision_id", "status", "owner_decision", "technical_effect", "pending_dependencies"}):
                errors.append(f"{entry.get('decision_id', 'unknown')} has an invalid schema")
                continue
            if entry["status"] != "OWNER_TECHNICAL_DESIGN_FROZEN":
                errors.append(f"{entry['decision_id']} must be frozen")
            if not isinstance(entry["owner_decision"], str) or not entry["owner_decision"].strip() or not isinstance(entry["technical_effect"], str) or not entry["technical_effect"].strip():
                errors.append(f"{entry['decision_id']} must record a non-empty decision and effect")
            if not isinstance(entry["pending_dependencies"], list) or not set(entry["pending_dependencies"]) <= _DEPENDENCY_STATUSES:
                errors.append(f"{entry['decision_id']} has invalid pending dependencies")

    dependencies = document["pending_external_dependencies"]
    if not _has_exact_keys(dependencies, {"advisor", "institution"}):
        errors.append("pending external dependencies schema is invalid")
    else:
        for key, required_status in (("advisor", "ADVISOR_CONFIRMATION_REQUIRED"), ("institution", "INSTITUTIONAL_VERIFICATION_REQUIRED")):
            entry = dependencies[key]
            if not _has_exact_keys(entry, {"status", "items"}) or entry["status"] != required_status or not isinstance(entry["items"], list) or not entry["items"]:
                errors.append(f"{key} dependencies must remain explicitly pending")

    return {
        "valid": not errors,
        "errors": errors,
        "summary": {
            "decision_status": document["decision_status"],
            "readiness_level": document["readiness_level"],
            "human_study_authorized": document["human_study_authorized"],
            "primary_item_count": len(primary_ids),
            "selected_concept_count": len(_PRIMARY_ITEMS_BY_CONCEPT),
            "exact_item_order": document["administration"].get("exact_item_order"),
            "advisor_status": document["pending_external_dependencies"]["advisor"].get("status"),
            "institution_status": document["pending_external_dependencies"]["institution"].get("status"),
        },
    }


if __name__ == "__main__":
    report = validate_p7_study_a_owner_design()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)
