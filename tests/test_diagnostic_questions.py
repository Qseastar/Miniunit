import copy
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.questions import (
    DiagnosticQuestionValidationError,
    load_diagnostic_questions,
    validate_diagnostic_questions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
QUESTIONS_FILE = PROJECT_ROOT / "data" / "diagnostic_questions.json"


def load_demo_questions():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    question_data = load_diagnostic_questions(QUESTIONS_FILE, knowledge_data)
    return knowledge_data, question_data


def test_load_current_diagnostic_questions_file():
    _, question_data = load_demo_questions()

    assert "diagnostic_questions" in question_data
    assert len(question_data["diagnostic_questions"]) >= 15


def test_current_file_keeps_legacy_questions_and_adds_structured_track_questions():
    _, question_data = load_demo_questions()
    ids = [question["id"] for question in question_data["diagnostic_questions"]]
    assert len(ids) >= 27
    assert "dq_bfs_order_001" in ids
    assert "dq_bfs_expansion_001" in ids
    assert "dq_ucs_when_costs_differ_001" in ids


def test_canonical_structured_track_questions_include_human_teaching_support():
    _, question_data = load_demo_questions()
    supports = {
        question["id"]: question.get("teaching_support")
        for question in question_data["diagnostic_questions"]
        if question["id"]
        in {
            "dq_bfs_expansion_001",
            "dq_bfs_order_001",
            "dq_ucs_when_costs_differ_001",
        }
    }

    assert set(supports) == {
        "dq_bfs_expansion_001",
        "dq_bfs_order_001",
        "dq_ucs_when_costs_differ_001",
    }
    for support in supports.values():
        assert set(support) == {"model_answer", "explanation", "scaffold"}
        assert all(isinstance(value, str) and value.strip() for value in support.values())


def test_missing_required_field_fails():
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)

    del broken["diagnostic_questions"][0]["expected_answer"]

    with pytest.raises(DiagnosticQuestionValidationError):
        validate_diagnostic_questions(broken, knowledge_data)


def test_duplicate_question_id_fails():
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)

    broken["diagnostic_questions"][1]["id"] = broken["diagnostic_questions"][0]["id"]

    with pytest.raises(DiagnosticQuestionValidationError):
        validate_diagnostic_questions(broken, knowledge_data)


def test_unknown_concept_id_fails():
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)

    broken["diagnostic_questions"][0]["concept_ids"] = ["unknown_concept"]

    with pytest.raises(DiagnosticQuestionValidationError):
        validate_diagnostic_questions(broken, knowledge_data)


def test_invalid_difficulty_fails():
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)

    broken["diagnostic_questions"][0]["difficulty"] = "beginner"

    with pytest.raises(DiagnosticQuestionValidationError):
        validate_diagnostic_questions(broken, knowledge_data)


def test_invalid_optional_structured_assessment_fails():
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)
    target = next(
        question
        for question in broken["diagnostic_questions"]
        if question["id"] == "dq_bfs_expansion_001"
    )
    target["assessment"]["pass_threshold"] = 2

    with pytest.raises(DiagnosticQuestionValidationError, match="invalid assessment"):
        validate_diagnostic_questions(broken, knowledge_data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda support: support.pop("scaffold"),
        lambda support: support.update({"unexpected": "not allowed"}),
        lambda support: support.update({"model_answer": "  "}),
    ],
)
def test_invalid_optional_teaching_support_fails(mutate):
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)
    target = next(
        question
        for question in broken["diagnostic_questions"]
        if question["id"] == "dq_bfs_expansion_001"
    )
    mutate(target["teaching_support"])

    with pytest.raises(DiagnosticQuestionValidationError, match="teaching_support"):
        validate_diagnostic_questions(broken, knowledge_data)


def test_concept_ids_must_be_non_empty_list():
    knowledge_data, question_data = load_demo_questions()
    broken = copy.deepcopy(question_data)

    broken["diagnostic_questions"][0]["concept_ids"] = []

    with pytest.raises(DiagnosticQuestionValidationError):
        validate_diagnostic_questions(broken, knowledge_data)
