"""Offline invariants for the P7 Study A owner technical-design freeze."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from tools.validate_p7_assessment_candidates import load_p7_candidate_document
from tools.validate_p7_readiness_status import load_p7_readiness_status
from tools.validate_p7_study_a_owner_design import (
    DECISION_PATH,
    load_p7_study_a_owner_design,
    validate_p7_study_a_owner_design,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_decision(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "owner-design.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_owner_design_record_freezes_exactly_od_01_through_od_10():
    report = validate_p7_study_a_owner_design(root=ROOT)

    assert report["valid"] is True
    assert report["summary"] == {
        "decision_status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "readiness_level": 2,
        "human_study_authorized": False,
        "primary_item_count": 10,
        "selected_concept_count": 6,
        "exact_item_order": "PENDING_PRE_STUDY_FREEZE",
        "advisor_status": "ADVISOR_CONFIRMATION_REQUIRED",
        "institution_status": "INSTITUTIONAL_VERIFICATION_REQUIRED",
    }
    document = load_p7_study_a_owner_design()
    assert document["decision_scope"] == "STUDY_A_TECHNICAL_DESIGN_ONLY"
    assert document["owner_decision_recorded"] is True
    assert {entry["decision_id"] for entry in document["decisions"]} == {
        f"OD-{index:02d}" for index in range(1, 11)
    }
    assert {entry["status"] for entry in document["decisions"]} == {
        "OWNER_TECHNICAL_DESIGN_FROZEN"
    }


def test_primary_manifest_retains_local_search_and_excludes_minimax_transfer():
    document = load_p7_study_a_owner_design()
    primary = document["primary_instrument"]["primary_item_ids_by_concept"]

    assert sum(len(item_ids) for item_ids in primary.values()) == 10
    assert primary["local_search"] == ["p7_ext_local_search_neighbor_a"]
    assert primary["minimax_search"] == ["p7_ext_minimax_min_node_a"]
    assert "p7_ext_minimax_two_level_b" not in {
        item_id for item_ids in primary.values() for item_id in item_ids
    }
    assert document["local_search"] == {
        "status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "primary_item_id": "p7_ext_local_search_neighbor_a",
        "external_concept_performance": "CORRECT_OVER_1",
        "representation_slot_status": "LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE",
        "second_replacement_item": "NOT_CREATED",
    }
    assert document["minimax_transfer"]["study_a_administration"] == (
        "NOT_ADMINISTERED_IN_PRIMARY_STUDY_A"
    )


def test_estimator_analysis_rank_missing_and_administration_roles_are_frozen():
    document = load_p7_study_a_owner_design()

    assert {
        key: document["estimator_roles"][key] for key in ("P0", "P1", "P2", "P3")
    } == {
        "P0": "PRIMARY_ESTIMATOR",
        "P1": "MATHEMATICAL_REFERENCE_ONLY",
        "P2": "PRESPECIFIED_SENSITIVITY_ESTIMATOR",
        "P3": "PRESPECIFIED_SENSITIVITY_ESTIMATOR",
    }
    assert document["analysis_design"]["primary_analysis_unit"] == "CONCEPT_STRATIFIED"
    assert document["analysis_design"]["pooled_participant_by_concept"] == "EXPLORATORY_ONLY"
    assert document["analysis_design"]["learner_level_cross_concept_aggregation"] == (
        "NOT_ADOPTED_FOR_PRIMARY"
    )
    assert document["rank_statistics"]["primary_descriptive_rank_statistic"] == "KENDALL_TAU_B"
    assert document["rank_statistics"]["prespecified_sensitivity_statistic"] == "SPEARMAN_RHO"
    assert document["rank_statistics"]["descriptive_ordering_required"] is True
    assert document["missing_data"]["missing_value"] is None
    assert document["missing_data"]["missing_is_zero"] is False
    assert document["missing_data"]["withdrawal_data_handling"] == (
        "INSTITUTIONAL_VERIFICATION_REQUIRED"
    )
    assert document["administration"]["all_participants_receive_same_primary_items"] is True
    assert document["administration"]["partial_administration"] == "NOT_ADOPTED"
    assert document["administration"]["primary_item_attempts"] == "SINGLE_ATTEMPT"
    assert document["administration"]["immediate_replay_as_independent_criterion"] is False
    assert document["administration"]["exact_item_order"] == "PENDING_PRE_STUDY_FREEZE"


def test_readiness_and_external_candidate_bank_remain_isolated_inputs():
    readiness = load_p7_readiness_status()
    candidates = load_p7_candidate_document()

    assert readiness["readiness_level"] == 2
    assert readiness["human_study"]["authorized"] is False
    assert readiness["production_isolation"] == {
        "production_template_count": 28,
        "active_production_candidate_count": 0,
        "blocked_production_slot_count": 1,
        "concept_count": 26,
        "registered_in_production": False,
        "writes_mastery": False,
        "writes_learner_state": False,
        "writes_recommendation": False,
    }
    assert candidates["assessment_status"] == "pending_owner_review"
    assert len(candidates["items"]) == 11
    assert all(item["human_review_status"] == "pending_owner_review" for item in candidates["items"])


def test_validator_fails_closed_for_unsafe_or_unfrozen_mutations(tmp_path):
    source = load_p7_study_a_owner_design(DECISION_PATH)

    unauthorized = deepcopy(source)
    unauthorized["human_study_authorized"] = True
    report = validate_p7_study_a_owner_design(root=ROOT, path=_write_decision(tmp_path, unauthorized))
    assert report["valid"] is False
    assert "human_study_authorized must remain false" in report["errors"]

    transfer_contamination = deepcopy(source)
    transfer_contamination["primary_instrument"]["primary_item_ids_by_concept"]["minimax_search"].append(
        "p7_ext_minimax_two_level_b"
    )
    transfer_contamination["primary_instrument"]["primary_item_count"] = 11
    report = validate_p7_study_a_owner_design(
        root=ROOT, path=_write_decision(tmp_path, transfer_contamination)
    )
    assert report["valid"] is False
    assert any("primary instrument IDs" in error for error in report["errors"])

    premature_order = deepcopy(source)
    premature_order["administration"]["exact_item_order"] = ["p7_ext_bfs_depth_claim_a"]
    report = validate_p7_study_a_owner_design(root=ROOT, path=_write_decision(tmp_path, premature_order))
    assert report["valid"] is False
    assert any("exact-order" in error for error in report["errors"])

    resolved_withdrawal = deepcopy(source)
    resolved_withdrawal["missing_data"]["withdrawal_data_handling"] = "DELETE_ALL_DATA"
    report = validate_p7_study_a_owner_design(root=ROOT, path=_write_decision(tmp_path, resolved_withdrawal))
    assert report["valid"] is False
    assert any("withdrawal handling" in error for error in report["errors"])
