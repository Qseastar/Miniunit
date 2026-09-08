"""Offline contract tests for registry-bounded course modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import app as streamlit_app

from introai_tutor.app_services import (
    AppServiceError,
    build_diagnostic_handoff_service,
    build_dual_track_diagnostic_workflow,
    build_question_answer_service,
    load_global_learning_catalog,
    load_module_app_package,
    load_registered_module_options,
)
from introai_tutor.course_modules import (
    CourseModuleError,
    load_all_course_module_data,
    load_course_module_data,
    load_course_module_registry,
)
from introai_tutor.learner import validate_learner_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _ModuleAdapter:
    """Answer one synthetic module question without a network request."""

    def __init__(self, concept_id: str, chunk_id: str) -> None:
        self.concept_id = concept_id
        self.chunk_id = chunk_id
        self.system_prompts: list[str] = []

    def complete_json(self, *, system_prompt: str, **_: Any) -> dict[str, Any]:
        self.system_prompts.append(system_prompt)
        if len(self.system_prompts) == 1:
            return {
                "in_scope": True,
                "intent": "definition",
                "topic_ids": [self.concept_id],
                "diagnostic_topic_ids": [self.concept_id],
                "supporting_topic_ids": [],
                "search_terms": ["synthetic concept"],
                "needs_clarification": False,
                "clarifying_question": None,
                "confidence": 0.9,
            }
        return {
            "status": "answered",
            "answer_blocks": [
                {"text": "Synthetic grounded answer.", "citation_ids": [self.chunk_id]}
            ],
            "limitations": [],
            "confidence": 0.9,
        }


class _StateOnlyStreamlit:
    def __init__(self, session_state: dict[str, Any]) -> None:
        self.session_state = session_state


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _module_files(root: Path, *, module_id: str, unit_id: str, concept_id: str) -> dict[str, str]:
    prefix = module_id
    source_file = f"{prefix}.pdf"
    chunk_id = f"{prefix}_chunk"
    template_id = f"verify_{prefix}_choice_v1"
    _write_json(
        root / "data" / f"{prefix}_knowledge.json",
        {
            "schema_version": "0.1.0",
            "course": {
                "course_id": "intro_ai",
                "course_name": "Introduction to Artificial Intelligence",
                "unit": unit_id,
                "version": "synthetic",
            },
            "knowledge_points": [
                {
                    "id": concept_id,
                    "title_zh": f"{module_id} 概念",
                    "title_en": f"{module_id} concept",
                    "module": module_id,
                    "description": f"A reviewed concept for {module_id}.",
                    "prerequisites": [],
                    "learning_objectives": ["Identify the reviewed concept."],
                    "common_misconceptions": [],
                    "mastery_criteria": ["Select the reviewed answer."],
                }
            ],
        },
    )
    _write_json(
        root / "data" / f"{prefix}_chunks.json",
        {
            "schema_version": "0.1.0",
            "course_id": "intro_ai",
            "unit_id": unit_id,
            "chunks": [
                {
                    "id": chunk_id,
                    "source_file": source_file,
                    "page_start": 1,
                    "page_end": 1,
                    "section_title": f"{module_id} section",
                    "topic_ids": [concept_id],
                    "support_tags": [],
                    "keywords": ["synthetic", module_id],
                    "content": f"Only {module_id} material is present in this package.",
                    "language": "en",
                    "source_role": "course_core",
                    "content_type": "definition",
                    "review_status": "human_verified",
                }
            ],
        },
    )
    _write_json(
        root / "data" / f"{prefix}_manifest.json",
        {
            "schema_version": 1,
            "materials": [
                {
                    "material_id": f"{prefix}_material",
                    "source_role": "course_core",
                    "source_file": source_file,
                    "sha256": "a" * 64,
                    "size_bytes": 1,
                    "page_count": 1,
                    "allowed_page_range": {"page_start": 1, "page_end": 1},
                    "provenance_note": "Synthetic offline fixture only.",
                }
            ],
        },
    )
    _write_json(
        root / "data" / f"{prefix}_templates.json",
        {
            "schema_version": 1,
            "templates": [
                {
                    "id": template_id,
                    "schema_version": 1,
                    "review_status": "human_verified",
                    "purpose": "mastery_verification",
                    "concept_ids": [concept_id],
                    "eligible_intents": ["definition", "diagnostic_request"],
                    "selection_priority": 10,
                    "question_type": "single_choice",
                    "prompt": f"Which choice identifies {module_id}?",
                    "choices": [
                        {"id": "correct", "text": "The reviewed answer"},
                        {"id": "incorrect", "text": "The distractor"},
                    ],
                    "expected_answer": {"choice_id": "correct"},
                    "deterministic_scorer": "single_choice_v1",
                    "misconception_rules": [],
                    "teaching_support": {
                        "hint": "Read the reviewed material.",
                        "explanation": "The expected answer is explicitly reviewed.",
                    },
                    "benchmark_case_ids": [f"{prefix}_correct"],
                }
            ],
        },
    )
    return {
        "knowledge_points_path": f"data/{prefix}_knowledge.json",
        "course_chunks_path": f"data/{prefix}_chunks.json",
        "diagnostic_templates_path": f"data/{prefix}_templates.json",
        "course_material_manifest_path": f"data/{prefix}_manifest.json",
        "chunk_id": chunk_id,
        "template_id": template_id,
    }


def _module_entry(
    *, module_id: str, unit_id: str, concept_id: str, paths: dict[str, str]
) -> dict[str, Any]:
    return {
        "module_id": module_id,
        "display_name_zh": module_id,
        "display_name_en": module_id.replace("_", " ").title(),
        "unit_ids": [unit_id],
        "knowledge_points_path": paths["knowledge_points_path"],
        "course_chunks_path": paths["course_chunks_path"],
        "diagnostic_templates_path": paths["diagnostic_templates_path"],
        "course_material_manifest_path": paths["course_material_manifest_path"],
        "default_diagnostic_concept_ids": [concept_id],
    }


@pytest.fixture
def two_module_root(tmp_path: Path) -> dict[str, Any]:
    search = _module_files(
        tmp_path,
        module_id="search_algorithms",
        unit_id="search_algorithms",
        concept_id="search__frontier",
    )
    ml = _module_files(
        tmp_path,
        module_id="machine_learning_foundations",
        unit_id="machine_learning_foundations",
        concept_id="ml__loss_function",
    )
    _write_json(
        tmp_path / "data" / "course_modules.json",
        {
            "schema_version": 1,
            "course_id": "intro_ai",
            "modules": [
                _module_entry(
                    module_id="search_algorithms",
                    unit_id="search_algorithms",
                    concept_id="search__frontier",
                    paths=search,
                ),
                _module_entry(
                    module_id="machine_learning_foundations",
                    unit_id="machine_learning_foundations",
                    concept_id="ml__loss_function",
                    paths=ml,
                ),
            ],
        },
    )
    return {"root": tmp_path, "search": search, "ml": ml}


def test_current_search_module_is_registered_and_loads_unchanged():
    registry = load_course_module_registry(PROJECT_ROOT)
    search = load_course_module_data(PROJECT_ROOT)

    assert registry["modules"][0]["module_id"] == "search_algorithms"
    assert search["module"]["unit_ids"] == ["search_algorithms"]
    assert len(search["knowledge_data"]["knowledge_points"]) == 26
    assert search["templates_data"]["templates"]


def test_registry_binds_each_module_to_its_own_materials_and_templates(two_module_root):
    root = two_module_root["root"]
    ml_bundle = load_module_app_package(root, module_id="machine_learning_foundations")
    search_bundle = load_module_app_package(root, module_id="search_algorithms")

    assert [chunk["id"] for chunk in ml_bundle["course_data"]["chunks"]] == [
        two_module_root["ml"]["chunk_id"]
    ]
    assert [item["id"] for item in ml_bundle["templates_data"]["templates"]] == [
        two_module_root["ml"]["template_id"]
    ]
    assert two_module_root["search"]["chunk_id"] not in {
        chunk["id"] for chunk in ml_bundle["course_data"]["chunks"]
    }
    assert [item["id"] for item in search_bundle["templates_data"]["templates"]] == [
        two_module_root["search"]["template_id"]
    ]


def test_selected_module_qa_and_diagnostic_lookup_cannot_cross_module(two_module_root):
    root, ml = two_module_root["root"], two_module_root["ml"]
    adapter = _ModuleAdapter("ml__loss_function", ml["chunk_id"])
    service = build_question_answer_service(
        root=root, module_id="machine_learning_foundations", adapter=adapter
    )

    result = service.ask("What is the synthetic concept?")
    assert [item["chunk"]["id"] for item in result["retrieval"]["results"]] == [
        ml["chunk_id"]
    ]
    assert "Search Algorithms" not in adapter.system_prompts[0]

    plan = build_diagnostic_handoff_service(
        root=root, module_id="machine_learning_foundations"
    ).plan(topic_ids=["ml__loss_function"], intent="definition")
    assert plan["template_ids"] == [ml["template_id"]]
    assert two_module_root["search"]["template_id"] not in plan["template_ids"]


def test_global_catalog_preserves_distinct_module_concept_and_template_identity(two_module_root):
    knowledge_data, template_ids = load_global_learning_catalog(two_module_root["root"])
    state = {
        "student_id": "synthetic",
        "course_id": "intro_ai",
        "mastery": {"search__frontier": 0.4, "ml__loss_function": 0.8},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }

    validate_learner_state(state, knowledge_data)
    assert {point["id"] for point in knowledge_data["knowledge_points"]} == {
        "search__frontier",
        "ml__loss_function",
    }
    assert template_ids == {
        two_module_root["search"]["template_id"],
        two_module_root["ml"]["template_id"],
    }


def test_formal_only_module_can_start_its_own_verification_session(two_module_root):
    workflow = build_dual_track_diagnostic_workflow(
        root=two_module_root["root"], module_id="machine_learning_foundations"
    )

    result = workflow.start_quick_verification(concept_ids=["ml__loss_function"])

    assert result["purpose"] == "mastery_verification"
    assert result["verification"]["question"]["template_id"] == two_module_root["ml"][
        "template_id"
    ]


def test_registry_rejects_cross_module_unit_collision(two_module_root):
    registry_path = two_module_root["root"] / "data" / "course_modules.json"
    document = json.loads(registry_path.read_text(encoding="utf-8"))
    document["modules"][1]["unit_ids"] = ["search_algorithms"]
    _write_json(registry_path, document)

    with pytest.raises(CourseModuleError, match="unit_ids"):
        load_course_module_registry(two_module_root["root"])


def test_module_rejects_chunk_page_outside_its_registered_manifest(two_module_root):
    root = two_module_root["root"]
    ml_chunks = root / two_module_root["ml"]["course_chunks_path"]
    document = json.loads(ml_chunks.read_text(encoding="utf-8"))
    document["chunks"][0]["page_end"] = 2
    _write_json(ml_chunks, document)

    with pytest.raises(CourseModuleError, match="manifest coverage"):
        load_course_module_data(root, "machine_learning_foundations")


def test_registry_rejects_cross_module_concept_and_template_collisions(two_module_root):
    root = two_module_root["root"]
    ml_knowledge = root / two_module_root["ml"]["knowledge_points_path"]
    document = json.loads(ml_knowledge.read_text(encoding="utf-8"))
    document["knowledge_points"][0]["id"] = "search__frontier"
    _write_json(ml_knowledge, document)
    ml_chunks = root / two_module_root["ml"]["course_chunks_path"]
    chunks_document = json.loads(ml_chunks.read_text(encoding="utf-8"))
    chunks_document["chunks"][0]["topic_ids"] = ["search__frontier"]
    _write_json(ml_chunks, chunks_document)
    ml_templates = root / two_module_root["ml"]["diagnostic_templates_path"]
    templates_document = json.loads(ml_templates.read_text(encoding="utf-8"))
    templates_document["templates"][0]["concept_ids"] = ["search__frontier"]
    _write_json(ml_templates, templates_document)
    registry_path = root / "data" / "course_modules.json"
    registry_document = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_document["modules"][1]["default_diagnostic_concept_ids"] = [
        "search__frontier"
    ]
    _write_json(registry_path, registry_document)

    with pytest.raises(CourseModuleError, match="concept IDs"):
        load_all_course_module_data(root)


def test_registry_rejects_cross_module_template_collision(two_module_root):
    root = two_module_root["root"]
    ml_templates = root / two_module_root["ml"]["diagnostic_templates_path"]
    document = json.loads(ml_templates.read_text(encoding="utf-8"))
    document["templates"][0]["id"] = two_module_root["search"]["template_id"]
    _write_json(ml_templates, document)

    with pytest.raises(CourseModuleError, match="template IDs"):
        load_all_course_module_data(root)


def test_selector_options_are_stable_and_unknown_module_fails_closed(two_module_root):
    root = two_module_root["root"]
    options = load_registered_module_options(root)

    assert [item["module_id"] for item in options] == [
        "search_algorithms",
        "machine_learning_foundations",
    ]
    with pytest.raises(AppServiceError, match="Unknown course module ID"):
        load_module_app_package(root, module_id="unknown_module")


def test_module_switch_resolves_new_package_without_mutating_learner_state(
    two_module_root, monkeypatch
):
    root = two_module_root["root"]
    learner_state = {
        "student_id": "synthetic",
        "course_id": "intro_ai",
        "mastery": {"search__frontier": 0.4},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }
    st = _StateOnlyStreamlit(
        {
            "introai_learner_state": learner_state,
            "introai_qa_service": object(),
            "introai_dual_track_result": {"phase": "verification"},
            "introai_last_qa_result": {"question": "old"},
        }
    )
    monkeypatch.setattr(streamlit_app, "ROOT", root)

    streamlit_app._switch_selected_module(
        st,
        "machine_learning_foundations",
        valid_module_ids={"search_algorithms", "machine_learning_foundations"},
    )

    assert st.session_state["introai_learner_state"] is learner_state
    assert st.session_state["introai_selected_module_id"] == "machine_learning_foundations"
    assert "introai_qa_service" not in st.session_state
    assert "introai_dual_track_result" not in st.session_state
    assert "introai_last_qa_result" not in st.session_state
    assert streamlit_app._get_app_data(st)["module"]["module_id"] == "machine_learning_foundations"
