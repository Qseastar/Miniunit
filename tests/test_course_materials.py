import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from introai_tutor.course_materials import (
    ALLOWED_SOURCE_FILES,
    COURSE_CORE_SOURCE_FILES,
    CourseMaterialValidationError,
    get_chunks_by_topic,
    get_course_chunk,
    load_course_chunks,
    validate_course_chunks,
)
from introai_tutor.knowledge import load_knowledge_points


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
CHUNKS_FILE = PROJECT_ROOT / "data" / "course_chunks.json"


def _load_current_data():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    chunk_data = load_course_chunks(CHUNKS_FILE, knowledge_data)
    return knowledge_data, chunk_data


def _broken_chunk_data():
    knowledge_data, chunk_data = _load_current_data()
    return knowledge_data, copy.deepcopy(chunk_data)


def test_load_current_course_chunks_file():
    knowledge_data, chunk_data = _load_current_data()

    assert chunk_data["course_id"] == "intro_ai"
    assert len(chunk_data["chunks"]) >= 40
    validate_course_chunks(chunk_data, knowledge_data)


def test_duplicate_chunk_id_fails():
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][1]["id"] = data["chunks"][0]["id"]

    with pytest.raises(CourseMaterialValidationError, match="Duplicate"):
        validate_course_chunks(data, knowledge_data)


def test_missing_required_chunk_field_fails():
    knowledge_data, data = _broken_chunk_data()
    del data["chunks"][0]["content"]

    with pytest.raises(CourseMaterialValidationError, match="missing required fields"):
        validate_course_chunks(data, knowledge_data)


def test_invalid_page_start_fails():
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0]["page_start"] = 0

    with pytest.raises(CourseMaterialValidationError, match="page_start"):
        validate_course_chunks(data, knowledge_data)


def test_page_end_before_start_fails():
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0]["page_end"] = data["chunks"][0]["page_start"] - 1

    with pytest.raises(CourseMaterialValidationError, match="page_end"):
        validate_course_chunks(data, knowledge_data)


def test_unknown_or_empty_topic_ids_fail():
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0]["topic_ids"] = ["unknown_topic"]

    with pytest.raises(CourseMaterialValidationError, match="unknown topic"):
        validate_course_chunks(data, knowledge_data)

    data["chunks"][0]["topic_ids"] = []
    with pytest.raises(CourseMaterialValidationError, match="topic_ids"):
        validate_course_chunks(data, knowledge_data)


def test_empty_keywords_and_non_list_support_tags_fail():
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0]["keywords"] = []

    with pytest.raises(CourseMaterialValidationError, match="keywords"):
        validate_course_chunks(data, knowledge_data)

    data["chunks"][0]["keywords"] = ["valid"]
    data["chunks"][0]["support_tags"] = "queue"
    with pytest.raises(CourseMaterialValidationError, match="support_tags"):
        validate_course_chunks(data, knowledge_data)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("language", "fr"),
        ("source_role", "external"),
        ("content_type", "lecture"),
        ("review_status", "approved"),
    ],
)
def test_invalid_enum_values_fail(field_name, value):
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0][field_name] = value

    with pytest.raises(CourseMaterialValidationError, match=f"invalid {field_name}"):
        validate_course_chunks(data, knowledge_data)


def test_unsupported_source_file_and_empty_text_fields_fail():
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0]["source_file"] = "unknown.pdf"

    with pytest.raises(CourseMaterialValidationError, match="unsupported source_file"):
        validate_course_chunks(data, knowledge_data)

    data["chunks"][0]["source_file"] = "ai_lec2_uninformed_search.pdf"
    data["chunks"][0]["section_title"] = ""
    with pytest.raises(CourseMaterialValidationError, match="section_title"):
        validate_course_chunks(data, knowledge_data)

    data["chunks"][0]["section_title"] = "Valid"
    data["chunks"][0]["content"] = "  "
    with pytest.raises(CourseMaterialValidationError, match="content"):
        validate_course_chunks(data, knowledge_data)


