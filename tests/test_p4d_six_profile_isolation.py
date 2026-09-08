"""Offline P4d canary for six concurrent remote-Pilot learner profiles."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from introai_tutor.app_services import (
    build_dual_track_diagnostic_workflow,
    build_learner_state_persistence_service,
    build_reviewed_template_exposure_policy,
    load_initial_learner_state,
)
from introai_tutor.learner_state_repository import SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
LEARNERS = tuple(
    f"00000000-0000-4000-8000-{index:012d}" for index in range(1, 7)
)
PROFILE_CASES = (
    (LEARNERS[0], "verify_ucs_min_g_choice_v1", "uniform_cost_search", "definition", "A"),
    (LEARNERS[1], "verify_successor_operator_v1", "state_space_and_operators", "definition", "move_right"),
    (LEARNERS[2], "verify_dfs_frontier_choice_v1", "depth_first_search", "definition", "node_c"),
    (LEARNERS[3], "verify_iddfs_depth_limit_schedule_v1", "iterative_deepening_search", "definition", "restart_limit_2"),
    (LEARNERS[4], "verify_greedy_min_h_choice_v1", "greedy_best_first_search", "definition", "node_b"),
    (LEARNERS[5], "verify_astar_f_value_v1", "a_star_search", "definition", "g_plus_h"),
)
SHARED_TEMPLATE = "verify_bfs_equal_cost_condition_v1"
SHARED_CONCEPT_IDS = ["breadth_first_search", "completeness_optimality_complexity"]


def _services(database: Path):
    """Build independent service instances over one actual SQLite file."""
    persistence = build_learner_state_persistence_service(root=ROOT, db_path=database)
    policy = build_reviewed_template_exposure_policy(
        root=ROOT, persistence_service=persistence
    )
    workflow = build_dual_track_diagnostic_workflow(
        root=ROOT, exposure_policy=policy
    )
    return persistence, workflow


def _complete_first_template(
    database: Path,
    learner_id: str,
    template_id: str,
    concept_ids: list[str],
    intent: str,
    answer: str,
    event_id: str,
) -> dict:
    persistence, workflow = _services(database)
    initial = persistence.restore(
        learner_id=learner_id, empty_state=load_initial_learner_state(ROOT)
    )["learner_state"]
    started = workflow.start_quick_verification(
        concept_ids=concept_ids,
        intent=intent,
        template_ids=[template_id],
        learner_id=learner_id,
    )
    completed = workflow.submit_verification(
        session=started["session"],
        answer=answer,
        submitted_template_id=template_id,
        learner_state=initial,
        learner_id=learner_id,
    )
    assert completed["attempt_mode"] == "formal"
    assert completed["formal_evidence_summary"] is not None
    persistence.save_completed(
        learner_id=learner_id,
        learner_state=completed["state_update"]["learner_state"],
        diagnostic_summary=completed["formal_evidence_summary"],
        event_id=event_id,
    )
    return {
        "learner_id": learner_id,
        "event_id": event_id,
        "formal_summary": completed["formal_evidence_summary"],
    }


def test_six_profiles_share_one_sqlite_without_state_exposure_or_event_crosstalk(tmp_path):
    database = tmp_path / "p4d-six-profiles.sqlite3"
    with ThreadPoolExecutor(max_workers=6) as executor:
        completed = list(
            executor.map(
                lambda case: _complete_first_template(
                    database, case[0], case[1], [case[2]], case[3], case[4],
                    f"p4d-primary-{case[0]}",
                ),
                PROFILE_CASES,
            )
        )

    assert {item["learner_id"] for item in completed} == set(LEARNERS)
    assert {item["event_id"] for item in completed} == {
        f"p4d-primary-{learner}" for learner in LEARNERS
    }

    for learner_id, template_id, concept_id, *_ in PROFILE_CASES:
        persistence, _ = _services(database)
        restored = persistence.restore(
            learner_id=learner_id, empty_state=load_initial_learner_state(ROOT)
        )
        assert restored["learner_state"]["student_id"] == learner_id
        assert restored["learner_state"]["mastery"][concept_id] == pytest.approx(0.35)
        assert len(restored["learner_state"]["learning_evidence"]) == 1
        assert set(persistence.reviewed_template_exposures(learner_id=learner_id)) == {template_id}

    # A common reviewed item remains a first formal measurement for each
    # distinct learner after their different first concept-specific template.
    shared = [
        _complete_first_template(
            database, learner_id, SHARED_TEMPLATE, SHARED_CONCEPT_IDS,
            "comparison", "equal_cost", f"p4d-shared-{learner_id}",
        )
        for learner_id in LEARNERS
    ]

    for learner_id, template_id, concept_id, *_ in PROFILE_CASES:
        persistence, workflow = _services(database)
        restored = persistence.restore(
            learner_id=learner_id, empty_state=load_initial_learner_state(ROOT)
        )
        assert restored["learner_state"]["mastery"][concept_id] == pytest.approx(0.35)
        assert restored["learner_state"]["mastery"]["breadth_first_search"] == pytest.approx(0.35)
        assert len(restored["learner_state"]["learning_evidence"]) == 2
        assert set(persistence.reviewed_template_exposures(learner_id=learner_id)) == {
            template_id, SHARED_TEMPLATE,
        }

        repeat = workflow.start_quick_verification(
            concept_ids=SHARED_CONCEPT_IDS,
            intent="comparison",
            template_ids=[SHARED_TEMPLATE],
            learner_id=learner_id,
        )
        assert repeat["attempt_mode"] == "practice_only"
        assert repeat["mastery_eligible"] is False

    persistence, _ = _services(database)
    first = shared[0]
    restored = persistence.restore(
        learner_id=first["learner_id"], empty_state=load_initial_learner_state(ROOT)
    )
    assert persistence.save_completed(
        learner_id=first["learner_id"],
        learner_state=restored["learner_state"],
        diagnostic_summary=first["formal_summary"],
        event_id=first["event_id"],
    ) is True
    assert SCHEMA_VERSION == 3
