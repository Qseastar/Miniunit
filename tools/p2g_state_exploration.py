"""Bounded offline exploration of real verification-session transitions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from introai_tutor.verification_diagnostics import (
    VerificationDiagnosticError,
    VerificationDiagnosticService,
)


def explore_template(*, template: dict[str, Any], correct_answer: Any, wrong_answer: Any, max_depth: int = 4) -> dict[str, int]:
    """Explore bounded action sequences through the production session service.

    The explorer prunes equal serialized states at an equal-or-shorter depth;
    it never creates learner state or invokes state integration.
    """
    service = VerificationDiagnosticService(templates=[template])
    initial = service.start(template_ids=[template["id"]])["session"]
    reached: set[str] = set()
    paths = 0
    rejected = 0

    def signature(state: dict[str, Any]) -> str:
        return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def transitions(state: dict[str, Any]) -> list[dict[str, Any]]:
        nonlocal rejected
        result: list[dict[str, Any]] = []
        current = state["current_template_id"]
        action_calls = []
        if state["interaction_state"] == "answering":
            action_calls = [
                lambda: service.submit(session=state, answer=deepcopy(correct_answer), submitted_template_id=current),
                lambda: service.submit(session=state, answer=deepcopy(wrong_answer), submitted_template_id=current),
                lambda: service.submit(session=state, answer=[], submitted_template_id=current),
                lambda: service.request_reveal(session=state, template_id=current),
                lambda: {"session": service.current_question(session=state) and deepcopy(state)},
                lambda: {"session": service.current_question(session=json.loads(json.dumps(state))) and json.loads(json.dumps(state))},
            ]
        elif state["interaction_state"] == "retry_ready":
            action_calls = [
                lambda: service.choose_hint_retry(session=state, template_id=current),
                lambda: service.request_reveal(session=state, template_id=current),
                lambda: {"session": service.current_question(session=state) and deepcopy(state)},
            ]
        elif state["interaction_state"] == "revealing":
            action_calls = [lambda: service.acknowledge_reveal(session=state, template_id=current)]
        for call in action_calls:
            before = deepcopy(state)
            try:
                raw = call()
            except VerificationDiagnosticError:
                rejected += 1
                assert state == before
                continue
            if raw.get("status") == "completed":
                # Completion is terminal and contains no active session suitable
                # for a second submission.
                continue
            next_state = raw.get("session")
            if isinstance(next_state, dict):
                result.append(next_state)
        return result

    def visit(state: dict[str, Any], depth: int) -> None:
        nonlocal paths
        marker = f"{depth}:{signature(state)}"
        if marker in reached:
            return
        reached.add(marker)
        paths += 1
        # Real rerun must preserve display order and service state.
        question = service.current_question(session=state)
        assert question["template_id"] == state["current_template_id"]
        if depth >= max_depth:
            return
        for next_state in transitions(state):
            visit(next_state, depth + 1)

    visit(initial, 0)
    return {"action_kinds": 9, "max_depth": max_depth, "explored_paths": paths, "unique_states": len(reached), "rejected_transitions": rejected}
