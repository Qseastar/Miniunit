from concurrent.futures import ThreadPoolExecutor

from introai_tutor.learner_state_repository import SQLiteLearnerStateRepository, SCHEMA_VERSION


LEARNER_A = "11111111-1111-4111-8111-111111111111"
LEARNER_B = "22222222-2222-4222-8222-222222222222"


def _state(learner_id, concept_id, score):
    return {
        "student_id": learner_id,
        "course_id": "intro_ai",
        "mastery": {concept_id: score},
        "misconceptions": [],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }


def test_two_profiles_using_two_repository_instances_do_not_cross_talk(tmp_path):
    path = tmp_path / "shared.sqlite3"
    first = SQLiteLearnerStateRepository(path)
    second = SQLiteLearnerStateRepository(path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda item: item[0].save_profile(
                    learner_id=item[1], learner_state=item[2]
                ),
                [
                    (first, LEARNER_A, _state(LEARNER_A, "breadth_first_search", 0.35)),
                    (second, LEARNER_B, _state(LEARNER_B, "uniform_cost_search", 0.70)),
                ],
            )
        )
    assert results == [False, False]
    assert first.load_profile(LEARNER_A).learner_state["mastery"] == {
        "breadth_first_search": 0.35
    }
    assert second.load_profile(LEARNER_B).learner_state["mastery"] == {
        "uniform_cost_search": 0.70
    }
    assert first.load_profile(LEARNER_A).learner_state["student_id"] == LEARNER_A
    assert second.load_profile(LEARNER_B).learner_state["student_id"] == LEARNER_B


def test_shared_profile_repository_keeps_existing_schema_and_event_boundary(tmp_path):
    path = tmp_path / "shared.sqlite3"
    repository = SQLiteLearnerStateRepository(path)
    assert repository.health_check() is True
    assert SCHEMA_VERSION == 3
    # Event idempotency remains scoped to the existing repository contract;
    # this P4c test deliberately does not add a new persistence key.
    assert repository.profile_exists(LEARNER_A) is False
