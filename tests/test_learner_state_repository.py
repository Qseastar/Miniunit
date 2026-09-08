import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from introai_tutor.learner_state_repository import (
    default_state_db_path,
    LearnerStatePersistenceError,
    SCHEMA_VERSION,
    SQLiteLearnerStateRepository,
)


LEARNER = "4ed2149c-6dd3-4a23-9c4d-94ea4edb63fd"


def _state(mastery=None):
    return {
        "student_id": LEARNER,
        "course_id": "intro_ai",
        "mastery": mastery or {"breadth_first_search": 0.35},
        "misconceptions": ["bfs_is_depth_first"],
        "learning_evidence": [],
        "preferred_style": "visual_example",
    }


def _summary(template_id="verify_bfs_frontier_choice_v1"):
    return {
        "status": "completed",
        "purpose": "mastery_verification",
        "evidence_eligible": True,
        "track_id": "reviewed_template_verification",
        "passed_steps": 1,
        "total_steps": 1,
        "step_results": [{
            "question_id": template_id,
            "status": "passed",
            "attempts": 1,
            "final_attempt_assistance_level": "none",
        }],
    }


def test_initialization_round_trip_and_reopen(tmp_path):
    path = tmp_path / "state.sqlite3"
    repository = SQLiteLearnerStateRepository(path)
    repository.save_profile(learner_id=LEARNER, learner_state=_state(), completed_summary=_summary(), event_id="event-1")

    assert repository.profile_exists(LEARNER)
    loaded = SQLiteLearnerStateRepository(path).load_profile(LEARNER)
    assert loaded is not None
    assert loaded.learner_state["mastery"] == {"breadth_first_search": 0.35}
    assert loaded.learner_state["misconceptions"] == ["bfs_is_depth_first"]
    assert loaded.learner_state["learning_evidence"][0]["event_id"] == "event-1"
    assert loaded.completed_summaries[0]["steps"][0]["template_id"] == "verify_bfs_frontier_choice_v1"


def test_duplicate_event_is_noop_and_conflict_fails_closed(tmp_path):
    repository = SQLiteLearnerStateRepository(tmp_path / "state.sqlite3")
    assert repository.save_profile(learner_id=LEARNER, learner_state=_state(), completed_summary=_summary(), event_id="event-1") is False
    assert repository.save_profile(learner_id=LEARNER, learner_state=_state({"breadth_first_search": 0.9}), completed_summary=_summary(), event_id="event-1") is True
    assert repository.load_profile(LEARNER).learner_state["mastery"]["breadth_first_search"] == 0.35
    with pytest.raises(LearnerStatePersistenceError, match="conflicts"):
        repository.save_profile(learner_id=LEARNER, learner_state=_state(), completed_summary=_summary("verify_ucs_min_g_choice_v1"), event_id="event-1")


def test_clear_and_profiles_are_isolated(tmp_path):
    repository = SQLiteLearnerStateRepository(tmp_path / "state.sqlite3")
    second = "41e6741d-bd10-4f29-b27a-98017831164c"
    repository.save_profile(learner_id=LEARNER, learner_state=_state())
    assert repository.claim_reviewed_template_exposure(
        learner_id=LEARNER,
        template_id="verify_bfs_frontier_choice_v1",
        reason="formal_answer_submitted",
    ) is False
    repository.save_profile(learner_id=second, learner_state={**_state({"uniform_cost_search": 0.5}), "student_id": second})
    repository.clear_profile(LEARNER)
    assert repository.load_profile(LEARNER).learner_state["mastery"] == {}
    assert repository.reviewed_template_exposures(LEARNER) == {}
    assert repository.load_profile(second).learner_state["mastery"] == {"uniform_cost_search": 0.5}


