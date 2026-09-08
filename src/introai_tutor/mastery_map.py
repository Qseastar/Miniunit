"""Pure, deterministic view model for the Search Algorithms mastery map.

The knowledge registry remains the source of truth for concepts and their
prerequisites.  The companion layout file deliberately stores presentation
coordinates only; it does not introduce a second semantic graph.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from introai_tutor.knowledge import validate_knowledge_points


DISPLAY_REVIEW_THRESHOLD = 0.60
DISPLAY_STEADY_THRESHOLD = 0.80
_MASTERY_BANDS = (
    ("review", "建议复习", "建议复习", "mastery-map-status-review"),
    ("developing", "初步掌握", "初步掌握", "mastery-map-status-developing"),
    ("steady", "掌握较稳", "掌握较稳", "mastery-map-status-steady"),
)
_UNTRACKED = {
    "status": "untracked",
    "label": "尚未追踪",
    "css_token": "mastery-map-status-untracked",
    "score": None,
    "is_tracked": False,
}
_INVALID = {
    "status": "unavailable",
    "label": "状态暂不可用",
    "css_token": "mastery-map-status-unavailable",
    "score": None,
    "is_tracked": True,
}
_REVIEW_STATUS = "human_verified"
_VERIFICATION_PURPOSE = "mastery_verification"


class MasteryMapError(ValueError):
    """Raised when map inputs cannot produce a safe, complete view model."""


def load_mastery_map_layout(path: str | Path) -> dict[str, Any]:
    """Load a presentation-only mastery-map layout document."""
    with Path(path).open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise MasteryMapError("Mastery-map layout must be an object.")
    return deepcopy(data)


def validate_mastery_map_layout(layout_data: Any, knowledge_data: dict[str, Any]) -> None:
    """Validate a complete layout against the authoritative knowledge DAG."""
    validate_knowledge_points(knowledge_data)
    if not isinstance(layout_data, dict) or set(layout_data) != {"schema_version", "nodes"}:
        raise MasteryMapError("Mastery-map layout must contain schema_version and nodes only.")
    if layout_data["schema_version"] != 1:
        raise MasteryMapError("Unsupported mastery-map layout schema_version.")
    nodes = layout_data["nodes"]
    if not isinstance(nodes, list) or not nodes:
        raise MasteryMapError("Mastery-map layout nodes must be a non-empty list.")

    known_ids = _knowledge_by_id(knowledge_data)
    node_ids: set[str] = set()
    positions: set[tuple[int, int]] = set()
    layers_by_id: dict[str, int] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) != {"concept_id", "layer", "order"}:
            raise MasteryMapError(f"Layout node at index {index} has an invalid schema.")
        concept_id = node["concept_id"]
        if not isinstance(concept_id, str) or not concept_id or concept_id not in known_ids:
            raise MasteryMapError(f"Layout node at index {index} has an unknown concept_id.")
        if concept_id in node_ids:
            raise MasteryMapError(f"Duplicate layout concept_id: {concept_id}")
        layer, order = node["layer"], node["order"]
        if not _non_negative_int(layer) or not _non_negative_int(order):
            raise MasteryMapError(f"Layout node '{concept_id}' has invalid layer or order.")
        position = (layer, order)
        if position in positions:
            raise MasteryMapError("Layout nodes must have unique layer/order positions.")
        node_ids.add(concept_id)
        positions.add(position)
        layers_by_id[concept_id] = layer
    if node_ids != set(known_ids):
        missing = sorted(set(known_ids) - node_ids)
        extra = sorted(node_ids - set(known_ids))
        raise MasteryMapError(
            f"Layout concepts must exactly match knowledge registry; missing={missing}, extra={extra}."
        )

    _stable_topological_order(knowledge_data)
    for concept_id, point in known_ids.items():
        for prerequisite_id in point["prerequisites"]:
            if prerequisite_id == concept_id:
                raise MasteryMapError(f"Knowledge prerequisite self-loop: {concept_id}")
            if layers_by_id[prerequisite_id] >= layers_by_id[concept_id]:
                raise MasteryMapError(
                    f"Layout layer for '{concept_id}' must follow prerequisite '{prerequisite_id}'."
                )


def classify_mastery_for_display(*, mastery_value: Any, is_tracked: bool) -> dict[str, Any]:
    """Return a fail-safe presentation band without changing domain evidence.

    This function intentionally does not call the learner-state validator:
    callers may receive a partially recovered local state.  Invalid values are
    contained in a student-safe display state instead of being normalized.
    """
    if not isinstance(is_tracked, bool):
        raise MasteryMapError("is_tracked must be a bool.")
    if not is_tracked:
        return deepcopy(_UNTRACKED)
    if (
        isinstance(mastery_value, bool)
        or not isinstance(mastery_value, int | float)
        or not math.isfinite(float(mastery_value))
        or not 0.0 <= float(mastery_value) <= 1.0
    ):
        return deepcopy(_INVALID)
    score = float(mastery_value)
    if score < DISPLAY_REVIEW_THRESHOLD:
        status, label, aria_label, css_token = _MASTERY_BANDS[0]
    elif score < DISPLAY_STEADY_THRESHOLD:
        status, label, aria_label, css_token = _MASTERY_BANDS[1]
    else:
        status, label, aria_label, css_token = _MASTERY_BANDS[2]
    return {
        "status": status,
        "label": label,
        "aria_label": aria_label,
        "css_token": css_token,
        "score": score,
        "is_tracked": True,
    }


def build_concept_coverage(
    *, templates_data: Any, knowledge_data: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Derive primary reviewed-template coverage from the production bank.

    A supporting concept in ``concept_ids[1:]`` does not establish reviewed
    coverage.  Candidate or otherwise unreviewed documents are deliberately
    ignored; malformed production records fail closed.
    """
    validate_knowledge_points(knowledge_data)
    known_ids = _knowledge_by_id(knowledge_data)
    if not isinstance(templates_data, dict) or set(templates_data) != {"schema_version", "templates"}:
        raise MasteryMapError("Template data must contain schema_version and templates only.")
    if templates_data["schema_version"] != 1 or not isinstance(templates_data["templates"], list):
        raise MasteryMapError("Template data has an invalid schema_version or templates list.")

    coverage: dict[str, list[tuple[int, str]]] = {concept_id: [] for concept_id in known_ids}
    seen_production_ids: set[str] = set()
    for index, template in enumerate(templates_data["templates"]):
        if not isinstance(template, dict):
            raise MasteryMapError(f"Template at index {index} must be an object.")
        review_status = template.get("review_status")
        purpose = template.get("purpose")
        if review_status != _REVIEW_STATUS or purpose != _VERIFICATION_PURPOSE:
            continue
        template_id = template.get("id")
        concept_ids = template.get("concept_ids")
        priority = template.get("selection_priority")
        if (
            not isinstance(template_id, str)
            or not template_id
            or template_id in seen_production_ids
            or not isinstance(concept_ids, list)
            or not concept_ids
            or not isinstance(concept_ids[0], str)
            or concept_ids[0] not in known_ids
            or isinstance(priority, bool)
            or not isinstance(priority, int)
        ):
            raise MasteryMapError("Production template has an invalid primary concept or identity.")
        seen_production_ids.add(template_id)
        coverage[concept_ids[0]].append((priority, template_id))

    return {
        concept_id: {
            "template_ids": [
                template_id for _, template_id in sorted(items, key=lambda item: (-item[0], item[1]))
            ],
            "template_count": len(items),
            "label": "可审核诊断" if items else "暂无审核诊断",
            "available": bool(items),
        }
        for concept_id, items in coverage.items()
    }


