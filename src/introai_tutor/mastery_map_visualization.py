"""Deterministic, student-safe presentation data for the mastery-map views."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from introai_tutor.mastery_map import MasteryMapError


CONCEPT_COPY_SCHEMA_VERSION = 1
LAYER_STAGE_NAMES = {
    0: "学习阶段 1：搜索问题建模",
    1: "学习阶段 2：搜索方向与应用",
    2: "学习阶段 3：搜索结构与策略",
    3: "学习阶段 4：节点管理与评价",
    4: "学习阶段 5：经典搜索与置信选择",
    5: "学习阶段 6：搜索性质与综合",
    6: "学习阶段 7：路径代价搜索",
    7: "学习阶段 8：启发式搜索基础",
    8: "学习阶段 9：启发式搜索策略",
    9: "学习阶段 10：启发函数性质",
}
LAYER_FILTERS = {
    "all": "全部知识点",
    "recommended": "当前推荐",
    "tracked": "已追踪",
    "covered": "可审核诊断",
    "review": "建议复习",
}
GRAPH_VISUAL_TOKENS = {
    "untracked": {"fill": "#EEF1F3", "border": "#64748B", "font": "#1F2937"},
    "review": {"fill": "#FFF3CD", "border": "#B7791F", "font": "#4A3500"},
    "developing": {"fill": "#D9F0DC", "border": "#2F855A", "font": "#173B20"},
    "steady": {"fill": "#A7DDAE", "border": "#166534", "font": "#102C17"},
    "unavailable": {"fill": "#FDE2E2", "border": "#B91C1C", "font": "#4A0D0D"},
}
_SNAKE_CASE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")
# Upper-case abbreviations such as IDDFS and MCTS are permitted, while a long
# lower-case run is a practical guard against accidentally pasting an English
# description into the student-facing Chinese copy.
_LONG_ENGLISH = re.compile(r"[a-z]{5,}")


def load_concept_copy_zh(path: str | Path) -> dict[str, Any]:
    """Load the independent student-copy document without mutating it."""
    with Path(path).open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise MasteryMapError("Chinese concept copy must be an object.")
    return deepcopy(data)


def validate_concept_copy_zh(copy_data: Any, knowledge_data: dict[str, Any]) -> None:
    """Require exactly one bounded, reviewed student summary per registry concept."""
    if not isinstance(copy_data, dict) or set(copy_data) != {"schema_version", "concepts"}:
        raise MasteryMapError("Chinese concept copy must contain schema_version and concepts only.")
    if copy_data["schema_version"] != CONCEPT_COPY_SCHEMA_VERSION:
        raise MasteryMapError("Unsupported Chinese concept-copy schema_version.")
    concepts = copy_data["concepts"]
    if not isinstance(concepts, list):
        raise MasteryMapError("Chinese concept copy concepts must be a list.")
    points = knowledge_data.get("knowledge_points") if isinstance(knowledge_data, dict) else None
    if not isinstance(points, list):
        raise MasteryMapError("Knowledge registry is invalid for Chinese concept copy.")
    known_ids = {point.get("id") for point in points if isinstance(point, dict)}
    if len(known_ids) != len(points) or not all(isinstance(item, str) and item for item in known_ids):
        raise MasteryMapError("Knowledge registry concept IDs are invalid.")
    seen_ids: set[str] = set()
    for index, item in enumerate(concepts):
        if not isinstance(item, dict) or set(item) != {"concept_id", "summary_zh"}:
            raise MasteryMapError(f"Chinese concept copy entry at index {index} has an invalid schema.")
        concept_id, summary = item["concept_id"], item["summary_zh"]
        if not isinstance(concept_id, str) or not concept_id or concept_id not in known_ids:
            raise MasteryMapError(f"Chinese concept copy entry at index {index} has an unknown concept_id.")
        if concept_id in seen_ids:
            raise MasteryMapError(f"Duplicate Chinese concept-copy concept_id: {concept_id}")
        if not isinstance(summary, str) or not summary or summary != summary.strip():
            raise MasteryMapError(f"Chinese summary for '{concept_id}' must be non-empty trimmed text.")
        if not 25 <= len(summary) <= 70:
            raise MasteryMapError(f"Chinese summary for '{concept_id}' must contain 25 to 70 characters.")
        if _SNAKE_CASE.search(summary) or "{{" in summary or "}}" in summary or "TODO" in summary:
            raise MasteryMapError(f"Chinese summary for '{concept_id}' contains implementation text.")
        if _LONG_ENGLISH.search(summary):
            raise MasteryMapError(f"Chinese summary for '{concept_id}' contains an unsupported long English fragment.")
        seen_ids.add(concept_id)
    if seen_ids != known_ids:
        raise MasteryMapError("Chinese concept copy must exactly cover the knowledge registry.")


def build_visual_mastery_map_model(
    *, map_model: dict[str, Any], concept_copy_data: dict[str, Any], knowledge_data: dict[str, Any], selected_concept_id: Any, stage_names: dict[int, str] | None = None
) -> dict[str, Any]:
    """Build a deterministic render snapshot from existing registry-derived data."""
    validate_concept_copy_zh(concept_copy_data, knowledge_data)
    if not isinstance(map_model, dict) or not isinstance(map_model.get("nodes_by_id"), dict):
        raise MasteryMapError("map_model is invalid for visualization.")
    effective_stage_names = LAYER_STAGE_NAMES if stage_names is None else stage_names
    nodes_by_id = deepcopy(map_model["nodes_by_id"])
    known_ids = set(nodes_by_id)
    if not known_ids:
        raise MasteryMapError("map_model does not contain nodes.")
    if not isinstance(selected_concept_id, str) or selected_concept_id not in known_ids:
        selected_concept_id = None
    summaries = {item["concept_id"]: item["summary_zh"] for item in concept_copy_data["concepts"]}
    dependents: dict[str, list[str]] = {concept_id: [] for concept_id in known_ids}
    edges: list[dict[str, Any]] = []
    edge_pairs: set[tuple[str, str]] = set()
    for edge in map_model.get("prerequisite_edges", []):
        if not isinstance(edge, tuple) or len(edge) != 2:
            raise MasteryMapError("Mastery-map prerequisite edge is invalid.")
        prerequisite_id, dependent_id = edge
        if prerequisite_id not in known_ids or dependent_id not in known_ids:
            raise MasteryMapError("Mastery-map prerequisite edge references an unknown concept.")
        if prerequisite_id == dependent_id or (prerequisite_id, dependent_id) in edge_pairs:
            raise MasteryMapError("Mastery-map prerequisite edges must be unique non-self edges.")
        edge_pairs.add((prerequisite_id, dependent_id))
        dependents[prerequisite_id].append(dependent_id)
        edges.append(
            {
                "prerequisite_id": prerequisite_id,
                "dependent_id": dependent_id,
                "is_selected_incident": selected_concept_id in {prerequisite_id, dependent_id},
            }
        )
    for concept_id, node in nodes_by_id.items():
        prerequisite_ids = node.get("prerequisite_ids")
        if not isinstance(prerequisite_ids, list) or any(item not in known_ids for item in prerequisite_ids):
            raise MasteryMapError("Mastery-map node prerequisites are invalid.")
        node["summary_zh"] = summaries[concept_id]
        node["dependent_ids"] = sorted(dependents[concept_id], key=lambda item: _node_order(nodes_by_id[item]))
        node["is_selected"] = concept_id == selected_concept_id
    layers = []
    for raw_layer in map_model.get("layers", []):
        if not isinstance(raw_layer, dict) or not isinstance(raw_layer.get("layer"), int):
            raise MasteryMapError("Mastery-map layer is invalid for visualization.")
        layer = raw_layer["layer"]
        if layer not in effective_stage_names:
            raise MasteryMapError(f"No student stage name for layer {layer}.")
        raw_nodes = raw_layer.get("nodes")
        if not isinstance(raw_nodes, list):
            raise MasteryMapError("Mastery-map layer nodes are invalid for visualization.")
        layer_nodes = [deepcopy(nodes_by_id[item["concept_id"]]) for item in raw_nodes]
        layers.append({"layer": layer, "stage_name": effective_stage_names[layer], "nodes": layer_nodes})
    actual_layers = {layer["layer"] for layer in layers}
    if actual_layers != set(effective_stage_names):
        raise MasteryMapError("Student stage names must exactly cover the fixed map layers.")
    presentation_model = deepcopy(map_model)
    presentation_model["nodes_by_id"] = deepcopy(nodes_by_id)
    presentation_model["layers"] = deepcopy(layers)
    focus = _build_focus(nodes_by_id=nodes_by_id, selected_concept_id=selected_concept_id)
    visual = {
        "map_model": presentation_model,
        "layers": layers,
        "nodes_by_id": deepcopy(nodes_by_id),
        "edges": edges,
        "selected_concept_id": selected_concept_id,
        "focus": focus,
        "summary": _build_progress_summary(nodes_by_id),
    }
    visual["global_dot"] = build_global_mastery_dot(visual)
    return visual


def filter_layered_nodes(layers: Any, *, filter_key: str) -> list[dict[str, Any]]:
    """Filter only presentation layers; selection and domain state remain untouched."""
    if filter_key not in LAYER_FILTERS:
        raise MasteryMapError("Unknown mastery-map layer filter.")
    if not isinstance(layers, list):
        raise MasteryMapError("Mastery-map layers are invalid for filtering.")
    result: list[dict[str, Any]] = []
    for layer in layers:
        if not isinstance(layer, dict) or not isinstance(layer.get("nodes"), list):
            raise MasteryMapError("Mastery-map layer is invalid for filtering.")
        nodes = [deepcopy(node) for node in layer["nodes"] if _matches_filter(node, filter_key)]
        if nodes:
            result.append({"layer": layer["layer"], "stage_name": layer["stage_name"], "nodes": nodes})
    return result


def build_global_mastery_dot(visual_model: dict[str, Any]) -> str:
    """Render a stable raw-DOT overview without learner content or external resources."""
    nodes_by_id = visual_model.get("nodes_by_id") if isinstance(visual_model, dict) else None
    layers = visual_model.get("layers") if isinstance(visual_model, dict) else None
    edges = visual_model.get("edges") if isinstance(visual_model, dict) else None
    if not isinstance(nodes_by_id, dict) or not isinstance(layers, list) or not isinstance(edges, list):
        raise MasteryMapError("visual mastery-map model is invalid for DOT generation.")
    ordered_nodes = sorted(nodes_by_id.values(), key=_node_order)
    aliases = {node["concept_id"]: f"n{index}" for index, node in enumerate(ordered_nodes)}
    if len(aliases) != len(nodes_by_id):
        raise MasteryMapError("visual mastery-map node IDs are invalid.")
    lines = [
        "digraph MasteryMap {",
        '  graph [rankdir=TB, bgcolor="transparent", pad="0.25", nodesep="0.22", ranksep="0.48", splines=polyline];',
        '  node [shape=box, style="rounded,filled", fontname="sans-serif", fontsize=13, margin="0.14,0.10"];',
        '  edge [arrowhead=vee, arrowsize=0.65];',
    ]
    for layer in layers:
        node_aliases = [aliases[node["concept_id"]] for node in layer["nodes"]]
        lines.append("  { rank=same; " + "; ".join(node_aliases) + "; }")
    for node in ordered_nodes:
        mastery = node.get("mastery")
        status = mastery.get("status") if isinstance(mastery, dict) else "unavailable"
        token = GRAPH_VISUAL_TOKENS.get(status, GRAPH_VISUAL_TOKENS["unavailable"])
        label = _graph_node_label(node)
        border = "#1D4ED8" if node.get("is_selected") else ("#7C3AED" if node.get("is_recommended") else token["border"])
        penwidth = "3.0" if node.get("is_selected") else ("2.3" if node.get("is_recommended") else "1.1")
        lines.append(
            f'  {aliases[node["concept_id"]]} [label="{dot_escape(label)}", fillcolor="{token["fill"]}", '
            f'color="{border}", fontcolor="{token["font"]}", penwidth={penwidth}];'
        )
    for edge in sorted(edges, key=lambda item: (item["prerequisite_id"], item["dependent_id"])):
        source = edge.get("prerequisite_id")
        destination = edge.get("dependent_id")
        if source not in aliases or destination not in aliases:
            raise MasteryMapError("visual mastery-map edge is invalid for DOT generation.")
        if edge.get("is_selected_incident"):
            edge_style = 'color="#1D4ED8", penwidth=2.4'
        else:
            edge_style = 'color="#AAB7C4", penwidth=0.8'
        lines.append(f"  {aliases[source]} -> {aliases[destination]} [{edge_style}];")
    lines.append("}")
    return "\n".join(lines)


def dot_escape(value: str) -> str:
    """Escape a plain DOT string label; HTML and user-provided labels are unsupported."""
    if not isinstance(value, str):
        raise MasteryMapError("DOT label must be a string.")
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("<", "＜")
        .replace(">", "＞")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _build_focus(*, nodes_by_id: dict[str, dict[str, Any]], selected_concept_id: str | None) -> dict[str, Any] | None:
    if selected_concept_id is None:
        return None
    selected = nodes_by_id[selected_concept_id]
    return {
        "selected": deepcopy(selected),
        "prerequisites": [deepcopy(nodes_by_id[item]) for item in selected["prerequisite_ids"]],
        "dependents": [deepcopy(nodes_by_id[item]) for item in selected["dependent_ids"]],
    }


def _build_progress_summary(nodes_by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(nodes_by_id), "tracked": 0, "untracked": 0, "review": 0, "developing": 0, "steady": 0, "covered": 0}
    for node in nodes_by_id.values():
        mastery = node.get("mastery") if isinstance(node, dict) else None
        status = mastery.get("status") if isinstance(mastery, dict) else "unavailable"
        if status == "untracked":
            counts["untracked"] += 1
        elif mastery and mastery.get("is_tracked"):
            counts["tracked"] += 1
        if status in {"review", "developing", "steady"}:
            counts[status] += 1
        coverage = node.get("coverage") if isinstance(node, dict) else None
        if isinstance(coverage, dict) and coverage.get("available") is True:
            counts["covered"] += 1
    return counts


def _matches_filter(node: Any, filter_key: str) -> bool:
    if not isinstance(node, dict):
        return False
    if filter_key == "all":
        return True
    if filter_key == "recommended":
        return node.get("is_recommended") is True
    if filter_key == "tracked":
        mastery = node.get("mastery")
        return isinstance(mastery, dict) and mastery.get("is_tracked") is True
    if filter_key == "covered":
        coverage = node.get("coverage")
        return isinstance(coverage, dict) and coverage.get("available") is True
    mastery = node.get("mastery")
    return isinstance(mastery, dict) and mastery.get("status") == "review"


def _graph_node_label(node: dict[str, Any]) -> str:
    mastery = node["mastery"]
    coverage_line = "可诊断" if node["coverage"]["available"] else "无审核题"
    return "\n".join([node["title_zh"], mastery["label"], coverage_line])


def _node_order(node: dict[str, Any]) -> tuple[int, int, str]:
    concept_id = node.get("concept_id") if isinstance(node, dict) else None
    layer = node.get("layer") if isinstance(node, dict) else None
    order = node.get("order") if isinstance(node, dict) else None
    if not isinstance(concept_id, str) or not isinstance(layer, int) or not isinstance(order, int):
        raise MasteryMapError("visual mastery-map node order is invalid.")
    return layer, order, concept_id