def test_get_course_chunk_and_get_chunks_by_topic():
    _, data = _load_current_data()

    chunk = get_course_chunk(data, "lec2_bfs_layer_order")
    assert chunk["source_file"] == "ai_lec2_uninformed_search.pdf"
    assert chunk in get_chunks_by_topic(data, "breadth_first_search")

    with pytest.raises(CourseMaterialValidationError, match="Unknown course chunk"):
        get_course_chunk(data, "unknown_chunk")


def test_real_chunks_use_valid_topics_and_positive_page_ranges():
    knowledge_data, data = _load_current_data()
    valid_topic_ids = {point["id"] for point in knowledge_data["knowledge_points"]}

    for chunk in data["chunks"]:
        assert set(chunk["topic_ids"]) <= valid_topic_ids
        assert chunk["page_start"] > 0
        assert chunk["page_end"] >= chunk["page_start"]


def test_reprocessed_sources_have_factual_chunks_and_no_extraction_placeholders():
    _, data = _load_current_data()
    replaced_sources = {
        "ai_lec4_local_search_and_llm_search.pdf",
        "ai_lec5_adversarial_search.pdf",
        "ai_lec6_mcts_and_search_summary.pdf",
        "ds_stack_queue_priority_queue.pdf",
        "ds_tree_traversal_heap.pdf",
        "ds_graph_traversal_shortest_path.pdf",
    }

    replaced_chunks = [
        chunk for chunk in data["chunks"] if chunk["source_file"] in replaced_sources
    ]

    assert len(replaced_chunks) >= 20
    assert all("未能由 pdftotext 恢复文本" not in chunk["content"] for chunk in replaced_chunks)
    assert not any("image_only" in chunk["id"] for chunk in data["chunks"])


def test_every_formal_source_file_has_at_least_one_chunk():
    _, data = _load_current_data()

    assert {chunk["source_file"] for chunk in data["chunks"]} == ALLOWED_SOURCE_FILES


def test_optional_local_source_verification_requires_a_root():
    knowledge_data, data = _load_current_data()

    with pytest.raises(CourseMaterialValidationError, match="local_materials_root"):
        validate_course_chunks(data, knowledge_data, verify_local_sources=True)


def _make_fake_local_sources(tmp_path, monkeypatch, *, page_count=100, omit=None):
    for source_file in ALLOWED_SOURCE_FILES - {omit}:
        source_directory = (
            "course_core"
            if source_file in COURSE_CORE_SOURCE_FILES
            else "prerequisite_support"
        )
        source_path = tmp_path / source_directory / source_file
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"not a real PDF")

    monkeypatch.setattr(
        "introai_tutor.course_materials.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=f"Pages:           {page_count}\n"),
    )


def test_optional_local_source_verification_accepts_existing_sources(tmp_path, monkeypatch):
    knowledge_data, data = _load_current_data()
    _make_fake_local_sources(tmp_path, monkeypatch)

    validate_course_chunks(
        data,
        knowledge_data,
        verify_local_sources=True,
        local_materials_root=tmp_path,
    )


def test_optional_local_source_verification_rejects_missing_source(tmp_path, monkeypatch):
    knowledge_data, data = _load_current_data()
    _make_fake_local_sources(
        tmp_path,
        monkeypatch,
        omit="ai_lec2_uninformed_search.pdf",
    )

    with pytest.raises(CourseMaterialValidationError, match="Expected local source file"):
        validate_course_chunks(
            data,
            knowledge_data,
            verify_local_sources=True,
            local_materials_root=tmp_path,
        )


def test_optional_local_source_verification_rejects_page_out_of_bounds(tmp_path, monkeypatch):
    knowledge_data, data = _broken_chunk_data()
    data["chunks"][0]["page_end"] = 101
    _make_fake_local_sources(tmp_path, monkeypatch, page_count=100)

    with pytest.raises(CourseMaterialValidationError, match="exceeds local source page count"):
        validate_course_chunks(
            data,
            knowledge_data,
            verify_local_sources=True,
            local_materials_root=tmp_path,
        )
