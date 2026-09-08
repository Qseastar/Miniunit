"""Second-owner-review P7c research-instrument revision invariants."""

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

_SECOND_OWNER_APPROVED_HASHES = {
    "p7_ext_bfs_depth_claim_a": "802dc213cd9a13bd2d624bd57b723f94acc0c891cd4d1aae5e8cc9997fd1b231",
    "p7_ext_local_search_neighbor_a": "2243b54a80e834ad19675fc4f608db5981c2c7dc8b790b946905ef7009f96092",
    "p7_ext_mcts_backpropagation_a": "67583fdf6b125d0d331a54f2724478e7b53f3b0b8c8bba6f3470c83b7f8ae1c5",
    "p7_ext_astar_zero_heuristic_c": "3322f375f4f4c82dfb295969f686aa23d62649fcd6fb1b8d7348f57e6e5695bd",
}

_P7C_REJECTED_IDS = {
    "p7_ext_ucs_depth_cost_tradeoff_c",
}

_P7C_DOCUMENT = ROOT / "docs" / "evaluation" / "p7c_second_owner_review_revision.md"
_P7D_DOCUMENT = ROOT / "docs" / "evaluation" / "p7d_third_owner_review_local_search_revision.md"
_P7B_LOCAL_REPRESENTATION_STEM = (
    "按照 Lec4 对局部搜索的总体介绍，若目标是找到低冲突棋盘布局而不关心从初始布局到该布局的完整路径，"
    "下列哪项最贴近该过程的核心关注对象？"
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


def test_second_owner_approved_items_remain_semantically_frozen():
    items = _items_by_id()
    assert {
        item_id: _canonical_hash(items[item_id])
        for item_id in _SECOND_OWNER_APPROVED_HASHES
    } == _SECOND_OWNER_APPROVED_HASHES


def test_p7c_local_representation_proposal_is_historical_after_p7d_blocking():
    assert _P7B_LOCAL_REPRESENTATION_STEM not in {
        item["stem"] for item in _items_by_id().values()
    }
    assert "p7_ext_local_search_representation_b" not in _items_by_id()
    history = _P7C_DOCUMENT.read_text(encoding="utf-8")
    assert "最终返回状态是否达到目标" in history
    p7d_history = _P7D_DOCUMENT.read_text(encoding="utf-8")
    assert "LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE" in p7d_history


def test_owner_rejected_ucs_item_is_history_only_and_new_replacement_has_independent_pathway():
    items = _items_by_id()
    assert not _P7C_REJECTED_IDS & set(items)
    history = _P7C_DOCUMENT.read_text(encoding="utf-8")
    assert "p7_ext_ucs_depth_cost_tradeoff_c" in history
    assert "choose the smaller" in history
    replacement = items["p7_ext_ucs_positive_cost_bound_d"]
    assert replacement["human_review_status"] == "pending_owner_review"
    assert replacement["question_type"] == "single_choice"
    assert replacement["expected_answer"] == {"choice_id": "a"}
    assert "完备性" in replacement["stem"]
    text = " ".join([replacement["stem"], *(choice["text"] for choice in replacement["choices"])])
    assert "g(n)" not in text
    assert "frontier" not in text.lower()
    assert "2+4" not in text
    assert replacement["source_refs"] == [{
        "chunk_id": "lec2_ucs_properties",
        "source_file": "ai_lec2_uninformed_search.pdf",
        "page_start": 63,
        "page_end": 63,
    }]


def test_changed_items_remain_research_only_closed_pending_and_do_not_collide_with_production():
    report = validate_p7_candidate_document(root=ROOT)
    assert report["valid"] is True
    items = _items_by_id()
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    production = load_diagnostic_templates(
        ROOT / "data" / "diagnostic_templates.json",
        valid_concept_ids={point["id"] for point in knowledge["knowledge_points"]},
    )["templates"]
    production_ids = {item["id"] for item in production}
    production_stems = {item["prompt"] for item in production}
    production_options = {frozenset(choice["text"] for choice in item["choices"]) for item in production}
    for item_id in {"p7_ext_ucs_positive_cost_bound_d"}:
        item = items[item_id]
        assert item_id not in production_ids
        assert item["stem"] not in production_stems
        assert frozenset(choice["text"] for choice in item["choices"]) not in production_options
        assert item["production_overlap_analysis"]["classification"] == "COMPLEMENTARY_CAPABILITY"


def test_synthetic_pipeline_uses_only_the_new_active_ucs_id_and_production_inventory_is_unchanged():
    report = run_synthetic_study(ROOT)
    assert report["records"][1]["external_assessment"]["assessment_item_id"] == "p7_ext_ucs_positive_cost_bound_d"
    assert all(
        record["external_assessment"]["assessment_item_id"] not in _P7C_REJECTED_IDS
        for record in report["records"]
    )
    manifest = build_manifest(root=ROOT)
    assert len(manifest["production"]) == 28
    assert len(manifest["candidates"]) == 0
    assert len(manifest["blocked_slots"]) == 1
