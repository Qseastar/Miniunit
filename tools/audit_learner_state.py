"""Offline P6 learner-state measurement audit.

This helper deliberately drives the production composition (reviewed template
selection, exposure policy, verification scorer, P5B integration, persistence,
and recommendation).  It does not contain a second mastery implementation and
never reads environment configuration or calls a network service.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable

from introai_tutor.app_services import (
    build_dual_track_diagnostic_workflow,
    build_learner_state_persistence_service,
    build_reviewed_template_exposure_policy,
    load_initial_learner_state,
)
from introai_tutor.knowledge import load_knowledge_points
from introai_tutor.recommend import recommend_next_concept


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("/tmp/introai_p6_learner_state_audit.json")


@dataclass(frozen=True)
class TrajectorySnapshot:
    trajectory_id: str
    step_index: int
    template_id: str
    primary_concept: str
    response_correctness: str
    assistance_provenance: str
    formal_or_practice_only: str
    selected_signal: float | None
    evidence_weight: float | None
    pre_mastery: float
    post_mastery: float
    mastery_delta: float
    formal_evidence_count: int
    exposure_count: int
    recommendation_before: str | None
    recommendation_after: str | None
    state_update_present: bool
    notes: str


def production_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Return a small, non-sensitive inventory from the real registry/files."""
    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
    templates = json.loads(
        (root / "data" / "diagnostic_templates.json").read_text(encoding="utf-8")
    )
    template_rows = []
    for template in templates["templates"]:
        template_rows.append(
            {
                "id": template["id"],
                "concept_ids": list(template["concept_ids"]),
                "eligible_intents": list(template["eligible_intents"]),
                "review_status": template["review_status"],
                "purpose": template["purpose"],
            }
        )
    return {
        "production_template_count": sum(
            row["review_status"] == "human_verified" and row["purpose"] == "mastery_verification"
            for row in template_rows
        ),
        "active_candidate_count": 0,
        "blocked_slot_count": 1,
        "concept_count": len(knowledge["knowledge_points"]),
        "templates": template_rows,
        "prerequisites": {
            point["id"]: list(point.get("prerequisites", []))
            for point in knowledge["knowledge_points"]
        },
    }


def _template_rows(root: Path) -> dict[str, dict[str, Any]]:
    data = json.loads((root / "data" / "diagnostic_templates.json").read_text(encoding="utf-8"))
    return {item["id"]: item for item in data["templates"]}


def _correct_answer(template: dict[str, Any]) -> Any:
    expected = template["expected_answer"]
    if "choice_id" in expected:
        return expected["choice_id"]
    if "choice_ids" in expected:
        return list(expected["choice_ids"])
    if "value" in expected:
        return expected["value"]
    if "ordered_choice_ids" in expected:
        return list(expected["ordered_choice_ids"])
    raise ValueError(f"unsupported expected answer for {template['id']}")


def _wrong_answer(template: dict[str, Any]) -> Any:
    expected = _correct_answer(template)
    choices = template.get("choices", [])
    if isinstance(expected, str):
        return next(choice["id"] for choice in choices if choice["id"] != expected)
    if isinstance(expected, list):
        ids = [choice["id"] for choice in choices]
        return [choice_id for choice_id in ids if choice_id not in expected][:1]
    return "not-a-valid-answer"


def _primary_concept(template: dict[str, Any]) -> str:
    return template["concept_ids"][0]


def _recommendation(knowledge: dict[str, Any], state: dict[str, Any]) -> str | None:
    result = recommend_next_concept(knowledge, state)
    return result.get("concept_id") if isinstance(result, dict) else None


def _configured_weight(workflow: Any) -> float | None:
    """Read the injected integration configuration for reporting only.

    The calculation remains entirely inside ``DiagnosticStateIntegrationService``;
    this avoids maintaining a second copy of the production weight in the audit.
    """
    integration = getattr(workflow, "_state_integration_service", None)
    value = getattr(integration, "_observation_weight", None)
    return float(value) if isinstance(value, (int, float)) else None


