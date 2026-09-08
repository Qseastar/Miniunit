"""Pure display helpers for the Streamlit MVP."""

from __future__ import annotations

import re
from typing import Any


_SOURCE_ROLE_LABELS = {
    "course_core": "课程核心材料",
    "prerequisite_support": "先修补充材料",
}

_MISCONCEPTION_LABELS = {
    "bfs_is_depth_first": "把 BFS 误解为沿一条路径深度优先扩展",
    "bfs_always_cost_optimal": "认为 BFS 在任意边权下都保证总代价最优",
    "ucs_uses_depth_or_step_count": "把 UCS 误解为按深度或步数选择节点",
}

_STATUS_LABELS = {
    "answered": "已回答",
    "out_of_scope": "超出课程范围",
    "needs_clarification": "需要澄清",
    "insufficient_evidence": "课件证据不足",
    "diagnostic_available": "可开始审核诊断",
}

# Streamlit renders student-facing answer strings as Markdown.  An unescaped
# ``A*`` can be paired with a later asterisk in the same answer and therefore
# be parsed as emphasis instead of the algorithm name.  Keep this deliberately
# narrow: normal Markdown (including bold text and lists) remains available.
_ASTAR_MARKDOWN_TOKEN = re.compile(r"(?<!\\)A\*(?!\*)")
_MARKDOWN_CODE_SEGMENT = re.compile(r"(```[\s\S]*?```|`[^`\n]*`)")


def format_pages(page_start: int, page_end: int) -> str:
    """Format a one-based PDF page or page range."""
    if not _positive_int(page_start) or not _positive_int(page_end) or page_end < page_start:
        raise ValueError("page range must contain positive ordered integers.")
    if page_start == page_end:
        return f"第 {page_start} 页"
    return f"第 {page_start}–{page_end} 页"


def source_role_label(source_role: str) -> str:
    """Return a safe Chinese label for a course-material source role."""
    if not isinstance(source_role, str):
        return "未知材料"
    return _SOURCE_ROLE_LABELS.get(source_role, source_role or "未知材料")


def mastery_rows(learner_state: dict, knowledge_data: dict) -> list[dict[str, Any]]:
    """Build rows only for concepts explicitly present in learner mastery."""
    points = {
        point["id"]: point
        for point in knowledge_data.get("knowledge_points", [])
        if isinstance(point, dict) and isinstance(point.get("id"), str)
    }
    rows: list[dict[str, Any]] = []
    for concept_id, mastery in learner_state.get("mastery", {}).items():
        point = points.get(concept_id)
        if point is None:
            continue
        rows.append(
            {
                "concept_id": concept_id,
                "title_zh": concept_display_name(concept_id, knowledge_data),
                "title_en": point.get("title_en", concept_id),
                "mastery": mastery,
            }
        )
    return rows


def tracked_mastery_count(learner_state: dict) -> int:
    """Return the number of concepts explicitly tracked in mastery."""
    mastery = learner_state.get("mastery", {})
    return len(mastery) if isinstance(mastery, dict) else 0


def update_rows(state_update: dict, knowledge_data: dict) -> list[dict[str, Any]]:
    """Add readable titles to the P5B update trace."""
    points = {
        point["id"]: point
        for point in knowledge_data.get("knowledge_points", [])
        if isinstance(point, dict) and isinstance(point.get("id"), str)
    }
    rows: list[dict[str, Any]] = []
    for update in state_update.get("updates", []):
        concept_id = update.get("concept_id")
        point = points.get(concept_id, {})
        rows.append(
            {
                **update,
                "title_zh": concept_display_name(concept_id, knowledge_data),
                "title_en": point.get("title_en", concept_id),
            }
        )
    return rows


def concept_display_name(concept_id: Any, knowledge_data: Any) -> str:
    """Return the authoritative Chinese label, never exposing an unknown ID to students."""
    if not isinstance(concept_id, str) or not concept_id.strip():
        return "未知知识点"
    points = knowledge_data.get("knowledge_points", []) if isinstance(knowledge_data, dict) else []
    if not isinstance(points, list):
        return "未知知识点"
    for point in points:
        if not isinstance(point, dict) or point.get("id") != concept_id:
            continue
        title = point.get("title_zh")
        if isinstance(title, str) and title.strip() and title.strip() != concept_id:
            return title.strip()
        return "未命名知识点"
    return "未知知识点"


