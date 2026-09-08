"""Tracked source metadata is strict even when PDFs are unavailable in CI."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.course_material_manifest import (
    CourseMaterialManifestError,
    load_course_material_manifest,
    material_index,
    validate_chunk_material_coverage,
    validate_course_material_manifest,
    validate_source_material,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "course_material_manifest.json"
CHUNKS = {
    item["id"]: item
    for item in json.loads((ROOT / "data" / "course_chunks.json").read_text(encoding="utf-8"))["chunks"]
}


def _manifest() -> dict:
    return load_course_material_manifest(MANIFEST_PATH)


def test_tracked_manifest_is_complete_for_real_chunk_sources_and_contains_no_pdf_content():
    manifest = _manifest()
    materials = material_index(manifest)
    assert len(materials) == 8
    assert validate_chunk_material_coverage(CHUNKS, materials) == []
    assert {key for item in manifest["materials"] for key in item} == {
        "material_id", "source_role", "source_file", "sha256", "size_bytes",
        "page_count", "allowed_page_range", "provenance_note",
    }
    assert all("/" not in item["source_file"] and "\\" not in item["source_file"] for item in manifest["materials"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["materials"].append(deepcopy(value["materials"][0])),
        lambda value: value["materials"][0].__setitem__("sha256", "not-a-digest"),
        lambda value: value["materials"][0].__setitem__("source_file", "/tmp/course.pdf"),
        lambda value: value["materials"][0].__setitem__("size_bytes", True),
        lambda value: value["materials"][0]["allowed_page_range"].__setitem__("page_end", 999),
        lambda value: value["materials"][0].__setitem__("pdf_content", "not allowed"),
    ],
)
def test_manifest_rejects_invalid_or_content_bearing_entries(mutate):
    invalid = deepcopy(_manifest())
    mutate(invalid)
    with pytest.raises(CourseMaterialManifestError):
        validate_course_material_manifest(invalid)


def test_source_material_validation_rejects_unknown_role_mismatch_and_page_overflow():
    materials = material_index(_manifest())
    chunk = deepcopy(CHUNKS["lec2_bfs_layer_order"])
    assert validate_source_material(
        chunk=chunk,
        source_file="unknown.pdf",
        page_start=31,
        page_end=31,
        materials=materials,
    ) == ["SOURCE_MATERIAL_UNKNOWN"]
    assert validate_source_material(
        chunk={**chunk, "source_role": "prerequisite_support"},
        source_file=chunk["source_file"],
        page_start=31,
        page_end=31,
        materials=materials,
    ) == ["SOURCE_MATERIAL_ROLE_MISMATCH"]
    assert validate_source_material(
        chunk=chunk,
        source_file=chunk["source_file"],
        page_start=31,
        page_end=999,
        materials=materials,
    ) == ["SOURCE_PAGE_OUTSIDE_MATERIAL"]


def test_chunk_coverage_rejects_unknown_or_unreferenced_materials():
    materials = material_index(_manifest())
    unknown_chunks = {"unknown": {"source_role": "course_core", "source_file": "missing.pdf", "page_start": 1, "page_end": 1}}
    assert validate_chunk_material_coverage(unknown_chunks, materials)[0] == "CHUNK_MATERIAL_UNKNOWN: unknown"