def build_mastery_map_model(
    *,
    knowledge_data: dict[str, Any],
    layout_data: dict[str, Any],
    templates_data: dict[str, Any],
    learner_state: Any,
    recommendation: Any = None,
) -> dict[str, Any]:
    """Build one immutable snapshot for a complete map render."""
    validate_mastery_map_layout(layout_data, knowledge_data)
    coverage = build_concept_coverage(
        templates_data=templates_data, knowledge_data=knowledge_data
    )
    registry = _knowledge_by_id(knowledge_data)
    mastery = learner_state.get("mastery", {}) if isinstance(learner_state, dict) else {}
    mastery = mastery if isinstance(mastery, dict) else {}
    recommended_id = recommendation.get("concept_id") if isinstance(recommendation, dict) else None
    recommended_id = recommended_id if recommended_id in registry else None
    warnings: list[str] = []
    if isinstance(recommendation, dict) and recommendation.get("concept_id") and not recommended_id:
        warnings.append("当前推荐不在本课程图谱中，已安全忽略。")

    by_id: dict[str, dict[str, Any]] = {}
    for layout_node in sorted(layout_data["nodes"], key=lambda item: (item["layer"], item["order"], item["concept_id"])):
        concept_id = layout_node["concept_id"]
        point = registry[concept_id]
        tracked = concept_id in mastery
        display = classify_mastery_for_display(
            mastery_value=mastery.get(concept_id), is_tracked=tracked
        )
        by_id[concept_id] = {
            "concept_id": concept_id,
            "title_zh": point["title_zh"],
            "title_en": point["title_en"],
            "module": point["module"],
            "description": point["description"],
            "prerequisite_ids": list(point["prerequisites"]),
            "layer": layout_node["layer"],
            "order": layout_node["order"],
            "mastery": display,
            "coverage": coverage[concept_id],
            "is_recommended": concept_id == recommended_id,
            "recommendation_reason": (
                recommendation.get("reason")
                if concept_id == recommended_id and isinstance(recommendation.get("reason"), str)
                else None
            ),
        }
    layers: list[dict[str, Any]] = []
    for layer in sorted({node["layer"] for node in by_id.values()}):
        nodes = sorted(
            (node for node in by_id.values() if node["layer"] == layer),
            key=lambda node: (node["order"], node["concept_id"]),
        )
        layers.append({"layer": layer, "nodes": deepcopy(nodes)})
    return {
        "layers": layers,
        "nodes_by_id": deepcopy(by_id),
        "recommended_concept_id": recommended_id,
        "warnings": warnings,
        "prerequisite_edges": _prerequisite_edges(knowledge_data),
    }