def format_concept_label(concept_id: Any, knowledge_data: Any, *, developer: bool = False) -> str:
    """Format a student label, optionally retaining the stable ID for developer views."""
    label = concept_display_name(concept_id, knowledge_data)
    if developer and isinstance(concept_id, str) and concept_id.strip():
        return f"{label}（{concept_id}）"
    return label


def misconception_label(misconception_id: str) -> str:
    """Return a known Chinese label, safely falling back to the raw ID."""
    if not isinstance(misconception_id, str):
        return str(misconception_id)
    return _MISCONCEPTION_LABELS.get(misconception_id, misconception_id)


def status_label(status: str) -> str:
    """Return a Chinese QA status label with safe fallback."""
    if not isinstance(status, str):
        return "未知状态"
    return _STATUS_LABELS.get(status, status)


def choice_text_by_id(choices: Any) -> dict[str, str]:
    """Return a display-safe choice-ID to choice-text mapping.

    The UI submits the stable ID to the deterministic scorer but must never
    use that internal ID as the student-facing option label.
    """
    if not isinstance(choices, list) or not choices:
        raise ValueError("choices must be a non-empty list.")
    result: dict[str, str] = {}
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {"id", "text"}:
            raise ValueError("choice has an invalid schema.")
        choice_id, text = choice["id"], choice["text"]
        if (
            not isinstance(choice_id, str)
            or not choice_id.strip()
            or not isinstance(text, str)
            or not text.strip()
            or choice_id in result
        ):
            raise ValueError("choice has an invalid id or text.")
        result[choice_id] = text
    return result


def citation_rows(response: dict) -> list[dict[str, Any]]:
    """Return a deterministic, de-duplicated display view of citations.

    The grounded-answer service keeps model-selected citations attached to
    their answer blocks.  This UI-only projection neither adds evidence nor
    changes that provenance.  It does make an identical set of cited physical
    pages display in a stable order, regardless of the model's block order.
    """

    rows_by_page: dict[tuple[Any, ...], dict[str, Any]] = {}
    for block in response.get("answer_blocks", []):
        for citation in block.get("citations", []):
            key = (
                citation.get("source_role"),
                citation.get("source_file"),
                citation.get("page_start"),
                citation.get("page_end"),
            )
            row = {
                **citation,
                "source_role_label": source_role_label(citation.get("source_role")),
                "pages": format_pages(citation["page_start"], citation["page_end"]),
            }
            # Citation rows are a display view.  Do not mutate the response or
            # citation evidence held by the service layer.
            if isinstance(row.get("section_title"), str):
                row["section_title"] = escape_algorithm_markdown_tokens(
                    row["section_title"]
                )
            existing = rows_by_page.get(key)
            if existing is None or _citation_display_identity(row) < _citation_display_identity(existing):
                # Two chunks can describe the same physical PDF range. Display
                # that reference once; choose its metadata deterministically.
                rows_by_page[key] = row
    return sorted(rows_by_page.values(), key=_citation_display_identity)


def _citation_display_identity(citation: dict[str, Any]) -> tuple[Any, ...]:
    """Return a fixed, source-first key for already validated citation rows."""

    role = citation.get("source_role")
    role_rank = 0 if role == "course_core" else 1
    return (
        role_rank,
        citation.get("source_file", ""),
        citation.get("page_start", 0),
        citation.get("page_end", 0),
        citation.get("chunk_id", ""),
        citation.get("section_title", ""),
    )


def format_qa_result(result: dict) -> dict[str, Any]:
    """Return a small UI-safe view of a TutorService result."""
    response = result.get("response", {})
    status = response.get("status", "unknown")
    return {
        "status": status,
        "status_label": status_label(status),
        "answer": escape_algorithm_markdown_tokens(
            hide_internal_chunk_citations(response.get("answer", ""), response)
        ),
        "citations": citation_rows(response),
        "limitations": list(response.get("limitations", [])),
    }


def escape_algorithm_markdown_tokens(text: Any) -> Any:
    """Escape the literal asterisk in ``A*`` for Markdown display only.

    The helper leaves Markdown code spans/fences untouched because their
    contents are already literal.  It is intentionally not a general Markdown
    escaping function: student-visible bold text, lists, links and other
    formatting continue to render normally.
    """
    if not isinstance(text, str) or not text:
        return text

    parts = _MARKDOWN_CODE_SEGMENT.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = _ASTAR_MARKDOWN_TOKEN.sub(r"A\\*", parts[index])
    return "".join(parts)


