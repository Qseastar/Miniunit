"""Offline invariants for the P7 Study A synthetic analysis dry run."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tools.run_p7_study_a_synthetic_analysis import (
    FIXTURE_PATH,
    P0,
    P2,
    P3,
    P7StudyASyntheticAnalysisError,
    candidate_alignment,
    load_synthetic_fixture,
    run_synthetic_analysis,
    validate_synthetic_fixture,
    write_synthetic_analysis,
)
from tools.validate_p7_assessment_candidates import validate_p7_candidate_document
from tools.validate_p7_readiness_status import validate_p7_readiness_status


ROOT = Path(__file__).resolve().parents[1]


def _rows(report):
    return {row["synthetic_profile_id"]: row for row in report["record_results"]}


def _write_fixture(tmp_path: Path, fixture: dict) -> Path:
    path = tmp_path / "synthetic-fixture.json"
    path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    return path


def _all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


def test_fixture_is_deterministic_synthetic_only_and_privacy_minimal():
    fixture = load_synthetic_fixture(FIXTURE_PATH)
    report = validate_synthetic_fixture(root=ROOT)
    assert report["valid"] is True
    assert report["summary"] == {
        "record_count": 18,
        "policy_ids": [P0, P2, P3],
        "minimum_valid_pairs": 3,
        "synthetic_only": True,
        "not_approved_for_real_human_data": True,
    }
    assert fixture["synthetic_only"] is True
    assert fixture["not_approved_for_real_human_data"] is True
    assert fixture["candidate_analysis_not_yet_frozen_for_real_study"] is True
    assert [row["synthetic_profile_id"] for row in fixture["records"]] == [
        f"synthetic_{index:03d}" for index in range(1, 19)
    ]
    forbidden = {
        "name", "student_id", "email", "ip", "user_agent", "learner_uuid",
        "qa", "question", "question_text", "prompt", "pdf", "timestamp",
        "grade", "api_key", "authorization", "secret",
    }
    assert not forbidden & set(_all_keys(fixture))


def test_policies_are_reproducible_from_same_frozen_evidence_without_production_side_effects():
    first = run_synthetic_analysis(root=ROOT)
    second = run_synthetic_analysis(root=ROOT)
    assert first == second
    rows = _rows(first)
    assert rows["synthetic_001"]["policy_estimates"][P0] == {
        "status": "available", "estimate": pytest.approx(0.5775), "unavailable_reason": None,
    }
    assert rows["synthetic_001"]["policy_estimates"][P2]["estimate"] == pytest.approx(0.75)
    assert rows["synthetic_001"]["policy_estimates"][P3]["estimate"] == pytest.approx(0.510867)
    assert first["edge_case_audit"]["production_state_written"] is False
    assert first["edge_case_audit"]["recommendation_called"] is False
    assert first["edge_case_audit"]["real_human_data_used"] is False
    assert first["owner_technical_design"] == {
        "decision_status": "OWNER_TECHNICAL_DESIGN_FROZEN",
        "decision_scope": "STUDY_A_TECHNICAL_DESIGN_ONLY",
        "human_study_authorized": False,
        "primary_analysis_unit": "CONCEPT_STRATIFIED",
        "primary_estimator": "PRIMARY_ESTIMATOR",
        "primary_rank_statistic": "KENDALL_TAU_B",
        "pooled_summary_role": "EXPLORATORY_ONLY",
        "exact_item_order": "PENDING_PRE_STUDY_FREEZE",
    }
    assert first["analysis_roles"] == {
        "primary": ["P0", "CONCEPT_STRATIFIED", "KENDALL_TAU_B", "DESCRIPTIVE_ORDERING"],
        "sensitivity": ["P2", "P3", "SPEARMAN_RHO"],
        "exploratory": ["POOLED_PARTICIPANT_BY_CONCEPT_DESCRIPTIVE_SUMMARIES"],
    }


def test_missing_external_results_remain_null_with_reason_and_create_no_alignment_pair():
    report = run_synthetic_analysis(root=ROOT)
    rows = _rows(report)
    for profile_id in ("synthetic_011", "synthetic_012"):
        criterion = rows[profile_id]["concept_criterion"]
        assert criterion["status"] == "external_missing_no_primary_alignment_pair"
        assert criterion["external_score"] is None
        assert criterion["missing_reasons"]
        assert all(reason == "synthetic_external_not_administered" for reason in criterion["missing_reasons"])
    assert report["fixture_summary"]["external_missing_record_count"] == 2
    assert report["fixture_summary"]["external_missing_item_count"] == 3
    assert report["edge_case_audit"]["missing_never_scored_as_zero"] is True
    assert report["policy_alignment"][P0]["by_analysis_group"]["missing_external_boundary"] == {
        "valid_pair_count": 0,
        "estimate_tie_pair_count": 0,
        "external_tie_pair_count": 0,
        "descriptive_paired_ordering": {
            "concordant_pairs": 0,
            "discordant_pairs": 0,
            "mastery_tie_pairs": 0,
            "external_tie_pairs": 0,
            "joint_tie_pairs": 0,
        },
        "spearman_rho": None,
        "kendall_tau_b": None,
        "status": "insufficient_data",
        "unavailable_reason": "fewer_than_three_valid_pairs",
        "synthetic_profile_ids": [],
        "missing_external_record_count": 2,
        "policy_unavailable_record_count": 0,
    }


def test_policy_unavailability_is_explicit_not_fabricated_as_zero():
    report = run_synthetic_analysis(root=ROOT)
    row = _rows(report)["synthetic_013"]
    assert row["concept_criterion"]["external_score"] == pytest.approx(0.5)
    assert all(row["policy_estimates"][policy] == {
        "status": "unavailable",
        "estimate": None,
        "unavailable_reason": "synthetic_no_frozen_eligible_evidence",
    } for policy in (P0, P2, P3))
    assert report["fixture_summary"]["policy_unavailable_record_count"] == 1


def test_small_n_ties_and_degenerate_values_fail_safe_without_fake_correlation():
    report = run_synthetic_analysis(root=ROOT)
    p0 = report["policy_alignment"][P0]
    assert p0["by_concept"]["minimax_search"]["status"] == "insufficient_data"
    assert p0["by_concept"]["minimax_search"]["unavailable_reason"] == "fewer_than_three_valid_pairs"
    assert p0["by_analysis_group"]["constant_external_boundary"]["status"] == "degenerate"
    assert p0["by_analysis_group"]["constant_external_boundary"]["unavailable_reason"] == "constant_external_scores"
    tied = candidate_alignment([0.2, 0.2, 0.8], [0.0, 1.0, 1.0])
    assert tied["status"] == "available"
    assert tied["estimate_tie_pair_count"] == 1
    assert tied["external_tie_pair_count"] == 1
    assert tied["spearman_rho"] is not None
    assert tied["kendall_tau_b"] is not None


def test_local_search_single_item_and_minimax_transfer_remain_separate_from_primary():
    report = run_synthetic_analysis(root=ROOT)
    rows = _rows(report)
    local = rows["synthetic_004"]["concept_criterion"]
    assert local["external_correct"] == 0
    assert local["external_total"] == 1
    assert local["external_score"] == 0.0
    minimax = rows["synthetic_005"]["concept_criterion"]
    assert minimax["external_correct"] == 1
    assert minimax["external_total"] == 1
    assert minimax["external_score"] == 1.0
    assert minimax["exploratory_item_ids_excluded"] == ["p7_ext_minimax_two_level_b"]
    assert report["fixture_summary"]["exploratory_item_ids_excluded_from_primary"] == [
        "p7_ext_minimax_two_level_b"
    ]
    assert report["edge_case_audit"]["local_search_primary_item_count"] == 1
    assert report["edge_case_audit"]["exploratory_minimax_item_excluded_from_primary"] is True


def test_synthetic_patterns_demonstrate_plumbing_not_a_policy_winner():
    report = run_synthetic_analysis(root=ROOT)
    for policy in (P0, P2, P3):
        positive = report["policy_alignment"][policy]["by_analysis_group"]["positive_monotonic_pattern"]
        inverse = report["policy_alignment"][policy]["by_analysis_group"]["inverse_pattern"]
        assert positive["status"] == "available"
        assert positive["spearman_rho"] > 0.9
        assert inverse["status"] == "available"
        assert inverse["spearman_rho"] == pytest.approx(-1.0)
    assert report["analysis_methods"]["policy_winner_selected"] is False
    assert report["candidate_analysis_not_yet_frozen_for_real_study"] is True
    assert report["fixture_summary"]["actual_study_a_item_assignment"] == (
        "OWNER_TECHNICAL_DESIGN_FROZEN_NOT_HUMAN_STUDY_RELEASE"
    )
    assert "policy_superiority" in report["interpretation_boundary"]["does_not_support"]


def test_validator_rejects_real_data_like_field_or_primary_exploratory_contamination(tmp_path):
    fixture = load_synthetic_fixture(FIXTURE_PATH)
    privacy_mutation = deepcopy(fixture)
    privacy_mutation["records"][0]["email"] = "not-allowed@example.invalid"
    report = validate_synthetic_fixture(root=ROOT, path=_write_fixture(tmp_path, privacy_mutation))
    assert report["valid"] is False
    assert any("invalid schema" in error for error in report["errors"])

    contamination = deepcopy(fixture)
    minimax = contamination["records"][4]["external_item_results"][1]
    minimax["criterion_role"] = "synthetic_primary_immediate"
    report = validate_synthetic_fixture(root=ROOT, path=_write_fixture(tmp_path, contamination))
    assert report["valid"] is False
    assert any("exploratory_transfer" in error for error in report["errors"])


def test_invalid_fixture_fails_before_analysis_and_output_stays_synthetic(tmp_path):
    fixture = load_synthetic_fixture(FIXTURE_PATH)
    invalid = deepcopy(fixture)
    invalid["synthetic_only"] = False
    path = _write_fixture(tmp_path, invalid)
    with pytest.raises(P7StudyASyntheticAnalysisError, match="synthetic_only"):
        run_synthetic_analysis(root=ROOT, fixture_path=path)

    output = tmp_path / "analysis.json"
    report = write_synthetic_analysis(output, root=ROOT)
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["synthetic_only"] is True
    assert report["not_approved_for_real_human_data"] is True
    assert report["readiness_boundary"] == {
        "readiness_level": 2,
        "human_study_authorized": False,
        "checkpoint_status": "UNRESOLVED",
        "ready_for_real_human_data": False,
    }


def test_current_bank_and_level2_status_remain_the_independent_validated_inputs():
    candidate = validate_p7_candidate_document(root=ROOT)
    readiness = validate_p7_readiness_status(root=ROOT)
    assert candidate["valid"] is True
    assert candidate["summary"]["item_count"] == 11
    assert readiness["valid"] is True
    assert readiness["summary"] == {
        "readiness_level": 2,
        "active_external_item_count": 11,
        "selected_concept_count": 6,
        "human_study_authorized": False,
        "human_study_checkpoint_status": "UNRESOLVED",
    }
    bank_path = ROOT / "data" / "evaluation" / "p7_external_assessment_candidates.json"
    assert hashlib.sha256(bank_path.read_bytes()).hexdigest() == (
        "38c5538b74da74b38027e1b584ebf0ccc618dba503e3e4025b06c9100d0cf1c5"
    )
