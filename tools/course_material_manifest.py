"""Validate tracked metadata for local, untracked course PDFs."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any


MANIFEST_SCHEMA_VERSION = 1
SOURCE_ROLES = {"course_core", "prerequisite_support"}
_TOP_LEVEL_KEYS = {"schema_version", "materials"}
_MATERIAL_KEYS = {
    "material_id",
    "source_role",
    "source_file",
    "sha256",
    "size_bytes",
    "page_count",
    "allowed_page_range",
    "provenance_note",
}
_PAGE_RANGE_KEYS = {"page_start", "page_end"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CourseMaterialManifestError(ValueError):
    """Raised when tracked course-material metadata is malformed."""


def load_course_material_manifest(path: str | Path) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CourseMaterialManifestError(f"Course material manifest is missing: {Path(path)}") from error
    except json.JSONDecodeError as error:
        raise CourseMaterialManifestError("Course material manifest is not valid JSON.") from error
    return validate_course_material_manifest(document)


def validate_course_material_manifest(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        raise CourseMaterialManifestError("Course material manifest has an invalid top-level schema.")
    if document.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise CourseMaterialManifestError("Unsupported course material manifest schema_version.")
    materials = document.get("materials")
    if not isinstance(materials, list) or not materials:
        raise CourseMaterialManifestError("Course material manifest materials must be a non-empty list.")

    material_ids: set[str] = set()
    source_pairs: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for index, material in enumerate(materials):
        label = f"materials[{index}]"
        if not isinstance(material, dict) or set(material) != _MATERIAL_KEYS:
            raise CourseMaterialManifestError(f"{label} has an invalid schema.")
        material_id = material["material_id"]
        source_role = material["source_role"]
        source_file = material["source_file"]
        sha256 = material["sha256"]
        size_bytes = material["size_bytes"]
        page_count = material["page_count"]
        page_range = material["allowed_page_range"]
        note = material["provenance_note"]
        if not isinstance(material_id, str) or not material_id.strip() or material_id in material_ids:
            raise CourseMaterialManifestError(f"{label} material_id must be unique and non-empty.")
        if source_role not in SOURCE_ROLES:
            raise CourseMaterialManifestError(f"{label} source_role is invalid.")
        if (
            not isinstance(source_file, str)
            or Path(source_file).name != source_file
            or not source_file.endswith(".pdf")
        ):
            raise CourseMaterialManifestError(f"{label} source_file must be a PDF basename.")
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise CourseMaterialManifestError(f"{label} sha256 must be a lowercase SHA-256 digest.")
        if type(size_bytes) is not int or size_bytes <= 0:
            raise CourseMaterialManifestError(f"{label} size_bytes must be a positive integer.")
        if type(page_count) is not int or page_count <= 0:
            raise CourseMaterialManifestError(f"{label} page_count must be a positive integer.")
        if not isinstance(page_range, dict) or set(page_range) != _PAGE_RANGE_KEYS:
            raise CourseMaterialManifestError(f"{label} allowed_page_range is invalid.")
        start, end = page_range["page_start"], page_range["page_end"]
        if type(start) is not int or type(end) is not int or start < 1 or end < start or end > page_count:
            raise CourseMaterialManifestError(f"{label} allowed_page_range is outside page_count.")
        if not isinstance(note, str) or not note.strip():
            raise CourseMaterialManifestError(f"{label} provenance_note must be non-empty.")
        pair = (source_role, source_file)
        if pair in source_pairs:
            raise CourseMaterialManifestError(f"{label} source_role/source_file must be unique.")
        material_ids.add(material_id)
        source_pairs.add(pair)
        normalized.append(deepcopy(material))
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "materials": normalized}


def material_index(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    validated = validate_course_material_manifest(document)
    return {
        (material["source_role"], material["source_file"]): material
        for material in validated["materials"]
    }


def validate_chunk_material_coverage(
    chunks: dict[str, dict[str, Any]],
    materials: dict[tuple[str, str], dict[str, Any]],
) -> list[str]:
    """Ensure the tracked chunk inventory and manifest describe the same materials."""
    chunk_pairs: set[tuple[str, str]] = set()
    issues: list[str] = []
    for chunk_id, chunk in chunks.items():
        role, source_file = chunk.get("source_role"), chunk.get("source_file")
        if not isinstance(role, str) or not isinstance(source_file, str):
            issues.append(f"CHUNK_SOURCE_SCHEMA_INVALID: {chunk_id}")
            continue
        pair = (role, source_file)
        chunk_pairs.add(pair)
        material = materials.get(pair)
        if material is None:
            issues.append(f"CHUNK_MATERIAL_UNKNOWN: {chunk_id}")
            continue
        page_start, page_end = chunk.get("page_start"), chunk.get("page_end")
        allowed = material["allowed_page_range"]
        if (
            type(page_start) is not int
            or type(page_end) is not int
            or page_start < allowed["page_start"]
            or page_end > allowed["page_end"]
        ):
            issues.append(f"CHUNK_PAGE_OUTSIDE_MATERIAL: {chunk_id}")
    for role, source_file in sorted(set(materials) - chunk_pairs):
        issues.append(f"MATERIAL_NOT_REFERENCED_BY_CHUNKS: {role}/{source_file}")
    return issues


def validate_source_material(
    *,
    chunk: dict[str, Any],
    source_file: str,
    page_start: int,
    page_end: int,
    materials: dict[tuple[str, str], dict[str, Any]],
) -> list[str]:
    """Validate source-ref material identity and physical pages without opening a PDF."""
    role = chunk.get("source_role")
    if not isinstance(role, str):
        return ["SOURCE_CHUNK_ROLE_INVALID"]
    material = materials.get((role, source_file))
    if material is None:
        if any(item_file == source_file for _, item_file in materials):
            return ["SOURCE_MATERIAL_ROLE_MISMATCH"]
        return ["SOURCE_MATERIAL_UNKNOWN"]
    allowed = material["allowed_page_range"]
    if page_start < allowed["page_start"] or page_end > allowed["page_end"]:
        return ["SOURCE_PAGE_OUTSIDE_MATERIAL"]
    return []
