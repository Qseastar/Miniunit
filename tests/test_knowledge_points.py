import copy
from pathlib import Path

import pytest

from introai_tutor.knowledge import (
    KnowledgeValidationError,
    get_knowledge_point,
    get_prerequisite_ids,
    load_knowledge_points,
    validate_knowledge_points,
)



PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"


def test_load_current_knowledge_points_file():
    data = load_knowledge_points(KNOWLEDGE_FILE)

    assert "knowledge_points" in data
    assert len(data["knowledge_points"]) >= 8


def test_missing_required_field_fails():
    data = load_knowledge_points(KNOWLEDGE_FILE)
    broken = copy.deepcopy(data)

    del broken["knowledge_points"][0]["title_en"]

    with pytest.raises(KnowledgeValidationError):
        validate_knowledge_points(broken)


def test_duplicate_id_fails():
    data = load_knowledge_points(KNOWLEDGE_FILE)
    broken = copy.deepcopy(data)

    broken["knowledge_points"][1]["id"] = broken["knowledge_points"][0]["id"]

    with pytest.raises(KnowledgeValidationError):
        validate_knowledge_points(broken)


def test_unknown_prerequisite_fails():
    data = load_knowledge_points(KNOWLEDGE_FILE)
    broken = copy.deepcopy(data)

    broken["knowledge_points"][0]["prerequisites"] = ["unknown_concept"]

    with pytest.raises(KnowledgeValidationError):
        validate_knowledge_points(broken)


def test_prerequisites_must_be_list():
    data = load_knowledge_points(KNOWLEDGE_FILE)
    broken = copy.deepcopy(data)

    broken["knowledge_points"][0]["prerequisites"] = "not_a_list"

    with pytest.raises(KnowledgeValidationError):
        validate_knowledge_points(broken)

def test_get_knowledge_point_by_id():
    data = load_knowledge_points(KNOWLEDGE_FILE)

    point = get_knowledge_point(data, "breadth_first_search")

    assert point["id"] == "breadth_first_search"
    assert point["title_en"] == "Breadth-First Search"


def test_get_unknown_knowledge_point_fails():
    data = load_knowledge_points(KNOWLEDGE_FILE)

    with pytest.raises(KnowledgeValidationError):
        get_knowledge_point(data, "unknown_concept")


def test_get_prerequisite_ids():
    data = load_knowledge_points(KNOWLEDGE_FILE)

    prerequisites = get_prerequisite_ids(data, "a_star_search")

    assert "uniform_cost_search" in prerequisites
    assert "informed_search_and_heuristics" in prerequisites

