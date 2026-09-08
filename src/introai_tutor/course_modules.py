"""Validated registry and loader for independently reviewed course modules.

The registry deliberately owns only package location and display metadata.  It
does not create a second learner-state, scoring, or recommendation policy:
concept and template IDs remain global across one course, while a selected
module provides the bounded data used for one QA or verification interaction.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from introai_tutor.course_materials import load_course_chunks
from introai_tutor.knowledge import load_knowledge_points, validate_knowledge_points
from introai_tutor.questions import validate_diagnostic_questions
from introai_tutor.template_selection import load_diagnostic_templates

try:
    from tools.course_material_manifest import (
        CourseMaterialManifestError,
        load_course_material_manifest,
        material_index,
        validate_chunk_material_coverage,
    )
except ImportError:  # pragma: no cover - repository-root execution is required
    CourseMaterialManifestError = ValueError
    load_course_material_manifest = None  # type: ignore[assignment]
    material_index = None  # type: ignore[assignment]
    validate_chunk_material_coverage = None  # type: ignore[assignment]


MODULE_REGISTRY_SCHEMA_VERSION = 1
DEFAULT_MODULE_ID = "search_algorithms"
REGISTRY_FILENAME = Path("data/course_modules.json")
_REGISTRY_FIELDS = {"schema_version", "course_id", "modules"}
_MODULE_REQUIRED_FIELDS = {
    "module_id",
    "display_name_zh",
    "display_name_en",
    "unit_ids",
    "knowledge_points_path",
    "course_chunks_path",
    "diagnostic_templates_path",
    "course_material_manifest_path",
    "default_diagnostic_concept_ids",
}
_MODULE_OPTIONAL_FIELDS = {
    "formative_questions_path",
    "formative_tracks_path",
    "default_formative_track_id",
    "mastery_map_layout_path",
    "concept_copy_zh_path",
    "mastery_map_stage_names",
}
_PATH_FIELDS = {
    "knowledge_points_path",
    "course_chunks_path",
    "diagnostic_templates_path",
    "course_material_manifest_path",
    "formative_questions_path",
    "formative_tracks_path",
    "mastery_map_layout_path",
    "concept_copy_zh_path",
}


class CourseModuleError(ValueError):
    """Raised when module registration or a module data package is invalid."""


def load_course_module_registry(root: str | Path) -> dict[str, Any]:
    """Load the one tracked course-module registry beneath a repository root."""
    root_path = _validate_root(root)
    path = root_path / REGISTRY_FILENAME
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CourseModuleError("Course module registry is missing.") from error
    except json.JSONDecodeError as error:
        raise CourseModuleError("Course module registry is not valid JSON.") from error
    return validate_course_module_registry(document, root=root_path)


def validate_course_module_registry(
    document: Any, *, root: str | Path | None = None
) -> dict[str, Any]:
    """Strictly validate the small routing registry without loading packages."""
    if not isinstance(document, dict) or set(document) != _REGISTRY_FIELDS:
        raise CourseModuleError("Course module registry has an invalid top-level schema.")
    if document.get("schema_version") != MODULE_REGISTRY_SCHEMA_VERSION:
        raise CourseModuleError("Unsupported course module registry schema_version.")
    course_id = _text(document.get("course_id"), "course_id")
    modules = document.get("modules")
    if not isinstance(modules, list) or not modules:
        raise CourseModuleError("Course module registry modules must be a non-empty list.")

    root_path = _validate_root(root) if root is not None else None
    module_ids: set[str] = set()
    unit_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, module in enumerate(modules):
        label = f"modules[{index}]"
        if not isinstance(module, dict) or set(module) - _MODULE_OPTIONAL_FIELDS != _MODULE_REQUIRED_FIELDS:
            raise CourseModuleError(f"{label} has an invalid schema.")
        module_id = _identifier(module.get("module_id"), f"{label}.module_id")
        if module_id in module_ids:
            raise CourseModuleError("Course module IDs must be globally unique.")
        module_ids.add(module_id)
        item = {
            "module_id": module_id,
            "display_name_zh": _text(module.get("display_name_zh"), f"{label}.display_name_zh"),
            "display_name_en": _text(module.get("display_name_en"), f"{label}.display_name_en"),
            "unit_ids": _identifier_list(module.get("unit_ids"), f"{label}.unit_ids"),
            "default_diagnostic_concept_ids": _identifier_list(
                module.get("default_diagnostic_concept_ids"),
                f"{label}.default_diagnostic_concept_ids",
            ),
        }
        duplicate_units = unit_ids.intersection(item["unit_ids"])
        if duplicate_units:
            raise CourseModuleError("unit_ids must be globally unique across modules.")
        unit_ids.update(item["unit_ids"])
        for field in _PATH_FIELDS:
            if field not in module:
                continue
            path = _relative_json_path(module[field], f"{label}.{field}")
            if root_path is not None:
                _resolve_under_root(root_path, path)
            item[field] = path.as_posix()
        formative_fields = {
            "formative_questions_path",
            "formative_tracks_path",
            "default_formative_track_id",
        }
        present_formative = formative_fields.intersection(module)
        if present_formative and present_formative != formative_fields:
            raise CourseModuleError(
                f"{label} formative configuration must contain questions, tracks, and track ID together."
            )
        if present_formative:
            item["default_formative_track_id"] = _identifier(
                module["default_formative_track_id"], f"{label}.default_formative_track_id"
            )
        map_fields = {"mastery_map_layout_path", "concept_copy_zh_path"}
        present_map = map_fields.intersection(module)
        if present_map and present_map != map_fields:
            raise CourseModuleError(
                f"{label} mastery-map configuration must contain layout and concept copy together."
            )
        if "mastery_map_stage_names" in module:
            item["mastery_map_stage_names"] = _stage_names(
                module["mastery_map_stage_names"], f"{label}.mastery_map_stage_names"
            )
        normalized.append(item)
    return {
        "schema_version": MODULE_REGISTRY_SCHEMA_VERSION,
        "course_id": course_id,
        "modules": normalized,
    }


def resolve_course_module(registry: dict[str, Any], module_id: str | None = None) -> dict[str, Any]:
    """Return one registered module; omitted IDs retain Search compatibility."""
    normalized = validate_course_module_registry(registry)
    requested = DEFAULT_MODULE_ID if module_id is None else _identifier(module_id, "module_id")
    for module in normalized["modules"]:
        if module["module_id"] == requested:
            return deepcopy(module)
    raise CourseModuleError("Unknown course module ID.")


def module_selector_options(registry: dict[str, Any]) -> list[dict[str, str]]:
    """Return stable, student-facing module selector options."""
    normalized = validate_course_module_registry(registry)
    return [
        {
            "module_id": module["module_id"],
            "display_name_zh": module["display_name_zh"],
            "display_name_en": module["display_name_en"],
        }
        for module in normalized["modules"]
    ]


def load_course_module_data(root: str | Path, module_id: str | None = None) -> dict[str, Any]:
    """Load one isolated module package and verify its internal references."""
    root_path = _validate_root(root)
    registry = load_course_module_registry(root_path)
    module = resolve_course_module(registry, module_id)
    paths = {
        key: _resolve_under_root(root_path, Path(value))
        for key, value in module.items()
        if key in _PATH_FIELDS
    }
    try:
        knowledge_data = load_knowledge_points(paths["knowledge_points_path"])
        _validate_module_course_metadata(
            module=module, registry=registry, knowledge_data=knowledge_data
        )
        manifest = _load_manifest(paths["course_material_manifest_path"])
        allowed_sources = set(material_index(manifest))
        course_data = load_course_chunks(
            paths["course_chunks_path"], knowledge_data, allowed_sources=allowed_sources
        )
        _validate_manifest_coverage(course_data, manifest)
        if course_data["course_id"] != registry["course_id"]:
            raise CourseModuleError("Module course_chunks course_id does not match registry.")
        if course_data["unit_id"] not in module["unit_ids"]:
            raise CourseModuleError("Module course_chunks unit_id is not registered for this module.")

        questions_data = tracks_data = None
        misconception_ids: set[str] | None = None
        if "formative_questions_path" in paths:
            questions_data = _load_json(paths["formative_questions_path"])
            tracks_data = _load_json(paths["formative_tracks_path"])
            validate_diagnostic_questions(questions_data, knowledge_data)
            misconception_ids = {
                item["id"]
                for question in questions_data["diagnostic_questions"]
                for item in question.get("assessment", {}).get("blocking_misconceptions", [])
            }
        valid_concept_ids = {point["id"] for point in knowledge_data["knowledge_points"]}
        templates_data = load_diagnostic_templates(
            paths["diagnostic_templates_path"],
            valid_concept_ids=valid_concept_ids,
            valid_misconception_ids=misconception_ids,
        )
        if not set(module["default_diagnostic_concept_ids"]).issubset(valid_concept_ids):
            raise CourseModuleError("default_diagnostic_concept_ids contains an unknown module concept.")
    except (OSError, json.JSONDecodeError, ValueError, CourseMaterialManifestError) as error:
        if isinstance(error, CourseModuleError):
            raise
        raise CourseModuleError(f"Course module data is invalid: {error}") from None
    return {
        "module": deepcopy(module),
        "registry_course_id": registry["course_id"],
        "paths": paths,
        "knowledge_data": deepcopy(knowledge_data),
        "course_data": deepcopy(course_data),
        "templates_data": deepcopy(templates_data),
        "questions_data": deepcopy(questions_data),
        "tracks_data": deepcopy(tracks_data),
        "misconception_ids": None if misconception_ids is None else set(misconception_ids),
    }


def load_all_course_module_data(root: str | Path) -> list[dict[str, Any]]:
    """Load all packages and reject cross-module concept/template collisions."""
    root_path = _validate_root(root)
    registry = load_course_module_registry(root_path)
    bundles = [load_course_module_data(root_path, item["module_id"]) for item in registry["modules"]]
    concept_ids: set[str] = set()
    template_ids: set[str] = set()
    for bundle in bundles:
        for point in bundle["knowledge_data"]["knowledge_points"]:
            if point["id"] in concept_ids:
                raise CourseModuleError("concept IDs must be globally unique across modules.")
            concept_ids.add(point["id"])
        for template in bundle["templates_data"]["templates"]:
            if template["id"] in template_ids:
                raise CourseModuleError("template IDs must be globally unique across modules.")
            template_ids.add(template["id"])
    return bundles


def aggregate_module_knowledge_data(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine registered concept registries for global learner-state validation."""
    if not isinstance(bundles, list) or not bundles:
        raise CourseModuleError("bundles must be a non-empty list.")
    course_ids = {bundle.get("registry_course_id") for bundle in bundles}
    if len(course_ids) != 1 or not isinstance(next(iter(course_ids)), str):
        raise CourseModuleError("All module bundles must belong to one course.")
    points = [
        deepcopy(point)
        for bundle in bundles
        for point in bundle["knowledge_data"]["knowledge_points"]
    ]
    document = {
        "schema_version": "module_registry_aggregate_v1",
        "course": {
            "course_id": next(iter(course_ids)),
            "course_name": "Introduction to Artificial Intelligence",
            "unit": "all_registered_modules",
            "version": "module_registry_aggregate_v1",
        },
        "knowledge_points": points,
    }
    try:
        validate_knowledge_points(document)
    except ValueError as error:
        raise CourseModuleError(f"Aggregated knowledge data is invalid: {error}") from None
    return document


