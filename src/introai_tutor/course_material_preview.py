"""Secure, optional server-side previews for cited course-material pages.

The preview boundary deliberately accepts only validated citation metadata.  A
student-facing citation can identify a source and physical page, but it never
becomes a filesystem path or a public HTTP endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Mapping

try:  # The repository already uses this tracked manifest validator.
    from tools.course_material_manifest import (
        CourseMaterialManifestError,
        load_course_material_manifest,
        material_index,
    )
except ImportError:  # pragma: no cover - only relevant outside the repository root
    CourseMaterialManifestError = ValueError
    load_course_material_manifest = None  # type: ignore[assignment]
    material_index = None  # type: ignore[assignment]


COURSE_MATERIALS_ROOT_ENV = "INTROAI_COURSE_MATERIALS_DIR"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = _PROJECT_ROOT / "data" / "course_material_manifest.json"
_ALLOWED_SOURCE_ROLES = frozenset({"course_core", "prerequisite_support"})
_PREVIEW_ERROR_MESSAGE = (
    "当前无法预览这条课件引用，你仍可根据上方文件名和页码查看原课件。"
)


class CourseMaterialPreviewError(ValueError):
    """A safe, categorized failure at the optional preview boundary."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or _PREVIEW_ERROR_MESSAGE)


@dataclass(frozen=True)
class ResolvedCourseSource:
    """A manifest-approved source resolved beneath the configured root."""

    source_role: str
    source_file: str
    path: Path
    page_count: int


@dataclass(frozen=True)
class CoursePagePreview:
    """Safe result returned to the UI; no error contains a local path."""

    available: bool
    source_file: str | None = None
    source_role: str | None = None
    page: int | None = None
    image_bytes: bytes | None = None
    mime_type: str | None = None
    error_code: str | None = None