def build_concept_detail(
    *, map_model: dict[str, Any], concept_id: str, learning_evidence: Any = None
) -> dict[str, Any]:
    """Build a student-safe selected-node detail without raw learner content."""
    if not isinstance(map_model, dict) or not isinstance(map_model.get("nodes_by_id"), dict):
        raise MasteryMapError("map_model is invalid.")
    if not isinstance(concept_id, str) or concept_id not in map_model["nodes_by_id"]:
        raise MasteryMapError("Unknown mastery-map concept_id.")
    nodes = map_model["nodes_by_id"]
    node = deepcopy(nodes[concept_id])
    node["prerequisites"] = [
        {"concept_id": prerequisite_id, "title_zh": nodes[prerequisite_id]["title_zh"]}
        for prerequisite_id in node.pop("prerequisite_ids")
    ]
    dependent_ids = node.pop("dependent_ids", [])
    if not isinstance(dependent_ids, list) or any(item not in nodes for item in dependent_ids):
        raise MasteryMapError("Mastery-map detail dependents are invalid.")
    node["dependents"] = [
        {"concept_id": dependent_id, "title_zh": nodes[dependent_id]["title_zh"]}
        for dependent_id in dependent_ids
    ]
    node["evidence_summary"] = _evidence_summary(
        learning_evidence=learning_evidence,
        production_template_ids=node["coverage"]["template_ids"],
    )
    return node


def concept_question_prefill(*, concept: dict[str, Any]) -> str:
    """Return a trusted, non-submitting QA prompt from a registry title."""
    title = concept.get("title_zh") if isinstance(concept, dict) else None
    if not isinstance(title, str) or not title.strip():
        raise MasteryMapError("Concept title is unavailable for a QA prefill.")
    return f"请结合课件讲解{title.strip()}。"


def default_selected_concept_id(*, map_model: dict[str, Any]) -> str:
    """Choose a stable default, preferring a valid recommendation."""
    if not isinstance(map_model, dict) or not isinstance(map_model.get("nodes_by_id"), dict):
        raise MasteryMapError("map_model is invalid.")
    recommended_id = map_model.get("recommended_concept_id")
    if isinstance(recommended_id, str) and recommended_id in map_model["nodes_by_id"]:
        return recommended_id
    for layer in map_model.get("layers", []):
        nodes = layer.get("nodes") if isinstance(layer, dict) else None
        if isinstance(nodes, list) and nodes:
            return nodes[0]["concept_id"]
    raise MasteryMapError("map_model does not contain any nodes.")


def _evidence_summary(*, learning_evidence: Any, production_template_ids: list[str]) -> dict[str, Any]:
    if not isinstance(learning_evidence, list) or not production_template_ids:
        return {"event_count": 0, "template_ids": [], "label": "暂无记录", "updated_at": None}
    allowed = set(production_template_ids)
    matched_template_ids: set[str] = set()
    event_count = 0
    for event in learning_evidence:
        if not isinstance(event, dict):
            continue
        template_ids = event.get("template_ids")
        if not isinstance(template_ids, list):
            continue
        overlap = {item for item in template_ids if isinstance(item, str)} & allowed
        if overlap:
            event_count += 1
            matched_template_ids.update(overlap)
    return {
        "event_count": event_count,
        "template_ids": sorted(matched_template_ids),
        "label": f"已记录 {event_count} 次审核学习活动" if event_count else "暂无记录",
        # The restored learner-state contract carries no per-concept timestamp.
        "updated_at": None,
    }


def _knowledge_by_id(knowledge_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {point["id"]: point for point in knowledge_data["knowledge_points"]}


def _stable_topological_order(knowledge_data: dict[str, Any]) -> list[str]:
    registry = _knowledge_by_id(knowledge_data)
    indegree = {concept_id: len(point["prerequisites"]) for concept_id, point in registry.items()}
    children: dict[str, list[str]] = {concept_id: [] for concept_id in registry}
    for concept_id, point in registry.items():
        for prerequisite_id in point["prerequisites"]:
            if prerequisite_id not in registry:
                raise MasteryMapError(f"Unknown prerequisite: {prerequisite_id}")
            children[prerequisite_id].append(concept_id)
    ready = sorted(concept_id for concept_id, degree in indegree.items() if degree == 0)
    ordered: list[str] = []
    while ready:
        concept_id = ready.pop(0)
        ordered.append(concept_id)
        for child in sorted(children[concept_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()
    if len(ordered) != len(registry):
        raise MasteryMapError("Knowledge prerequisite graph contains a cycle.")
    return ordered


def _prerequisite_edges(knowledge_data: dict[str, Any]) -> list[tuple[str, str]]:
    _stable_topological_order(knowledge_data)
    return sorted(
        (prerequisite_id, point["id"])
        for point in knowledge_data["knowledge_points"]
        for prerequisite_id in point["prerequisites"]
    )


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
