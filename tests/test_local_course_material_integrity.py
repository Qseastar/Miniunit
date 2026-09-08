"""Tests for optional local-PDF integrity verification without real PDFs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.course_material_manifest import CourseMaterialManifestError
from tools.verify_local_course_materials import (
    LocalMaterialIntegrityError,
    verify_local_course_materials,
)


def _write_manifest(path: Path, *, content: bytes = b"verified material") -> Path:
    path.write_text(json.dumps({
        "schema_version": 1,
        "materials": [{
            "material_id": "synthetic_material",
            "source_role": "course_core",
            "source_file": "synthetic.pdf",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "page_count": 7,
            "allowed_page_range": {"page_start": 1, "page_end": 7},
            "provenance_note": "Synthetic test metadata only.",
        }],
    }), encoding="utf-8")
    return path


def _page_counter(_: Path) -> int:
    return 7


def test_available_local_material_matches_hash_size_and_page_count(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    material = tmp_path / "materials" / "course_core" / "synthetic.pdf"
    material.parent.mkdir(parents=True)
    material.write_bytes(b"verified material")
    result = verify_local_course_materials(
        manifest_path=manifest, materials_root=tmp_path / "materials", require=True, page_counter=_page_counter
    )
    assert result == {
        "status": "pass",
        "verified_materials": ["course_core/synthetic.pdf"],
        "missing_materials": [],
        "required": True,
    }


def test_missing_material_is_unavailable_only_when_not_required(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    optional = verify_local_course_materials(
        manifest_path=manifest, materials_root=tmp_path / "missing", page_counter=_page_counter
    )
    assert optional["status"] == "unavailable"
    assert optional["missing_materials"] == ["course_core/synthetic.pdf"]
    with pytest.raises(LocalMaterialIntegrityError, match="Required local course materials"):
        verify_local_course_materials(
            manifest_path=manifest, materials_root=tmp_path / "wrong-root", require=True, page_counter=_page_counter
        )


@pytest.mark.parametrize("content, message", [(b"tampered material", "SHA-256"), (b"longer verified material", "size")])
def test_available_material_mismatch_fails_closed(tmp_path, content, message):
    manifest = _write_manifest(tmp_path / "manifest.json")
    material = tmp_path / "materials" / "course_core" / "synthetic.pdf"
    material.parent.mkdir(parents=True)
    material.write_bytes(content)
    with pytest.raises(LocalMaterialIntegrityError, match=message):
        verify_local_course_materials(
            manifest_path=manifest, materials_root=tmp_path / "materials", require=False, page_counter=_page_counter
        )


def test_page_count_and_manifest_schema_fail_closed(tmp_path):
    manifest = _write_manifest(tmp_path / "manifest.json")
    material = tmp_path / "materials" / "course_core" / "synthetic.pdf"
    material.parent.mkdir(parents=True)
    material.write_bytes(b"verified material")
    with pytest.raises(LocalMaterialIntegrityError, match="page count"):
        verify_local_course_materials(
            manifest_path=manifest, materials_root=tmp_path / "materials", page_counter=lambda _: 6
        )
    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(CourseMaterialManifestError):
        verify_local_course_materials(
            manifest_path=manifest, materials_root=tmp_path / "materials", page_counter=_page_counter
        )
