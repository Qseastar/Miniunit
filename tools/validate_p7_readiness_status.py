"""Validate the research-only P7 Level 2 readiness status record offline."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.knowledge import load_knowledge_points  # noqa: E402
from introai_tutor.template_selection import load_diagnostic_templates  # noqa: E402
from tools.validate_p7_assessment_candidates import (  # noqa: E402
    CANDIDATE_PATH,
    load_p7_candidate_document,
    validate_p7_candidate_document,
)
from tools.verification_benchmark import build_manifest  # noqa: E402


STATUS_PATH = ROOT / "data" / "evaluation" / "p7_readiness_status.json"
STATUS_SCHEMA_VERSION = 1
EXPECTED_CONCEPT_DISTRIBUTION = {
    "breadth_first_search": 2,
    "uniform_cost_search": 2,
    "a_star_search": 2,
    "local_search": 1,
    "minimax_search": 2,
    "monte_carlo_tree_search": 2,
}
EXPECTED_ACTIVE_IDS = {
    "p7_ext_bfs_depth_claim_a",
    "p7_ext_bfs_queue_trace_b",
    "p7_ext_ucs_cost_accumulation_a",
    "p7_ext_ucs_positive_cost_bound_d",
    "p7_ext_astar_zero_heuristic_c",
    "p7_ext_astar_component_change_b",
    "p7_ext_local_search_neighbor_a",
    "p7_ext_minimax_min_node_a",
    "p7_ext_minimax_two_level_b",
    "p7_ext_mcts_backpropagation_a",
    "p7_ext_mcts_expand_untried_child_b",
}
EXPECTED_OWNER_DISPOSITIONS = {
    "p7_ext_bfs_queue_trace_b": "OWNER_APPROVE_PRESERVE",
    "p7_ext_ucs_cost_accumulation_a": "OWNER_APPROVE_PRESERVE",
    "p7_ext_astar_component_change_b": "OWNER_APPROVE_PRESERVE",
    "p7_ext_minimax_min_node_a": "OWNER_APPROVE_PRESERVE",
    "p7_ext_minimax_two_level_b": "OWNER_APPROVE_TRANSFER_EXPLORATORY_ONLY",
    "p7_ext_mcts_expand_untried_child_b": "OWNER_APPROVE_PRESERVE",
    "p7_ext_bfs_depth_claim_a": "OWNER_APPROVE",
    "p7_ext_local_search_neighbor_a": "OWNER_APPROVE",
    "p7_ext_mcts_backpropagation_a": "OWNER_APPROVE",
    "p7_ext_astar_zero_heuristic_c": "OWNER_APPROVE",
    "p7_ext_ucs_positive_cost_bound_d": "OWNER_APPROVE",
}
REQUIRED_OWNER_DECISION_DOCUMENTS = {
    "docs/evaluation/p7_readiness_promotion_audit.md",
    "docs/evaluation/p7a_external_assessment_owner_review.md",
    "docs/evaluation/p7b_owner_directed_assessment_revision.md",
    "docs/evaluation/p7c_second_owner_review_revision.md",
    "docs/evaluation/p7d_third_owner_review_local_search_revision.md",
}


class P7ReadinessStatusError(ValueError):
    """Raised when the research-only readiness record is invalid."""


def load_p7_readiness_status(path: str | Path = STATUS_PATH) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise P7ReadinessStatusError("P7 readiness status record is missing.") from error
    except json.JSONDecodeError as error:
        raise P7ReadinessStatusError("P7 readiness status record is invalid JSON.") from error
    if not isinstance(value, dict):
        raise P7ReadinessStatusError("P7 readiness status record must be an object.")
    return value


def validate_p7_readiness_status(*, root: Path = ROOT, path: str | Path = STATUS_PATH) -> dict[str, Any]:
    root = Path(root)
    status = load_p7_readiness_status(path)
    errors: list[str] = []
    required_top_level = {
        "schema_version", "record_type", "project_id", "readiness_level", "readiness_label",
        "owner_decision", "owner_decision_basis", "owner_dispositions", "external_bank", "human_study",
        "external_result_interpretation", "production_isolation", "candidate_schema_note",
    }
    if set(status) != required_top_level:
        errors.append("readiness status has an invalid top-level schema")
    if status.get("schema_version") != STATUS_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if status.get("record_type") != "p7_research_readiness_status":
        errors.append("record_type is invalid")
    if status.get("project_id") != "introai_tutor_search_algorithms":
        errors.append("project_id is invalid")
    if status.get("readiness_level") != 2:
        errors.append("readiness_level must be 2")
    if status.get("readiness_label") != "external assessment items owner-reviewed":
        errors.append("readiness_label must match the formal Level 2 definition")
    if status.get("owner_decision") != "OWNER_APPROVE_LEVEL_2":
        errors.append("owner_decision must be OWNER_APPROVE_LEVEL_2")
    basis = status.get("owner_decision_basis")
    if not isinstance(basis, dict) or set(basis) != {"documents", "lineage"}:
        errors.append("owner_decision_basis schema is invalid")
    else:
        if set(basis.get("documents", [])) != REQUIRED_OWNER_DECISION_DOCUMENTS:
            errors.append("owner decision lineage documents are incomplete or unexpected")
        else:
            for document in basis["documents"]:
                if not (root / document).is_file():
                    errors.append(f"owner decision lineage document is missing: {document}")
        if not isinstance(basis.get("lineage"), str) or not basis["lineage"].strip():
            errors.append("owner decision lineage must be non-empty")
    if status.get("owner_dispositions") != EXPECTED_OWNER_DISPOSITIONS:
        errors.append("owner dispositions do not cover the accepted active bank exactly")

    candidate_report = validate_p7_candidate_document(root=root)
    candidate_document = load_p7_candidate_document(root / "data" / "evaluation" / "p7_external_assessment_candidates.json")
    active_items = candidate_document["items"]
    active_ids = {item["assessment_item_id"] for item in active_items}
    bank = status.get("external_bank")
    required_bank = {
        "active_item_count", "selected_concept_count", "concept_distribution", "asymmetric_bank_accepted",
        "active_item_ids", "local_search_representation_status", "local_search_block_code",
        "strict_parallel_forms_available", "minimax_two_level_role",
    }
    if not isinstance(bank, dict) or set(bank) != required_bank:
        errors.append("external_bank schema is invalid")
    else:
        if bank["active_item_count"] != len(active_items) or bank["active_item_count"] != 11:
            errors.append("active external item count does not match the reviewed bank")
        if bank["selected_concept_count"] != 6:
            errors.append("selected concept count must be 6")
        if bank["concept_distribution"] != EXPECTED_CONCEPT_DISTRIBUTION:
            errors.append("concept distribution does not match the accepted asymmetric bank")
        if set(bank["active_item_ids"]) != EXPECTED_ACTIVE_IDS or active_ids != EXPECTED_ACTIVE_IDS:
            errors.append("active item IDs do not match the accepted owner-reviewed bank")
        if bank["asymmetric_bank_accepted"] is not True:
            errors.append("asymmetric_bank_accepted must be true")
        if bank["local_search_representation_status"] != "BLOCKED_BY_INDEPENDENCE":
            errors.append("Local Search representation status is invalid")
        if bank["local_search_block_code"] != "LOCAL_SEARCH_REPRESENTATION_BLOCKED_BY_INDEPENDENCE":
            errors.append("Local Search block code is invalid")
        if bank["strict_parallel_forms_available"] is not False:
            errors.append("strict_parallel_forms_available must be false")
        if bank["minimax_two_level_role"] != "TRANSFER_EXPLORATORY_ONLY":
            errors.append("Minimax two-level role is invalid")

    human_study = status.get("human_study")
    if not isinstance(human_study, dict) or set(human_study) != {"authorized", "checkpoint", "checkpoint_status"}:
        errors.append("human_study schema is invalid")
    else:
        if human_study["authorized"] is not False:
            errors.append("human_study.authorized must be false")
        if human_study["checkpoint"] != "CHECK_BEFORE_REAL_HUMAN_STUDY":
            errors.append("human-study checkpoint is invalid")
        if human_study["checkpoint_status"] != "UNRESOLVED":
            errors.append("human-study checkpoint must remain unresolved")
    if status.get("external_result_interpretation") != "independent course-grounded performance criterion":
        errors.append("external result interpretation is unsafe or invalid")

    isolation = status.get("production_isolation")
    required_isolation = {
        "production_template_count", "active_production_candidate_count", "blocked_production_slot_count",
        "concept_count", "registered_in_production", "writes_mastery", "writes_learner_state",
        "writes_recommendation",
    }
    if not isinstance(isolation, dict) or set(isolation) != required_isolation:
        errors.append("production_isolation schema is invalid")
    else:
        manifest = build_manifest(root=root)
        knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
        production = load_diagnostic_templates(
            root / "data" / "diagnostic_templates.json",
            valid_concept_ids={point["id"] for point in knowledge["knowledge_points"]},
        )["templates"]
        expected_counts = {
            "production_template_count": len(production),
            "active_production_candidate_count": len(manifest["candidates"]),
            "blocked_production_slot_count": len(manifest["blocked_slots"]),
            "concept_count": len(knowledge["knowledge_points"]),
        }
        for field, expected in expected_counts.items():
            if isolation[field] != expected:
                errors.append(f"production isolation count mismatch: {field}")
        for field in ("registered_in_production", "writes_mastery", "writes_learner_state", "writes_recommendation"):
            if isolation[field] is not False:
                errors.append(f"production isolation flag must be false: {field}")

    if not candidate_report["valid"]:
        errors.append("candidate bank validator failed")
    if candidate_document["assessment_status"] != "pending_owner_review":
        errors.append("candidate bank lifecycle status must remain pending_owner_review")
    if any(item["human_review_status"] != "pending_owner_review" for item in active_items):
        errors.append("candidate-level lifecycle statuses must remain pending_owner_review")

    return {
        "valid": not errors,
        "errors": errors,
        "summary": {
            "readiness_level": status.get("readiness_level"),
            "active_external_item_count": len(active_items),
            "selected_concept_count": len(status.get("external_bank", {}).get("concept_distribution", {})),
            "human_study_authorized": status.get("human_study", {}).get("authorized"),
            "human_study_checkpoint_status": status.get("human_study", {}).get("checkpoint_status"),
        },
    }


if __name__ == "__main__":
    report = validate_p7_readiness_status()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)
