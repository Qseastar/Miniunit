"""Owner-directed P7b research-candidate revision invariants."""

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


ROOT = Path(__file__).resolve().parents[1]

_APPROVED_SIX_HASHES = {
    "p7_ext_bfs_queue_trace_b": "1169b1d42f2be879f780bfb8a746bbc24d659e9a09c8904acb50f1984ecb9a5e",
    "p7_ext_ucs_cost_accumulation_a": "a61cfd2aaf85f8ad396ce62171a9c8dedaad3da2beb28a39bbeb9fb987735144",
    "p7_ext_astar_component_change_b": "8a333437353c435522f86ed407a61da43f1d5ddc97cfd696aecbb2979e9a7eb2",
    "p7_ext_minimax_min_node_a": "2daf2e04adebf871f074b5c8c494c1f1623df05430d6dda99fe93a2a525b2b22",
    "p7_ext_minimax_two_level_b": "501f782af88a045496ebd310a22daa3f4ab36dab5dd23fdd1b6ab8ba32a532da",
    "p7_ext_mcts_expand_untried_child_b": "990415b856c8d50b5b90eb4f356cc0dd7496d85f7e953b9fdb516b3ef1a520da",
}

_REJECTED_IDS = {
    "p7_ext_ucs_equal_depth_cost_b",
    "p7_ext_astar_f_computation_a",
}

_P7B_REPLACEMENT_STILL_ACTIVE = {
    "p7_ext_astar_zero_heuristic_c": "a_star_search",
}

_CHANGED_IDS = {
    "p7_ext_bfs_depth_claim_a",
    "p7_ext_local_search_neighbor_a",
    "p7_ext_mcts_backpropagation_a",
    *_P7B_REPLACEMENT_STILL_ACTIVE,
}


def _items_by_id():
    return {
        item["assessment_item_id"]: item
        for item in load_p7_candidate_document(CANDIDATE_PATH)["items"]
    }


def _canonical_hash(item: dict) -> str:
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_owner_preserved_six_are_semantically_immutable():
    items = _items_by_id()
    assert set(_APPROVED_SIX_HASHES) <= set(items)
    assert {
        item_id: _canonical_hash(items[item_id])
        for item_id in _APPROVED_SIX_HASHES
    } == _APPROVED_SIX_HASHES


def test_p7a_rejected_originals_are_history_only_and_the_surviving_p7b_replacement_is_pending():
    document = load_p7_candidate_document(CANDIDATE_PATH)
    items = _items_by_id()
    assert not _REJECTED_IDS & set(items)
    assert set(_P7B_REPLACEMENT_STILL_ACTIVE) <= set(items)
    # P7d may scientifically block the second Local Search external form rather
    # than retain an invalid cosmetic parallel item.
    assert len(items) == len(document["items"]) == 11
    assert len(set(items)) == 11
    assert all(items[item_id]["concept_id"] == concept_id for item_id, concept_id in _P7B_REPLACEMENT_STILL_ACTIVE.items())
    assert all(items[item_id]["human_review_status"] == "pending_owner_review" for item_id in _P7B_REPLACEMENT_STILL_ACTIVE)


def test_changed_items_are_closed_pending_and_course_grounded_without_production_registration():
    report = validate_p7_candidate_document(root=ROOT)
    assert report["valid"] is True
    items = _items_by_id()
    knowledge = load_knowledge_points(ROOT / "data" / "knowledge_points.json")
    production_ids = {
        item["id"]
        for item in load_diagnostic_templates(
            ROOT / "data" / "diagnostic_templates.json",
            valid_concept_ids={point["id"] for point in knowledge["knowledge_points"]},
        )["templates"]
    }
    for item_id in _CHANGED_IDS:
        item = items[item_id]
        assert item["question_type"] == "single_choice"
        assert item["human_review_status"] == "pending_owner_review"
        assert item["source_refs"]
        assert item["expected_answer"]["choice_id"] in {choice["id"] for choice in item["choices"]}
        assert item_id not in production_ids
        assert item["production_overlap_analysis"]["classification"] not in {"TOO_SIMILAR", "CIRCULAR"}


def test_surviving_p7b_astar_replacement_preserves_its_distinct_capability_slice():
    items = _items_by_id()
    astar = items["p7_ext_astar_zero_heuristic_c"]
    assert "h(n)=0" in astar["stem"]
    assert "f(n) 的数值计算" in astar["does_not_measure"]
    assert astar["source_refs"] == [{
        "chunk_id": "lec3_heuristic_extremes",
        "source_file": "ai_lec3_informed_search.pdf",
        "page_start": 57,
        "page_end": 57,
    }]


def test_mcts_revision_uses_the_direct_backpropagation_definition_page():
    item = _items_by_id()["p7_ext_mcts_backpropagation_a"]
    assert item["source_refs"] == [{
        "chunk_id": "lec6_mcts_four_stages",
        "source_file": "ai_lec6_mcts_and_search_summary.pdf",
        "page_start": 20,
        "page_end": 20,
    }]


def test_synthetic_pipeline_never_references_p7a_rejected_originals():
    report = run_synthetic_study(ROOT)
    assert all(
        row["external_assessment"]["assessment_item_id"] not in _REJECTED_IDS
        for row in report["records"]
    )
    assert report["candidate_bank_status"] == "pending_owner_review"