def configured_materials_root(
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Read the optional runtime root without loading or executing ``.env``."""

    values = os.environ if environment is None else environment
    raw_value = values.get(COURSE_MATERIALS_ROOT_ENV, "")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    return Path(raw_value.strip()).expanduser()


def citation_preview_key(citation: Mapping[str, Any], index: int) -> str:
    """Return a stable per-citation UI key without exposing source metadata."""

    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError("citation index must be a non-negative integer.")
    chunk_id = citation.get("chunk_id") if isinstance(citation, Mapping) else None
    identity = chunk_id if isinstance(chunk_id, str) and chunk_id else str(index)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"introai_citation_preview_{index}_{digest}"


def resolve_course_source(
    *,
    source_file: Any,
    source_role: Any,
    materials_root: str | Path,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> ResolvedCourseSource:
    """Resolve a manifest-approved PDF under ``materials_root``.

    The source identifier must be a known PDF basename.  Roles determine the
    only permitted subdirectory; user-provided path fragments are rejected.
    """

    _validate_source_identity(source_file, source_role)
    if not isinstance(materials_root, (str, Path)) or not str(materials_root).strip():
        raise CourseMaterialPreviewError("material_root_unconfigured")
    root = Path(materials_root).expanduser()
    if not root.is_absolute():
        # The runtime contract is a directory identity, not a path relative to
        # whichever working directory happens to launch Streamlit.
        raise CourseMaterialPreviewError("source_unavailable")
    try:
        root_resolved = root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise CourseMaterialPreviewError("source_unavailable") from None
    if not root_resolved.is_dir():
        raise CourseMaterialPreviewError("source_unavailable")

    materials = _load_material_index(manifest_path)
    material = materials.get((source_role, source_file))
    if material is None:
        raise CourseMaterialPreviewError("invalid_source")
    page_count = material.get("page_count")
    if type(page_count) is not int or page_count <= 0:
        raise CourseMaterialPreviewError("manifest_invalid")

    candidate = root_resolved / source_role / source_file
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise CourseMaterialPreviewError("source_unavailable") from None
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise CourseMaterialPreviewError("source_outside_root") from None
    if not resolved.is_file():
        raise CourseMaterialPreviewError("source_unavailable")
    return ResolvedCourseSource(source_role, source_file, resolved, page_count)


def validate_citation_page(
    *,
    page_start: Any,
    page_end: Any,
    page_count: int,
) -> int:
    """Validate one-based physical citation pages and return the first page."""

    if type(page_count) is not int or page_count <= 0:
        raise CourseMaterialPreviewError("manifest_invalid")
    if type(page_start) is not int or page_start < 1:
        raise CourseMaterialPreviewError("invalid_page")
    if type(page_end) is not int or page_end < page_start:
        raise CourseMaterialPreviewError("invalid_page")
    if page_end > page_count:
        raise CourseMaterialPreviewError("invalid_page")
    return page_start


def render_course_page(
    citation: Mapping[str, Any],
    *,
    page: int | None = None,
    materials_root: str | Path | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    timeout_seconds: float = 15.0,
) -> CoursePagePreview:
    """Render one validated physical page from a citation's stated range.

    ``page`` is intentionally not a general PDF page selector.  When present,
    it must be an integer within the already validated ``page_start`` to
    ``page_end`` citation range.  The source resolver and manifest bounds are
    still checked for every lazy render.
    """

    if not isinstance(citation, Mapping):
        raise CourseMaterialPreviewError("invalid_citation")
    root = configured_materials_root() if materials_root is None else materials_root
    if root is None:
        raise CourseMaterialPreviewError("material_root_unconfigured")
    source = resolve_course_source(
        source_file=citation.get("source_file"),
        source_role=citation.get("source_role"),
        materials_root=root,
        manifest_path=manifest_path,
    )
    citation_start = validate_citation_page(
        page_start=citation.get("page_start"),
        page_end=citation.get("page_end"),
        page_count=source.page_count,
    )
    citation_end = citation.get("page_end")
    if page is None:
        selected_page = citation_start
    elif type(page) is int and citation_start <= page <= citation_end:
        selected_page = page
    else:
        raise CourseMaterialPreviewError("invalid_page")
    # Preserve the manifest-bound physical-page validation for the selected
    # page as well as for the citation range above.
    validate_citation_page(
        page_start=selected_page,
        page_end=selected_page,
        page_count=source.page_count,
    )
    if (
        type(timeout_seconds) not in (int, float)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
        or timeout_seconds > 60
    ):
        raise CourseMaterialPreviewError("invalid_render_timeout")
    renderer = shutil.which("pdftoppm")
    if renderer is None:
        raise CourseMaterialPreviewError("renderer_unavailable")

    try:
        with tempfile.TemporaryDirectory(prefix="introai_course_preview_") as directory:
            output_prefix = Path(directory) / "page"
            subprocess.run(
                [
                    renderer,
                    "-f",
                    str(selected_page),
                    "-l",
                    str(selected_page),
                    "-png",
                    "-singlefile",
                    str(source.path),
                    str(output_prefix),
                ],
                check=True,
                capture_output=True,
                timeout=float(timeout_seconds),
            )
            image_path = output_prefix.with_suffix(".png")
            image_bytes = image_path.read_bytes()
    except subprocess.TimeoutExpired:
        raise CourseMaterialPreviewError("render_timeout") from None
    except (OSError, subprocess.CalledProcessError):
        raise CourseMaterialPreviewError("render_failed") from None
    if not image_bytes:
        raise CourseMaterialPreviewError("render_failed")
    return CoursePagePreview(
        available=True,
        source_file=source.source_file,
        source_role=source.source_role,
        page=selected_page,
        image_bytes=image_bytes,
        mime_type="image/png",
    )


def preview_citation(
    citation: Mapping[str, Any],
    *,
    page: int | None = None,
    materials_root: str | Path | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> CoursePagePreview:
    """Return a graceful unavailable result for any optional preview failure."""

    try:
        return render_course_page(
            citation,
            page=page,
            materials_root=materials_root,
            manifest_path=manifest_path,
        )
    except CourseMaterialPreviewError as error:
        return CoursePagePreview(available=False, error_code=error.code)


def preview_unavailable_message() -> str:
    """Return the single safe student-facing fallback message."""

    return _PREVIEW_ERROR_MESSAGE


def _validate_source_identity(source_file: Any, source_role: Any) -> None:
    if not isinstance(source_file, str) or not source_file.strip():
        raise CourseMaterialPreviewError("invalid_source")
    if (
        Path(source_file).name != source_file
        or "/" in source_file
        or "\\" in source_file
        or ":" in source_file
        or source_file.startswith(".")
        or not source_file.endswith(".pdf")
    ):
        raise CourseMaterialPreviewError("invalid_source")
    if source_role not in _ALLOWED_SOURCE_ROLES:
        raise CourseMaterialPreviewError("invalid_source")


def _load_material_index(manifest_path: str | Path) -> dict[tuple[str, str], dict[str, Any]]:
    if load_course_material_manifest is None or material_index is None:
        raise CourseMaterialPreviewError("manifest_unavailable")
    try:
        manifest = load_course_material_manifest(manifest_path)
        return material_index(manifest)
    except (OSError, CourseMaterialManifestError, ValueError, TypeError):
        raise CourseMaterialPreviewError("manifest_invalid") from None


__all__ = [
    "COURSE_MATERIALS_ROOT_ENV",
    "CourseMaterialPreviewError",
    "CoursePagePreview",
    "ResolvedCourseSource",
    "configured_materials_root",
    "citation_preview_key",
    "resolve_course_source",
    "validate_citation_page",
    "render_course_page",
    "preview_citation",
    "preview_unavailable_message",
]
