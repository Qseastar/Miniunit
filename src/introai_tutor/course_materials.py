"""Load and validate one registered module's local course-material chunks."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from introai_tutor.knowledge import validate_knowledge_points


REQUIRED_TOP_LEVEL_FIELDS = {"schema_version", "course_id", "unit_id", "chunks"}
REQUIRED_CHUNK_FIELDS = {
    "id",
    "source_file",
    "page_start",
    "page_end",
    "section_title",
    "topic_ids",
    "support_tags",
    "keywords",
    "content",
    "language",
    "source_role",
    "content_type",
    "review_status",
}

ALLOWED_SOURCE_FILES = {
    "ai_lec2_uninformed_search.pdf",
    "ai_lec3_informed_search.pdf",
    "ai_lec4_local_search_and_llm_search.pdf",
    "ai_lec5_adversarial_search.pdf",
    "ai_lec6_mcts_and_search_summary.pdf",
    "ds_stack_queue_priority_queue.pdf",
    "ds_tree_traversal_heap.pdf",
    "ds_graph_traversal_shortest_path.pdf",
}
COURSE_CORE_SOURCE_FILES = {
    "ai_lec2_uninformed_search.pdf",
    "ai_lec3_informed_search.pdf",
    "ai_lec4_local_search_and_llm_search.pdf",
    "ai_lec5_adversarial_search.pdf",
    "ai_lec6_mcts_and_search_summary.pdf",
}
ALLOWED_LANGUAGES = {"zh", "en", "bilingual"}
ALLOWED_SOURCE_ROLES = {"course_core", "prerequisite_support"}
ALLOWED_CONTENT_TYPES = {
    "definition",
    "algorithm",
    "property",
    "comparison",
    "example",
    "complexity",
    "implementation_support",
    "application",
    "historical_context",
}
ALLOWED_REVIEW_STATUSES = {
    "codex_draft",
    "human_verified",
    "needs_human_review",
}


class CourseMaterialValidationError(ValueError):
    """Raised when course chunk data is invalid."""


def load_course_chunks(
    path: str | Path,
    knowledge_data: dict[str, Any],
    *,
    allowed_sources: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Load and validate a course-chunk JSON document."""
    with Path(path).open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    validate_course_chunks(data, knowledge_data, allowed_sources=allowed_sources)
    return data


def validate_course_chunks(
    data: dict[str, Any],
    knowledge_data: dict[str, Any],
    *,
    verify_local_sources: bool = False,
    local_materials_root: str | Path | None = None,
    allowed_sources: set[tuple[str, str]] | None = None,
) -> None:
    """Validate chunk schema and, optionally, local PDF page bounds.

    Local-source verification is opt-in because ``local_materials`` is not part
    of the repository and therefore is unavailable to ordinary CI runs.
    """
    validate_knowledge_points(knowledge_data)

    if not isinstance(data, dict):
        raise CourseMaterialValidationError("Course material data must be an object.")

    missing_top_level = REQUIRED_TOP_LEVEL_FIELDS - set(data)
    if missing_top_level:
        missing = ", ".join(sorted(missing_top_level))
        raise CourseMaterialValidationError(
            f"Course material data is missing required fields: {missing}"
        )

    for field_name in ("schema_version", "course_id", "unit_id"):
        _validate_non_empty_string(data[field_name], field_name)

    chunks = data["chunks"]
    if not isinstance(chunks, list) or not chunks:
        raise CourseMaterialValidationError("'chunks' must be a non-empty list.")

    valid_topic_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
    normalized_allowed_sources = _validate_allowed_sources(allowed_sources)
    chunk_ids: set[str] = set()
    source_page_limits = (
        _load_source_page_limits(local_materials_root, normalized_allowed_sources)
        if verify_local_sources
        else {}
    )

    for index, chunk in enumerate(chunks):
        _validate_chunk(
            chunk,
            index=index,
            chunk_ids=chunk_ids,
            valid_topic_ids=valid_topic_ids,
            source_page_limits=source_page_limits,
            allowed_sources=normalized_allowed_sources,
        )


def get_course_chunk(data: dict[str, Any], chunk_id: str) -> dict[str, Any]:
    """Return a chunk by ID."""
    for chunk in data.get("chunks", []):
        if chunk.get("id") == chunk_id:
            return chunk
    raise CourseMaterialValidationError(f"Unknown course chunk id: {chunk_id}")


def get_chunks_by_topic(data: dict[str, Any], topic_id: str) -> list[dict[str, Any]]:
    """Return chunks associated with a knowledge-point ID in document order."""
    return [
        chunk
        for chunk in data.get("chunks", [])
        if topic_id in chunk.get("topic_ids", [])
    ]


