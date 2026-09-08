"""P7 Level 2 status record invariants; research-only and production-isolated."""

from __future__ import annotations

import json
from pathlib import Path

from tools.validate_p7_readiness_status import (
    STATUS_PATH,
    load_p7_readiness_status,
    validate_p7_readiness_status,
)


ROOT = Path(__file__).resolve().parents[1]
DECISION_DOC = ROOT / "docs" / "evaluation" / "p7_level2_owner_readiness_decision.md"


def test_level2_status_record_is_valid_and_matches_real_bank():
    report = validate_p7_readiness_status(root=ROOT)
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["summary"] == {
        "readiness_level": 2,
        "active_external_item_count": 11,
        "selected_concept_count": 6,
        "human_study_authorized": False,
        "human_study_checkpoint_status": "UNRESOLVED",
    }


def test_level2_decision_document_explicitly_separates_human_study_authorization():
    text = DECISION_DOC.read_text(encoding="utf-8")
    assert "LEVEL 2 — external assessment items owner-reviewed" in text
    assert "human_study_authorized = false" in text
    assert "CHECK_BEFORE_REAL_HUMAN_STUDY = UNRESOLVED" in text
    assert "independent course-grounded performance criterion" in text
    assert "p7_ext_local_search_representation_b" in text
    assert "TRANSFER_EXPLORATORY_ONLY" in text


def test_candidate_lifecycle_pending_fields_are_not_rewritten():
    status = load_p7_readiness_status(STATUS_PATH)
    assert "pending_owner_review" in status["candidate_schema_note"]
    candidate = json.loads(
        (ROOT / "data" / "evaluation" / "p7_external_assessment_candidates.json").read_text(encoding="utf-8")
    )
    assert candidate["assessment_status"] == "pending_owner_review"
    assert all(item["human_review_status"] == "pending_owner_review" for item in candidate["items"])


def test_machine_readable_owner_dispositions_cover_all_active_items():
    status = load_p7_readiness_status(STATUS_PATH)
    assert set(status["owner_dispositions"]) == set(status["external_bank"]["active_item_ids"])
    assert status["owner_dispositions"]["p7_ext_minimax_two_level_b"] == "OWNER_APPROVE_TRANSFER_EXPLORATORY_ONLY"


def test_status_validator_rejects_human_study_authorization_or_wrong_bank(tmp_path):
    original = load_p7_readiness_status(STATUS_PATH)
    authorized = dict(original)
    authorized["human_study"] = dict(original["human_study"], authorized=True)
    authorized_path = tmp_path / "authorized.json"
    authorized_path.write_text(json.dumps(authorized, ensure_ascii=False), encoding="utf-8")
    report = validate_p7_readiness_status(root=ROOT, path=authorized_path)
    assert report["valid"] is False
    assert any("authorized" in error for error in report["errors"])

    wrong_count = json.loads(json.dumps(original))
    wrong_count["external_bank"]["active_item_count"] = 10
    wrong_path = tmp_path / "wrong-count.json"
    wrong_path.write_text(json.dumps(wrong_count, ensure_ascii=False), encoding="utf-8")
    report = validate_p7_readiness_status(root=ROOT, path=wrong_path)
    assert report["valid"] is False
    assert any("count" in error for error in report["errors"])


def test_status_validator_rejects_missing_owner_lineage_document(tmp_path):
    original = load_p7_readiness_status(STATUS_PATH)
    mutated = json.loads(json.dumps(original))
    mutated["owner_decision_basis"]["documents"] = mutated["owner_decision_basis"]["documents"][:-1]
    path = tmp_path / "missing-lineage.json"
    path.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
    report = validate_p7_readiness_status(root=ROOT, path=path)
    assert report["valid"] is False
    assert any("lineage" in error for error in report["errors"])
