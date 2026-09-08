from pathlib import Path
import json

import pytest

import introai_tutor.course_material_preview as preview


SOURCE_FILE = "ai_lec2_uninformed_search.pdf"


def _manifest(path: Path, *, page_count: int = 2) -> Path:
    document = {
        "schema_version": 1,
        "materials": [
            {
                "material_id": "course_core_ai_lec2_uninformed_search",
                "source_role": "course_core",
                "source_file": SOURCE_FILE,
                "sha256": "0" * 64,
                "size_bytes": 1,
                "page_count": page_count,
                "allowed_page_range": {"page_start": 1, "page_end": page_count},
                "provenance_note": "synthetic test material",
            }
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _citation(*, page_start=1, page_end=1, source_file=SOURCE_FILE, source_role="course_core"):
    return {
        "chunk_id": "synthetic_chunk",
        "source_file": source_file,
        "source_role": source_role,
        "page_start": page_start,
        "page_end": page_end,
    }


def _materials(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "materials"
    source_dir = root / "course_core"
    source_dir.mkdir(parents=True)
    (source_dir / SOURCE_FILE).write_bytes(b"synthetic-not-a-real-pdf")
    manifest = _manifest(tmp_path / "manifest.json")
    return root, manifest


def test_runtime_root_is_trimmed_without_loading_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv(preview.COURSE_MATERIALS_ROOT_ENV, f"  {tmp_path}\r\n")
    assert preview.configured_materials_root() == tmp_path


def test_valid_manifest_source_resolves_under_configured_root(tmp_path):
    root, manifest = _materials(tmp_path)
    resolved = preview.resolve_course_source(
        source_file=SOURCE_FILE,
        source_role="course_core",
        materials_root=root,
        manifest_path=manifest,
    )
    assert resolved.path == (root / "course_core" / SOURCE_FILE).resolve()
    assert resolved.page_count == 2


@pytest.mark.parametrize(
    "source_file",
    [
        "../../.env",
        "../.git/config",
        "/etc/passwd",
        "/home/user/.env",
        r"C:\\Users\\secret.pdf",
        "file:///etc/passwd",
        "evil.pdf",
    ],
)
def test_source_resolver_rejects_arbitrary_and_traversal_identifiers(tmp_path, source_file):
    root, manifest = _materials(tmp_path)
    with pytest.raises(preview.CourseMaterialPreviewError) as error:
        preview.resolve_course_source(
            source_file=source_file,
            source_role="course_core",
            materials_root=root,
            manifest_path=manifest,
        )
    assert error.value.code == "invalid_source"


def test_symlink_escape_is_rejected_when_supported(tmp_path):
    root, manifest = _materials(tmp_path)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    target = root / "course_core" / SOURCE_FILE
    target.unlink()
    try:
        target.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    with pytest.raises(preview.CourseMaterialPreviewError) as error:
        preview.resolve_course_source(
            source_file=SOURCE_FILE,
            source_role="course_core",
            materials_root=root,
            manifest_path=manifest,
        )
    assert error.value.code == "source_outside_root"


@pytest.mark.parametrize("page_start,page_end", [(0, 1), (-1, 1), (1, 3), (1.5, 2), ("1", 1)])
def test_page_validation_is_strict_and_one_based(tmp_path, page_start, page_end):
    root, manifest = _materials(tmp_path)
    with pytest.raises(preview.CourseMaterialPreviewError) as error:
        preview.render_course_page(
            _citation(page_start=page_start, page_end=page_end),
            materials_root=root,
            manifest_path=manifest,
        )
    assert error.value.code == "invalid_page"


def test_missing_material_root_is_graceful(monkeypatch):
    monkeypatch.delenv(preview.COURSE_MATERIALS_ROOT_ENV, raising=False)
    result = preview.preview_citation(_citation())
    assert result.available is False
    assert result.error_code == "material_root_unconfigured"
    assert "无法预览" in preview.preview_unavailable_message()


def test_missing_pdf_is_graceful(tmp_path):
    manifest = _manifest(tmp_path / "manifest.json")
    root = tmp_path / "materials"
    root.mkdir()
    result = preview.preview_citation(
        _citation(), materials_root=root, manifest_path=manifest
    )
    assert result.available is False
    assert result.error_code == "source_unavailable"


def test_relative_material_root_is_rejected_to_avoid_cwd_dependency(tmp_path):
    _, manifest = _materials(tmp_path)
    with pytest.raises(preview.CourseMaterialPreviewError) as error:
        preview.resolve_course_source(
            source_file=SOURCE_FILE,
            source_role="course_core",
            materials_root="local_materials",
            manifest_path=manifest,
        )
    assert error.value.code == "source_unavailable"


def test_renderer_unavailable_is_graceful(monkeypatch, tmp_path):
    root, manifest = _materials(tmp_path)
    monkeypatch.setattr(preview.shutil, "which", lambda _: None)
    result = preview.preview_citation(
        _citation(), materials_root=root, manifest_path=manifest
    )
    assert result.available is False
    assert result.error_code == "renderer_unavailable"


def test_normal_render_uses_only_the_selected_physical_page_and_returns_png(monkeypatch, tmp_path):
    root, manifest = _materials(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        output_prefix = Path(command[-1])
        output_prefix.with_suffix(".png").write_bytes(b"PNG-page-2")
        return object()

    monkeypatch.setattr(preview.shutil, "which", lambda _: "/usr/bin/pdftoppm")
    monkeypatch.setattr(preview.subprocess, "run", fake_run)
    result = preview.render_course_page(
        _citation(page_start=1, page_end=2),
        page=2,
        materials_root=root,
        manifest_path=manifest,
    )
    assert result.available is True
    assert result.page == 2
    assert result.image_bytes == b"PNG-page-2"
    command, kwargs = commands[0]
    assert command[1:6] == ["-f", "2", "-l", "2", "-png"]
    assert command[0] == "/usr/bin/pdftoppm"
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 15.0


def test_render_defaults_to_citation_start_and_rejects_pages_outside_the_range(
    monkeypatch, tmp_path
):
    root, manifest = _materials(tmp_path)
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        Path(command[-1]).with_suffix(".png").write_bytes(b"PNG")
        return object()

    monkeypatch.setattr(preview.shutil, "which", lambda _: "/usr/bin/pdftoppm")
    monkeypatch.setattr(preview.subprocess, "run", fake_run)
    citation = _citation(page_start=1, page_end=2)

    assert preview.render_course_page(
        citation, materials_root=root, manifest_path=manifest
    ).page == 1
    assert len(commands) == 1
    assert commands[0][1:6] == ["-f", "1", "-l", "1", "-png"]

    for page in (0, 3, "2"):
        unavailable = preview.preview_citation(
            citation, page=page, materials_root=root, manifest_path=manifest
        )
        assert unavailable.available is False
        assert unavailable.error_code == "invalid_page"


def test_timeout_and_nonzero_renderer_fail_closed(monkeypatch, tmp_path):
    root, manifest = _materials(tmp_path)
    monkeypatch.setattr(preview.shutil, "which", lambda _: "/usr/bin/pdftoppm")

    def timeout(*_args, **_kwargs):
        raise preview.subprocess.TimeoutExpired("pdftoppm", 15)

    monkeypatch.setattr(preview.subprocess, "run", timeout)
    assert preview.preview_citation(
        _citation(), materials_root=root, manifest_path=manifest
    ).error_code == "render_timeout"

    def failure(*_args, **_kwargs):
        raise preview.subprocess.CalledProcessError(1, "pdftoppm")

    monkeypatch.setattr(preview.subprocess, "run", failure)
    assert preview.preview_citation(
        _citation(), materials_root=root, manifest_path=manifest
    ).error_code == "render_failed"


def test_preview_key_isolated_for_multiple_citations_and_same_chunk():
    citation = _citation()
    assert preview.citation_preview_key(citation, 0) != preview.citation_preview_key(citation, 1)