def test_unknown_version_migration_and_corrupted_row_recovery(tmp_path):
    path = tmp_path / "state.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE learner_profiles (learner_id TEXT PRIMARY KEY, course_id TEXT NOT NULL, preferred_style TEXT NOT NULL, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, state_version INTEGER NOT NULL);
        CREATE TABLE concept_state (learner_id TEXT NOT NULL, concept_id TEXT NOT NULL, mastery REAL NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (learner_id, concept_id));
        PRAGMA user_version = 1;
    """)
    connection.execute("INSERT INTO learner_profiles VALUES (?, 'intro_ai', 'visual_example', 'now', 'now', 1)", (LEARNER,))
    connection.execute("INSERT INTO concept_state VALUES (?, 'breadth_first_search', 3.0, 'now')", (LEARNER,))
    connection.commit()
    connection.close()
    repository = SQLiteLearnerStateRepository(path)
    repository.initialize_schema()
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    loaded = repository.load_profile(LEARNER)
    assert loaded.learner_state["mastery"] == {}
    assert loaded.warnings
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()
    with pytest.raises(LearnerStatePersistenceError, match="newer unsupported"):
        repository.initialize_schema()


def test_v2_migration_backfills_one_exposure_per_template_with_earliest_event(tmp_path):
    path = tmp_path / "state.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE learner_profiles (learner_id TEXT PRIMARY KEY, course_id TEXT NOT NULL, preferred_style TEXT NOT NULL, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, state_version INTEGER NOT NULL);
        CREATE TABLE concept_state (learner_id TEXT NOT NULL, concept_id TEXT NOT NULL, mastery REAL NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (learner_id, concept_id));
        CREATE TABLE misconception_state (learner_id TEXT NOT NULL, misconception_id TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (learner_id, misconception_id));
        CREATE TABLE evidence_events (event_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL, occurred_at TEXT NOT NULL, schema_version INTEGER NOT NULL);
        PRAGMA user_version = 2;
    """)
    connection.execute(
        "INSERT INTO learner_profiles VALUES (?, 'intro_ai', 'visual_example', 'now', 'now', 1)",
        (LEARNER,),
    )
    payload = {
        "schema_version": 1, "track_id": "reviewed_template_verification",
        "evidence_eligible": True, "passed_steps": 1, "total_steps": 1,
        "steps": [{
            "template_id": "verify_bfs_frontier_choice_v1", "status": "passed",
            "attempts": 1, "final_attempt_assistance_level": "none",
        }],
    }
    for event_id, occurred_at in (("older", "2025-01-01T00:00:00+00:00"), ("newer", "2025-02-01T00:00:00+00:00")):
        connection.execute(
            "INSERT INTO evidence_events VALUES (?, ?, ?, 'hash', ?, 1)",
            (event_id, LEARNER, json.dumps(payload), occurred_at),
        )
    connection.commit()
    connection.close()

    repository = SQLiteLearnerStateRepository(path)
    repository.initialize_schema()
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    exposures = repository.reviewed_template_exposures(LEARNER)
    assert exposures == {
        "verify_bfs_frontier_choice_v1": {
            "first_exposed_at": "2025-01-01T00:00:00+00:00",
            "exposure_reason": "migrated_existing_evidence",
        }
    }


def test_schema_has_no_sensitive_columns_and_uses_parameterized_values(tmp_path):
    repository = SQLiteLearnerStateRepository(tmp_path / "state.sqlite3")
    repository.save_profile(learner_id=LEARNER, learner_state=_state({"x'); DROP TABLE learner_profiles; --": 0.2}))
    with sqlite3.connect(repository.path) as connection:
        columns = {
            row[1]
            for table in ("learner_profiles", "concept_state", "misconception_state", "evidence_events")
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        assert not columns & {"question_text", "answer_text", "prompt", "api_key", "authorization", "course_chunk_text"}
        assert connection.execute("SELECT COUNT(*) FROM learner_profiles").fetchone()[0] == 1


def test_two_repository_instances_preserve_distinct_events_and_duplicate_is_idempotent(tmp_path):
    path = tmp_path / "state.sqlite3"
    first = SQLiteLearnerStateRepository(path)
    second = SQLiteLearnerStateRepository(path)

    def save(repository, state, event_id, template_id):
        return repository.save_profile(
            learner_id=LEARNER, learner_state=state,
            completed_summary=_summary(template_id), event_id=event_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda item: save(*item),
            [
                (first, _state({"breadth_first_search": 0.35}), "event-1", "verify_bfs_frontier_choice_v1"),
                (second, _state({"uniform_cost_search": 0.5}), "event-2", "verify_ucs_min_g_choice_v1"),
            ],
        ))
    assert results == [False, False]
    loaded = first.load_profile(LEARNER)
    assert loaded.learner_state["mastery"] == {
        "breadth_first_search": 0.35, "uniform_cost_search": 0.5
    }
    assert len(loaded.completed_summaries) == 2
    assert save(second, _state({"uniform_cost_search": 0.9}), "event-2", "verify_ucs_min_g_choice_v1") is True


def test_database_path_override_health_check_and_unwritable_parent_fail_safely(tmp_path, monkeypatch):
    override = tmp_path / "override.sqlite3"
    monkeypatch.setenv("INTROAI_STATE_DB", f"  {override}  ")
    assert default_state_db_path() == override
    assert SQLiteLearnerStateRepository().health_check() is True
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("block", encoding="utf-8")
    with pytest.raises(LearnerStatePersistenceError, match="unavailable"):
        SQLiteLearnerStateRepository(blocker / "state.sqlite3").initialize_schema()