def _services(root: Path, database: Path):
    persistence = build_learner_state_persistence_service(root=root, db_path=database)
    policy = build_reviewed_template_exposure_policy(
        root=root, persistence_service=persistence
    )
    workflow = build_dual_track_diagnostic_workflow(root=root, exposure_policy=policy)
    return persistence, workflow


def _restore(persistence: Any, root: Path, learner_id: str) -> dict[str, Any]:
    return persistence.restore(
        learner_id=learner_id, empty_state=load_initial_learner_state(root)
    )["learner_state"]


def _persist_if_formal(
    persistence: Any,
    learner_id: str,
    result: dict[str, Any],
    event_id: str,
) -> None:
    summary = result.get("formal_evidence_summary")
    update = result.get("state_update")
    if isinstance(summary, dict) and isinstance(update, dict):
        persistence.save_completed(
            learner_id=learner_id,
            learner_state=update["learner_state"],
            diagnostic_summary=summary,
            event_id=event_id,
        )


def run_session(
    *,
    root: Path,
    database: Path,
    learner_id: str,
    template_id: str,
    answer_sequence: Iterable[Any],
    trajectory_id: str,
    step_index: int = 0,
    assistance: str = "none",
) -> tuple[dict[str, Any], TrajectorySnapshot]:
    """Run one reviewed template through the real workflow and P5B boundary.

    ``assistance`` supports production verification actions ``none``, ``hint``
    and ``reveal``.  Formative ``scaffold``/``clarification`` are intentionally
    reported as not applicable here: they cannot create evidence in this track.
    """
    if assistance in {"scaffold", "clarification"}:
        raise ValueError(
            f"{assistance} is formative-only and cannot be injected into verification evidence."
        )
    rows = _template_rows(root)
    template = rows[template_id]
    concept = _primary_concept(template)
    persistence, workflow = _services(root, database)
    evidence_weight = _configured_weight(workflow)
    state_before = _restore(persistence, root, learner_id)
    recommendation_before = _recommendation(
        load_knowledge_points(root / "data" / "knowledge_points.json"), state_before
    )
    started = workflow.start_quick_verification(
        concept_ids=list(template["concept_ids"]),
        intent=template["eligible_intents"][0],
        template_ids=[template_id],
        learner_id=learner_id,
    )
    result = started
    answers = list(answer_sequence)
    if assistance == "reveal":
        result = workflow.request_verification_reveal(
            session=result["session"], template_id=template_id, learner_id=learner_id
        )
        result = workflow.acknowledge_verification_reveal(
            session=result["session"],
            template_id=template_id,
            learner_state=deepcopy(state_before),
            learner_id=learner_id,
        )
    else:
        for answer_index, answer in enumerate(answers):
            if assistance == "hint" and answer_index == 1:
                result = workflow.choose_verification_hint_retry(
                    session=result["session"],
                    template_id=template_id,
                    learner_id=learner_id,
                )
            result = workflow.submit_verification(
                session=result["session"],
                answer=deepcopy(answer),
                submitted_template_id=template_id,
                learner_state=deepcopy(state_before),
                learner_id=learner_id,
            )
        verification_session = result.get("session", {}).get("verification_session", {})
        if (
            result.get("phase") == "verification"
            and verification_session.get("interaction_state") == "revealing"
        ):
            result = workflow.acknowledge_verification_reveal(
                session=result["session"],
                template_id=template_id,
                learner_state=deepcopy(state_before),
                learner_id=learner_id,
            )
    state_update = result.get("state_update")
    state_after = (
        deepcopy(state_update["learner_state"])
        if isinstance(state_update, dict)
        else deepcopy(state_before)
    )
    _persist_if_formal(
        persistence, learner_id, result, f"p6-{trajectory_id}-{step_index}"
    )
    verification = result.get("verification")
    evaluation = verification.get("evaluation") if isinstance(verification, dict) else None
    summary = verification.get("summary") if isinstance(verification, dict) else None
    observations = summary.get("concept_observations", {}) if isinstance(summary, dict) else {}
    levels = summary.get("concept_observation_assistance_levels", {}) if isinstance(summary, dict) else {}
    selected_signal = None
    if isinstance(state_update, dict):
        for update in state_update.get("updates", []):
            if update.get("concept_id") == concept:
                selected_signal = update.get("selected_signal")
                break
    if assistance == "reveal":
        correctness = "revealed_without_answer"
        provenance = "reveal"
    elif isinstance(evaluation, dict):
        correctness = "correct" if evaluation.get("passed") else "incorrect"
        provenance = str(evaluation.get("assistance_level", "none"))
    elif isinstance(summary, dict) and isinstance(summary.get("observation_records"), list) and summary["observation_records"]:
        last_record = summary["observation_records"][-1]
        correctness = "correct" if last_record.get("passed") else "incorrect"
        provenance = str(last_record.get("assistance_level", "none"))
    else:
        correctness = "no_observation"
        provenance = assistance
    mode = "formal" if result.get("mastery_eligible") else "practice_only"
    exposure_count = len(persistence.reviewed_template_exposures(learner_id=learner_id))
    formal_count = len(
        persistence.restore(
            learner_id=learner_id, empty_state=load_initial_learner_state(root)
        )["completed_summaries"]
    )
    pre = float(state_before.get("mastery", {}).get(concept, 0.0))
    post = float(state_after.get("mastery", {}).get(concept, 0.0))
    note = ""
    if assistance in {"scaffold", "clarification"}:
        note = "formative-only assistance; not an evidence path"
    if isinstance(levels, dict) and concept in levels:
        note = f"observation_levels={levels[concept]}"
    snapshot = TrajectorySnapshot(
        trajectory_id=trajectory_id,
        step_index=step_index,
        template_id=template_id,
        primary_concept=concept,
        response_correctness=correctness,
        assistance_provenance=provenance,
        formal_or_practice_only=mode,
        selected_signal=selected_signal,
        evidence_weight=evidence_weight,
        pre_mastery=pre,
        post_mastery=post,
        mastery_delta=post - pre,
        formal_evidence_count=formal_count,
        exposure_count=exposure_count,
        recommendation_before=recommendation_before,
        recommendation_after=_recommendation(
            load_knowledge_points(root / "data" / "knowledge_points.json"), state_after
        ),
        state_update_present=isinstance(state_update, dict),
        notes=note,
    )
    return {"result": result, "state": state_after, "summary": summary, "observations": observations}, snapshot