def _validate_chunk(
    chunk: Any,
    *,
    index: int,
    chunk_ids: set[str],
    valid_topic_ids: set[str],
    source_page_limits: dict[tuple[str, str], int],
    allowed_sources: set[tuple[str, str]],
) -> None:
    if not isinstance(chunk, dict):
        raise CourseMaterialValidationError(f"Chunk at index {index} must be an object.")

    missing_fields = REQUIRED_CHUNK_FIELDS - set(chunk)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise CourseMaterialValidationError(
            f"Chunk at index {index} is missing required fields: {missing}"
        )

    chunk_id = chunk["id"]
    _validate_non_empty_string(chunk_id, f"Chunk at index {index} id")
    if chunk_id in chunk_ids:
        raise CourseMaterialValidationError(f"Duplicate course chunk id: {chunk_id}")
    chunk_ids.add(chunk_id)

    source_file = chunk["source_file"]
    _validate_non_empty_string(source_file, f"Chunk '{chunk_id}' source_file")
    _validate_enum(chunk["source_role"], "source_role", chunk_id, ALLOWED_SOURCE_ROLES)
    if (chunk.get("source_role"), source_file) not in allowed_sources:
        raise CourseMaterialValidationError(
            f"Chunk '{chunk_id}' has unsupported source_file: {source_file}"
        )

    _validate_page_range(chunk, chunk_id)
    source_identity = (chunk["source_role"], source_file)
    if source_page_limits and chunk["page_end"] > source_page_limits[source_identity]:
        raise CourseMaterialValidationError(
            f"Chunk '{chunk_id}' page_end exceeds local source page count for {source_file}."
        )

    _validate_non_empty_string(chunk["section_title"], f"Chunk '{chunk_id}' section_title")
    _validate_non_empty_string(chunk["content"], f"Chunk '{chunk_id}' content")
    _validate_string_list(chunk["topic_ids"], f"Chunk '{chunk_id}' topic_ids", non_empty=True)
    _validate_string_list(chunk["keywords"], f"Chunk '{chunk_id}' keywords", non_empty=True)
    _validate_string_list(chunk["support_tags"], f"Chunk '{chunk_id}' support_tags")

    for topic_id in chunk["topic_ids"]:
        if topic_id not in valid_topic_ids:
            raise CourseMaterialValidationError(
                f"Chunk '{chunk_id}' has unknown topic id: {topic_id}"
            )

    _validate_enum(chunk["language"], "language", chunk_id, ALLOWED_LANGUAGES)
    _validate_enum(chunk["content_type"], "content_type", chunk_id, ALLOWED_CONTENT_TYPES)
    _validate_enum(chunk["review_status"], "review_status", chunk_id, ALLOWED_REVIEW_STATUSES)


def _validate_page_range(chunk: dict[str, Any], chunk_id: str) -> None:
    start = chunk["page_start"]
    end = chunk["page_end"]
    if isinstance(start, bool) or not isinstance(start, int) or start <= 0:
        raise CourseMaterialValidationError(
            f"Chunk '{chunk_id}' page_start must be a positive integer."
        )
    if isinstance(end, bool) or not isinstance(end, int) or end < start:
        raise CourseMaterialValidationError(
            f"Chunk '{chunk_id}' page_end must be an integer not smaller than page_start."
        )


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CourseMaterialValidationError(f"{field_name} must be a non-empty string.")


def _validate_string_list(value: Any, field_name: str, *, non_empty: bool = False) -> None:
    if not isinstance(value, list) or (non_empty and not value):
        qualifier = "a non-empty list" if non_empty else "a list"
        raise CourseMaterialValidationError(f"{field_name} must be {qualifier}.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CourseMaterialValidationError(f"{field_name} must contain non-empty strings.")


def _validate_enum(value: Any, field_name: str, chunk_id: str, allowed: set[str]) -> None:
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise CourseMaterialValidationError(
            f"Chunk '{chunk_id}' has invalid {field_name}. Expected one of: {options}"
        )


def _load_source_page_limits(
    local_materials_root: str | Path | None,
    allowed_sources: set[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    if local_materials_root is None:
        raise CourseMaterialValidationError(
            "local_materials_root is required when verify_local_sources is enabled."
        )

    root = Path(local_materials_root)
    limits: dict[tuple[str, str], int] = {}
    for source_directory, source_file in sorted(allowed_sources):
        source_path = root / source_directory / source_file
        if not source_path.is_file():
            raise CourseMaterialValidationError(
                f"Expected local source file at {source_directory}/{source_file}."
            )
        try:
            result = subprocess.run(
                ["pdfinfo", str(source_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            raise CourseMaterialValidationError(
                f"Could not read local PDF metadata for {source_file}."
            ) from None

        page_match = re.search(r"^Pages:\s+(\d+)$", result.stdout, re.MULTILINE)
        if not page_match:
            raise CourseMaterialValidationError(
                f"Could not determine page count for {source_file}."
            )
        limits[(source_directory, source_file)] = int(page_match.group(1))
    return limits


def _validate_allowed_sources(value: set[tuple[str, str]] | None) -> set[tuple[str, str]]:
    """Use module manifest pairs when supplied, else preserve Search defaults."""
    if value is None:
        return {
            (
                "course_core" if source_file in COURSE_CORE_SOURCE_FILES else "prerequisite_support",
                source_file,
            )
            for source_file in ALLOWED_SOURCE_FILES
        }
    if not isinstance(value, set) or not value:
        raise CourseMaterialValidationError("allowed_sources must be a non-empty source-role/file set.")
    normalized: set[tuple[str, str]] = set()
    for pair in value:
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or pair[0] not in ALLOWED_SOURCE_ROLES
            or not isinstance(pair[1], str)
            or not pair[1].strip()
            or Path(pair[1]).name != pair[1]
            or not pair[1].endswith(".pdf")
        ):
            raise CourseMaterialValidationError("allowed_sources contains an invalid source identity.")
        normalized.add((pair[0], pair[1]))
    return normalized