def aggregate_template_ids(bundles: list[dict[str, Any]]) -> set[str]:
    """Return globally validated reviewed template IDs for persistence/exposure."""
    if not isinstance(bundles, list) or not bundles:
        raise CourseModuleError("bundles must be a non-empty list.")
    identifiers = {
        template["id"]
        for bundle in bundles
        for template in bundle["templates_data"]["templates"]
    }
    if not identifiers:
        raise CourseModuleError("Registered modules must provide reviewed templates.")
    return identifiers


def _validate_module_course_metadata(
    *, module: dict[str, Any], registry: dict[str, Any], knowledge_data: dict[str, Any]
) -> None:
    course = knowledge_data.get("course")
    if not isinstance(course, dict) or course.get("course_id") != registry["course_id"]:
        raise CourseModuleError("Module knowledge_points course_id does not match registry.")
    if not isinstance(course.get("unit"), str) or not course["unit"].strip():
        raise CourseModuleError("Module knowledge_points unit is invalid.")


def _load_manifest(path: Path) -> dict[str, Any]:
    if load_course_material_manifest is None or material_index is None:
        raise CourseModuleError("Course material manifest loader is unavailable.")
    return load_course_material_manifest(path)


def _validate_manifest_coverage(course_data: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Keep module chunks inside their own manifest's source and page bounds."""
    if material_index is None or validate_chunk_material_coverage is None:
        raise CourseModuleError("Course material manifest validator is unavailable.")
    chunks = {chunk["id"]: chunk for chunk in course_data["chunks"]}
    issues = validate_chunk_material_coverage(chunks, material_index(manifest))
    if issues:
        raise CourseModuleError("Course material manifest coverage failed: " + "; ".join(issues))


def _validate_root(root: str | Path | None) -> Path:
    if not isinstance(root, (str, Path)) or not str(root).strip():
        raise CourseModuleError("root must be a repository directory.")
    path = Path(root).resolve()
    if not path.is_dir():
        raise CourseModuleError("root must be a repository directory.")
    return path


def _resolve_under_root(root: Path, relative_path: Path) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise CourseModuleError("Module data path must stay within the repository root.") from None
    return candidate


def _relative_json_path(value: Any, field_name: str) -> Path:
    text = _text(value, field_name)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise CourseModuleError(f"{field_name} must be a repository-relative JSON path.")
    return path


def _identifier_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) != len(set(value)):
        raise CourseModuleError(f"{field_name} must be a non-empty unique identifier list.")
    return [_identifier(item, field_name) for item in value]


def _identifier(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    if any(character.isspace() for character in text):
        raise CourseModuleError(f"{field_name} must not contain whitespace.")
    return text


def _stage_names(value: Any, field_name: str) -> dict[int, str]:
    if not isinstance(value, dict) or not value:
        raise CourseModuleError(f"{field_name} must be a non-empty object.")
    result: dict[int, str] = {}
    for key, name in value.items():
        if isinstance(key, int) and not isinstance(key, bool):
            layer = key
        elif isinstance(key, str) and key.isdigit():
            layer = int(key)
        else:
            raise CourseModuleError(f"{field_name} keys must be non-negative integer strings.")
        if layer < 0:
            raise CourseModuleError(f"{field_name} keys must be non-negative integer strings.")
        result[layer] = _text(name, f"{field_name}.{key}")
    return result


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CourseModuleError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "DEFAULT_MODULE_ID",
    "MODULE_REGISTRY_SCHEMA_VERSION",
    "CourseModuleError",
    "aggregate_module_knowledge_data",
    "aggregate_template_ids",
    "load_all_course_module_data",
    "load_course_module_data",
    "load_course_module_registry",
    "module_selector_options",
    "resolve_course_module",
    "validate_course_module_registry",
]
