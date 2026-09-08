"""Third-owner-review P7d Local Search blocking and immutability invariants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.template_selection import load_diagnostic_templates
from tools.run_p7_synthetic_study import run_synthetic_study
from tools.validate_p7_assessment_candidates import (
    CANDIDATE_PATH,
    load_p7_candidate_document,
    validate_p7_candidate_document,
)
from tools.verification_benchmark import build_manifest


ROOT = Path(__file__).resolve().parents[1]
P7C_DOCUMENT = ROOT / "docs" / "evaluation" / "p7c_second_owner_review_revision.md"
P7D_DOCUMENT = ROOT / "docs" / "evaluation" / "p7d_third_owner_review_local_search_revision.md"

_OWNER_APPROVED_HASHES = {
    "p7_ext_bfs_depth_claim_a": "802dc213cd9a13bd2d624bd57b723f94acc0c891cd4d1aae5e8cc9997fd1b231",
    "p7_ext_local_search_neighbor_a": "2243b54a80e834ad19675fc4f608db5981c2c7dc8b790b946905ef7009f96092",
    "p7_ext_mcts_backpropagation_a": "67583fdf6b125d0d331a54f2724478e7b53f3b0b8c8bba6f3470c83b7f8ae1c5",
    "p7_ext_astar_zero_heuristic_c": "3322f375f4f4c82dfb295969f686aa23d62649fcd6fb1b8d7348f57e6e5695bd",
    "p7_ext_ucs_positive_cost_bound_d": "a04400e4658a0a5aaf43128e27b0880682c8cb13e3cecd5ee33dfeefc04afcdf",
}

_P7C_LOCAL_STEM = (
    "按照 Lec4 对局部搜索的总体介绍，下列哪项任务结果最适合采用“只关心最终返回状态是否达到目标，而不关心完整路径”的搜索视角？"
)


def _items_by_id() -> dict[str, dict]:
    return {
        item["assessment_item_id"]: item
        for item in load_p7_candidate_document(CANDIDATE_PATH)["items"]
    }


def _canonical_hash(item: dict) -> str:
    return hashlib.sha256(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_third_owner_approved_items_are_canonically_frozen():
    items = _items_by_id()
    assert {
        item_id: _canonical_hash(items[item_id])
        for item_id in _OWNER_APPROVED_HASHES
    } == _OWNER_APPROVED_HASHES


def test_local_representation_slot_is_explicitly_blocked_not_replaced_cosmetically():
    document = load_p7_candidate_document(CANDIDATE_PATH)
    active_items = _items_by_id()
    assert "p7_ext_local_search_representation_b" not in active_items
    assert _P7C_LOCAL_STEM not in {item["stem"] for item in document["items"]}
    history = P7C_DOCUMENT.read_text(encoding="utf-8")
    audit = P7D_DOCUMENT.read_text(encoding="utf-8")
    assert _P7C_LOCAL_STEM in history
    assert "OWNER_REVISE" in audit
    assert "LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE" in audit
    assert "没有新的 P7d Local Search 题干、A/B/C/D 或 expected answer" in audit


def test_blocked_asymmetry_keeps_the_research_bank_closed_pending_and_valid():
    report = validate_p7_candidate_document(root=ROOT)
    document = load_p7_candidate_document(CANDIDATE_PATH)
    assert report["valid"] is True
    assert report["summary"]["item_count"] == len(document["items"]) == 11
    assert report["summary"]["independent_or_complementary_item_count"] == 11
    assert document["assessment_status"] == "pending_owner_review"
    assert all(item["human_review_status"] == "pending_owner_review" for item in document["items"])
    assert sum(item["concept_id"] == "local_search" for item in document["items"]) == 1


def test_blocking_does_not_change_production_or_synthetic_research_boundaries():
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    production = load_diagnostic_templates(
        ROOT / "data" / "diagnostic_templates.json",
        valid_concept_ids={point["id"] for point in knowledge["knowledge_points"]},
    )["templates"]
    external_ids = set(_items_by_id())
    assert not external_ids & {item["id"] for item in production}
    manifest = build_manifest(root=ROOT)
    assert len(manifest["production"]) == 28
    assert len(manifest["candidates"]) == 0
    assert len(manifest["blocked_slots"]) == 1
    report = run_synthetic_study(ROOT)
    assert report["records"][3]["external_assessment"]["assessment_item_id"] == "p7_ext_local_search_neighbor_a"
    assert report["research_boundary"]["external_assessment_writes_mastery"] is False
    assert report["research_boundary"]["production_learner_state_written"] is False