def hide_internal_chunk_citations(text: str, response: dict) -> str:
    """Remove only known chunk IDs shown as inline citation markers.

    Chunk identifiers are implementation details; formal citation rows remain
    available separately.  Matching is deliberately limited to IDs present
    in this response, so ordinary parenthesized prose is untouched.
    """
    if not isinstance(text, str) or not text:
        return text
    if not isinstance(response, dict):
        return text

    chunk_ids: set[str] = set()
    used_chunk_ids = response.get("used_chunk_ids", [])
    if isinstance(used_chunk_ids, list):
        chunk_ids.update(item for item in used_chunk_ids if isinstance(item, str) and item)
    blocks = response.get("answer_blocks", [])
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            citations = block.get("citations", [])
            if not isinstance(citations, list):
                continue
            for citation in citations:
                if isinstance(citation, dict):
                    chunk_id = citation.get("chunk_id")
                    if isinstance(chunk_id, str) and chunk_id:
                        chunk_ids.add(chunk_id)
    # Keep the helper compatible with response views that expose a flattened
    # citations collection in addition to the grounded answer blocks.
    citations = response.get("citations", [])
    if isinstance(citations, list):
        for citation in citations:
            if isinstance(citation, dict):
                chunk_id = citation.get("chunk_id")
                if isinstance(chunk_id, str) and chunk_id:
                    chunk_ids.add(chunk_id)
    if not chunk_ids:
        return text

    alternatives = "|".join(
        re.escape(chunk_id) for chunk_id in sorted(chunk_ids, key=len, reverse=True)
    )
    marker = re.compile(
        rf"(?:\(\s*(?:{alternatives})\s*\)|（\s*(?:{alternatives})\s*）"
        rf"|\[\s*(?:{alternatives})\s*\]|【\s*(?:{alternatives})\s*】)"
    )
    cleaned = marker.sub("", text)
    # Only tidy whitespace directly left by a removed marker.  Ordinary
    # punctuation and Markdown brackets are not matched or rewritten.
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def reset_session_state(session_state: Any) -> None:
    """Clear only IntroAI MVP keys from a Streamlit-like session mapping."""
    for key in (
        "introai_learner_state",
        "introai_diagnostic_session",
        "introai_diagnostic_result",
        "introai_last_qa_result",
        "introai_qa_error",
        "introai_qa_retry_state",
        "introai_qa_question",
        "introai_qa_input_session_token",
        "introai_last_qa_elapsed",
        "introai_citation_preview",
        "introai_citation_preview_scroll_revision",
        "introai_diagnostic_error",
        "introai_diagnostic_answer",
        "introai_diagnostic_flash",
        "introai_dual_track_result",
        "introai_dual_track_session",
        "introai_dual_track_diagnostic_workflow",
        "introai_last_recommendation",
        "introai_diagnostic_mode",
        "introai_formative_feedback_error",
        "introai_qa_diagnostic_plan",
        "introai_pending_diagnostic_plan",
        "introai_diagnostic_origin",
        "introai_handoff_source_topic_ids",
        "introai_completed_verification_summaries",
        "introai_returned_to_qa",
        "introai_confirm_clear_learning_records",
        "introai_pending_persistence",
        "introai_persistence_warning",
        "introai_scroll_request",
        "introai_scroll_consumed_events",
        "introai_qa_result_revision",
        "introai_mastery_map_selected_concept",
        "introai_mastery_map_action_revision",
        "introai_mastery_map_view",
        "introai_mastery_map_layer_filter",
        "introai_mastery_map_static_inputs",
        "introai_mastery_map_navigation_message",
        "introai_pending_mastery_map_qa_question",
        "introai_selected_module_id",
        "introai_module_selector",
        "introai_shared_deepseek_configuration_error",
    ):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        if isinstance(key, str) and (
            key.startswith("introai_qa_question_")
            or
            key.startswith("introai_diagnostic_answer_")
            or key.startswith("introai_formative_answer_")
            or key.startswith("introai_verification_")
        ):
            session_state.pop(key, None)


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
