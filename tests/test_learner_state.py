import copy
from pathlib import Path

import pytest

from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.learner import (
    LearnerStateValidationError,
    get_mastery,
    load_learner_state,
    validate_learner_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PROJECT_ROOT / "data" / "knowledge_points.json"
LEARNER_STATE_FILE = PROJECT_ROOT / "data" / "demo_student_state.json"


def load_demo_data():
    knowledge_data = load_knowledge_points(KNOWLEDGE_FILE)
    learner_state = load_learner_state(LEARNER_STATE_FILE, knowledge_data)
    return knowledge_data, learner_state


def test_load_demo_learner_state():
    _, learner_state = load_demo_data()

    assert learner_state["student_id"] == "demo_student"
    assert "breadth_first_search" in learner_state["mastery"]


def test_missing_required_field_fails():
    knowledge_data, learner_state = load_demo_data()
    broken = copy.deepcopy(learner_state)

    del broken["student_id"]

    with pytest.raises(LearnerStateValidationError):
        validate_learner_state(broken, knowledge_data)


def test_mastery_score_out_of_range_fails():
    knowledge_data, learner_state = load_demo_data()
    broken = copy.deepcopy(learner_state)

    broken["mastery"]["breadth_first_search"] = 1.5

    with pytest.raises(LearnerStateValidationError):
        validate_learner_state(broken, knowledge_data)


def test_unknown_mastery_concept_fails():
    knowledge_data, learner_state = load_demo_data()
    broken = copy.deepcopy(learner_state)

    broken["mastery"]["unknown_concept"] = 0.5

    with pytest.raises(LearnerStateValidationError):
        validate_learner_state(broken, knowledge_data)


def test_unknown_misconception_concept_fails():
    knowledge_data, learner_state = load_demo_data()
    broken = copy.deepcopy(learner_state)

    broken["misconceptions"].append(
        {
            "concept_id": "unknown_concept",
            "description": "This concept does not exist."
        }
    )

    with pytest.raises(LearnerStateValidationError):
        validate_learner_state(broken, knowledge_data)


def test_get_mastery_existing_concept():
    _, learner_state = load_demo_data()

    assert get_mastery(learner_state, "breadth_first_search") == 0.45


def test_get_mastery_missing_concept_defaults_to_zero():
    _, learner_state = load_demo_data()

    assert get_mastery(learner_state, "admissibility_and_consistency") == 0.0