def run_representative_audit(root: Path = ROOT) -> dict[str, Any]:
    """Run deterministic P6 trajectories in isolated temporary databases."""
    templates = _template_rows(root)
    cases = {
        "breadth_first_search": "verify_bfs_frontier_choice_v1",
        "uniform_cost_search": "verify_ucs_min_g_choice_v1",
        "a_star_search": "verify_astar_min_f_choice_v1",
    }
    output: dict[str, Any] = {
        "inventory": production_inventory(root),
        "representative_concepts": list(cases),
        "single_step": [],
        "repeat": [],
        "assistance": [],
        "independent_templates": [],
        "order": [],
        "prerequisite": [],
        "determinism": [],
        "recommendation": [],
        "failure_cases": [],
    }
    with TemporaryDirectory(prefix="introai-p6-") as directory:
        base = Path(directory)
        bfs_a = templates["verify_bfs_frontier_choice_v1"]
        bfs_b = templates["verify_bfs_equal_cost_condition_v1"]
        for concept, template_id in cases.items():
            template = templates[template_id]
            for label, answer, assistance in (
                ("independent_correct", _correct_answer(template), "none"),
                ("incorrect_first_attempt", [_wrong_answer(template)], "none"),
                ("hint_assisted_correct", [_wrong_answer(template), _correct_answer(template)], "hint"),
                ("reveal", [], "reveal"),
            ):
                _, snapshot = run_session(
                    root=root,
                    database=base / f"{concept}-{label}.sqlite3",
                    learner_id=f"synthetic_p6_{concept}_{label}",
                    template_id=template_id,
                    answer_sequence=answer if isinstance(answer, list) else [answer],
                    trajectory_id=f"{concept}-{label}",
                    assistance=assistance,
                )
                output["single_step"].append(asdict(snapshot))
                if assistance in {"hint", "reveal"}:
                    output["assistance"].append(asdict(snapshot))

        # T5--T7: the first formal event is persisted, then a new session uses
        # the same template in practice-only mode.  Wrong -> correct is kept
        # inside one formal session so it measures the actual retry policy.
        repeat_db = base / "bfs-repeat.sqlite3"
        repeat_learner = "synthetic_p6_bfs_repeat"
        _, first_snapshot = run_session(
            root=root, database=repeat_db, learner_id=repeat_learner,
            template_id="verify_bfs_frontier_choice_v1",
            answer_sequence=[_correct_answer(bfs_a)], trajectory_id="bfs-repeat", step_index=0,
        )
        output["repeat"].append(asdict(first_snapshot))
        _, repeated_snapshot = run_session(
            root=root, database=repeat_db, learner_id=repeat_learner,
            template_id="verify_bfs_frontier_choice_v1",
            answer_sequence=[_correct_answer(bfs_a)],
            trajectory_id="bfs-repeat", step_index=1,
        )
        output["repeat"].append(asdict(repeated_snapshot))
        _, repeated_wrong_snapshot = run_session(
            root=root, database=repeat_db, learner_id=repeat_learner,
            template_id="verify_bfs_frontier_choice_v1",
            answer_sequence=[_wrong_answer(bfs_a), _wrong_answer(bfs_a)],
            trajectory_id="bfs-repeat", step_index=2, assistance="hint",
        )
        output["repeat"].append(asdict(repeated_wrong_snapshot))

        retry_db = base / "bfs-wrong-correct.sqlite3"
        _, retry_snapshot = run_session(
            root=root, database=retry_db, learner_id="synthetic_p6_bfs_wrong_correct",
            template_id="verify_bfs_frontier_choice_v1",
            answer_sequence=[_wrong_answer(bfs_a), _correct_answer(bfs_a)],
            trajectory_id="bfs-wrong-correct", step_index=0, assistance="hint",
        )
        output["repeat"].append(asdict(retry_snapshot))

        # Formative assistance levels do not enter verification evidence.  We
        # state this explicitly in the artifact rather than injecting a fake
        # verification observation for scaffold/clarification.
        output["assistance"].extend([
            {
                "assistance": "scaffold", "formal_or_practice_only": "formative_only",
                "evidence_eligible": False, "notes": "not applicable to verification evidence",
            },
            {
                "assistance": "clarification", "formal_or_practice_only": "formative_only",
                "evidence_eligible": False, "notes": "not applicable to verification evidence",
            },
        ])

        # Same concept, two different reviewed templates: BFS has two direct
        # production opportunities and therefore is the cleanest comparison.
        for label, sequence in (
            ("one_template", [("verify_bfs_frontier_choice_v1", bfs_a)]),
            ("two_templates", [("verify_bfs_frontier_choice_v1", bfs_a), ("verify_bfs_equal_cost_condition_v1", bfs_b)]),
        ):
            database = base / f"bfs-{label}.sqlite3"
            learner_id = f"synthetic_p6_bfs_{label}"
            for index, (template_id, template) in enumerate(sequence):
                _, snapshot = run_session(
                    root=root,
                    database=database,
                    learner_id=learner_id,
                    template_id=template_id,
                    answer_sequence=[_correct_answer(template)],
                    trajectory_id=f"bfs-{label}",
                    step_index=index,
                )
                output["independent_templates"].append(asdict(snapshot))

        # Order is intentionally measured with two different templates, so
        # same-template practice policy cannot contaminate the comparison.
        for label, sequence in (
            ("correct_then_incorrect", [("verify_bfs_frontier_choice_v1", [_correct_answer(bfs_a)], "none"), ("verify_bfs_equal_cost_condition_v1", [_wrong_answer(bfs_b), _wrong_answer(bfs_b)], "hint")]),
            ("incorrect_then_correct", [("verify_bfs_frontier_choice_v1", [_wrong_answer(bfs_a), _wrong_answer(bfs_a)], "hint"), ("verify_bfs_equal_cost_condition_v1", [_correct_answer(bfs_b)], "none")]),
        ):
            database = base / f"bfs-order-{label}.sqlite3"
            learner_id = f"synthetic_p6_bfs_order_{label}"
            for index, (template_id, answer, assistance) in enumerate(sequence):
                template = templates[template_id]
                _, snapshot = run_session(
                    root=root,
                    database=database,
                    learner_id=learner_id,
                    template_id=template_id,
                    answer_sequence=answer,
                    trajectory_id=f"bfs-order-{label}",
                    step_index=index,
                    assistance=assistance,
                )
                output["order"].append(asdict(snapshot))

        # Prerequisite recommendation boundary from the real registry.  These
        # are state snapshots, not a new recommendation policy.
        knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
        all_concepts = [point["id"] for point in knowledge["knowledge_points"]]
        for label, mastery in (
            ("frontier_weak_bfs_unseen", {"frontier_and_explored_set": 0.0, "breadth_first_search": 0.0}),
            ("frontier_strong_bfs_unseen", {"frontier_and_explored_set": 1.0, "breadth_first_search": 0.0}),
            ("dependent_strong_prereq_weak", {"frontier_and_explored_set": 0.0, "breadth_first_search": 1.0}),
        ):
            state = load_initial_learner_state(root)
            state["mastery"] = {concept_id: 1.0 for concept_id in all_concepts}
            state["mastery"].update(mastery)
            output["prerequisite"].append({
                "label": label,
                "mastery": mastery,
                "recommendation": _recommendation(knowledge, state),
            })

        # Replay identical production calls in two isolated stores.  The
        # resulting snapshots are compared by the tests as well as recorded.
        replay_rows = []
        for index in range(2):
            _, snapshot = run_session(
                root=root,
                database=base / f"replay-{index}.sqlite3",
                learner_id=f"synthetic_p6_replay_{index}",
                template_id="verify_ucs_min_g_choice_v1",
                answer_sequence=[_correct_answer(templates["verify_ucs_min_g_choice_v1"])],
                trajectory_id="replay",
            )
            replay_rows.append(asdict(snapshot))
        output["determinism"] = replay_rows

        # Recommendation boundaries are measured directly against the real
        # function, with no new policy or threshold.
        state = load_initial_learner_state(root)
        output["recommendation"] = [
            {"label": "fresh", "recommendation": _recommendation(knowledge, state)},
            {"label": "frontier_strong", "recommendation": _recommendation(knowledge, {**state, "mastery": {"search_problem_formulation": 1.0, "state_space_and_operators": 1.0, "tree_search_vs_graph_search": 1.0, "frontier_and_explored_set": 1.0}})},
            {"label": "prerequisite_weak", "recommendation": _recommendation(knowledge, {**state, "mastery": {"breadth_first_search": 1.0}})},
        ]
    return output


def write_report(path: Path = DEFAULT_OUTPUT, root: Path = ROOT) -> dict[str, Any]:
    report = run_representative_audit(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the offline P6 learner-state audit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = write_report(args.output)
    print(json.dumps({
        "production_template_count": report["inventory"]["production_template_count"],
        "concept_count": report["inventory"]["concept_count"],
        "single_step_rows": len(report["single_step"]),
        "assistance_rows": len(report["assistance"]),
        "independent_rows": len(report["independent_templates"]),
        "order_rows": len(report["order"]),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
