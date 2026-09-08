"""P7 research protocol, candidate-bank and synthetic-pipeline invariants."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import load_diagnostic_templates
from tools.run_p7_synthetic_study import (
    FrozenEvidenceSequence,
    freeze_eligible_evidence,
    generate_participant_code,
    policy_estimates,
    run_synthetic_study,
    write_synthetic_export,
)
from tools.validate_p7_assessment_candidates import (
    CANDIDATE_PATH,
    build_production_capability_map,
    load_p7_candidate_document,
    validate_p7_candidate_document,
)


ROOT = Path(__file__).resolve().parents[1]


def _all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


def test_candidate_bank_is_pending_isolated_and_course_grounded():
    report = validate_p7_candidate_document(root=ROOT)
    assert report["valid"] is True
    assert report["summary"] == {
        "item_count": 11,
        "selected_concept_count": 6,
        "independent_or_complementary_item_count": 11,
        "too_similar_or_circular_item_count": 0,
        "external_criterion_blocked_concept_count": 5,
        "production_template_id_collisions": [],
    }
    document = load_p7_candidate_document(CANDIDATE_PATH)
    assert document["assessment_status"] == "pending_owner_review"
    assert all(item["human_review_status"] == "pending_owner_review" for item in document["items"])


def test_capability_map_derives_the_real_21_of_26_primary_coverage():
    capability_map = build_production_capability_map(ROOT)
    assert len(capability_map) == 26
    assert sum(row["production_template_count"] > 0 for row in capability_map) == 21
    assert sum(row["external_assessment_feasibility"] == "DO_NOT_USE" for row in capability_map) == 5
    bfs = next(row for row in capability_map if row["concept_id"] == "breadth_first_search")
    assert bfs["production_template_count"] == 2
    assert bfs["external_assessment_feasibility"] == "HIGH_FEASIBILITY"


def test_candidate_validator_rejects_production_id_collision_and_bad_source(tmp_path):
    document = load_p7_candidate_document(CANDIDATE_PATH)
    collision = deepcopy(document)
    collision["items"][0]["assessment_item_id"] = "verify_bfs_frontier_choice_v1"
    collision_path = tmp_path / "collision.json"
    collision_path.write_text(json.dumps(collision, ensure_ascii=False), encoding="utf-8")
    report = validate_p7_candidate_document(root=ROOT, path=collision_path)
    assert report["valid"] is False
    assert any("collides" in error for error in report["errors"])

    bad_source = deepcopy(document)
    bad_source["items"][0]["source_refs"][0]["page_start"] = 999
    bad_path = tmp_path / "bad-source.json"
    bad_path.write_text(json.dumps(bad_source, ensure_ascii=False), encoding="utf-8")
    report = validate_p7_candidate_document(root=ROOT, path=bad_path)
    assert report["valid"] is False
    assert any("does not match" in error for error in report["errors"])

    copied_options = deepcopy(document)
    copied_options["items"][0]["choices"] = [
        {"id": "a", "text": "A"},
        {"id": "b", "text": "B"},
        {"id": "c", "text": "C"},
    ]
    copied_options["items"][0]["expected_answer"] = {"choice_id": "a"}
    copied_options_path = tmp_path / "copied-options.json"
    copied_options_path.write_text(
        json.dumps(copied_options, ensure_ascii=False), encoding="utf-8"
    )
    report = validate_p7_candidate_document(root=ROOT, path=copied_options_path)
    assert report["valid"] is False
    assert any("duplicates a production option set" in error for error in report["errors"])


def test_external_candidate_ids_are_not_visible_to_production_template_registry():
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    production_ids = {
        item["id"]
        for item in load_diagnostic_templates(
            ROOT / "data" / "diagnostic_templates.json",
            valid_concept_ids={point["id"] for point in knowledge["knowledge_points"]},
        )["templates"]
    }
    external_ids = {
        item["assessment_item_id"]
        for item in load_p7_candidate_document()["items"]
    }
    assert not production_ids & external_ids


def test_frozen_evidence_is_immutable_binary_and_computed_reproducibly():
    frozen = freeze_eligible_evidence(sequence_id="freeze-a", concept_id="breadth_first_search", signals=[1, 0])
    assert frozen.eligible_signals == (1.0, 0.0)
    try:
        frozen.eligible_signals = (0.0,)  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:  # pragma: no cover - documents the immutable protocol requirement
        raise AssertionError("frozen evidence must be immutable")
    assert policy_estimates(frozen) == policy_estimates(frozen)


def test_participant_code_is_random_format_and_not_learner_uuid_derived():
    code = generate_participant_code()
    assert re.fullmatch(r"R7-[A-Z0-9]{6}", code)
    assert "uuid" not in code.lower()
    assert "streamlit_user" not in code


def test_synthetic_dry_run_covers_all_eight_required_scenarios_without_shadow_state():
    report = run_synthetic_study(ROOT)
    assert report["synthetic"] is True
    assert report["participant_code"] == "R7-SYN-001"
    assert [record["scenario_id"] for record in report["records"]] == [f"S{index}" for index in range(1, 9)]
    assert report["research_boundary"] == {
        "external_assessment_writes_mastery": False,
        "external_assessment_creates_exposure": False,
        "recommendation_evaluated": False,
        "production_learner_state_written": False,
        "network_called": False,
        "real_participant_data_used": False,
    }
    assert "learner_state" not in report
    assert "recommendation" not in report


def test_missing_external_results_are_null_not_incorrect_and_assisted_repeat_are_excluded():
    report = run_synthetic_study(ROOT)
    rows = {row["scenario_id"]: row for row in report["records"]}
    assert rows["S7"]["external_assessment"]["external_assessment_score"] is None
    assert rows["S7"]["external_assessment"]["missing_reason"] == "participant_stopped_before_external_assessment"
    assert rows["S8"]["external_assessment"]["external_assessment_score"] is None
    assert rows["S8"]["external_assessment"]["missing_reason"] == "delayed_session_missing"
    assert rows["S6"]["frozen_evidence"]["eligible_signals"] == [1.0]
    assert rows["S6"]["frozen_evidence"]["excluded_event_categories"] == [
        "practice_only_repeat", "hint_assisted_correct", "reveal_without_observation"
    ]


def test_export_is_privacy_safe_and_contains_no_question_text_or_secret_fields(tmp_path):
    output = tmp_path / "p7-export.json"
    report = write_synthetic_export(output, ROOT)
    exported = json.loads(output.read_text(encoding="utf-8"))
    assert report == exported
    forbidden_keys = {
        "question", "question_text", "stem", "choices", "answer", "answer_text",
        "learner_uuid", "student_id", "api_key", "authorization", "timestamp",
    }
    assert not forbidden_keys & set(_all_keys(exported))


def test_p7_tooling_is_not_imported_by_production_or_app():
    source_paths = [ROOT / "app.py", *sorted((ROOT / "src" / "introai_tutor").glob("*.py"))]
    assert all("run_p7_synthetic_study" not in path.read_text(encoding="utf-8") for path in source_paths)
    assert all("validate_p7_assessment_candidates" not in path.read_text(encoding="utf-8") for path in source_paths)
