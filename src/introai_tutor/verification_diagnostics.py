"""Deterministic, evidence-eligible diagnostics from reviewed templates."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import math
import re
from typing import Any, Callable


class VerificationDiagnosticError(ValueError):
    """Raised when a verification session, template, or answer is invalid."""


class VerificationDiagnosticService:
    """Run reviewed controlled questions without model scoring or state updates."""

    def __init__(
        self,
        *,
        templates: list[dict[str, Any]],
        max_attempts_per_step: int = 2,
        scorers: dict[str, Callable[[dict[str, Any], Any], dict[str, Any]]] | None = None,
    ) -> None:
        if not isinstance(templates, list) or not templates:
            raise VerificationDiagnosticError("templates must be a non-empty list.")
        if isinstance(max_attempts_per_step, bool) or not isinstance(max_attempts_per_step, int) or max_attempts_per_step < 1:
            raise VerificationDiagnosticError("max_attempts_per_step must be a positive integer.")
        self._templates = _index_templates(templates)
        self._max_attempts = max_attempts_per_step
        self._scorers = dict(DEFAULT_SCORERS)
        if scorers is not None:
            if not isinstance(scorers, dict) or not all(isinstance(key, str) and callable(value) for key, value in scorers.items()):
                raise VerificationDiagnosticError("scorers must map strings to callables.")
            self._scorers.update(scorers)
        unsupported = sorted({item["deterministic_scorer"] for item in self._templates.values()} - set(self._scorers))
        if unsupported:
            raise VerificationDiagnosticError("Unsupported deterministic scorer: " + ", ".join(unsupported))

    def start(self, *, template_ids: list[str]) -> dict[str, Any]:
        """Start a serializable verification session from selected reviewed templates."""
        normalized_ids = self._validate_template_ids(template_ids)
        session = {
            "purpose": "mastery_verification",
            "status": "in_progress",
            "template_ids": normalized_ids,
            "step_index": 0,
            "current_template_id": normalized_ids[0],
            "attempt_in_step": 0,
            "interaction_state": "answering",
            "history": [],
        }
        return {
            "purpose": "mastery_verification",
            "evidence_eligible": True,
            "status": "in_progress",
            "session": session,
            "question": self._student_question(normalized_ids[0], step_number=1, attempt_number=1, total_steps=len(normalized_ids)),
            "evaluation": None,
            "summary": None,
        }

    def submit(
        self,
        *,
        session: dict[str, Any],
        answer: Any,
        submitted_template_id: str,
    ) -> dict[str, Any]:
        """Deterministically score one JSON-safe answer and advance only by policy."""
        state = deepcopy(session)
        self._validate_session(state)
        if state["interaction_state"] != "answering":
            raise VerificationDiagnosticError(
                "verification answer submission is not allowed in the current interaction state."
            )
        template_id = state["template_ids"][state["step_index"]]
        if submitted_template_id != template_id:
            raise VerificationDiagnosticError(
                "submitted template does not match the current verification step."
            )
        template = self._templates[template_id]
        attempt_number = state["attempt_in_step"] + 1
        assistance_level, assistance_source = _pending_assistance(
            state, template_id=template_id, max_attempts=self._max_attempts
        )
        assisted = assistance_level != "none"
        scorer = self._scorers[template["deterministic_scorer"]]
        raw = scorer(deepcopy(template), deepcopy(answer))
        _validate_score_result(raw)
        serialized_answer = _json_safe_copy(answer)
        history_entry = {
            "template_id": template_id,
            "concept_ids": list(template["concept_ids"]),
            "step_index": state["step_index"],
            "attempt_number": attempt_number,
            "score": raw["score"],
            "passed": raw["passed"],
            "assisted": assisted,
            "assistance_level": assistance_level,
            "assistance_source": assistance_source,
            "misconception_ids": list(raw["misconception_ids"]),
        }
        history_entry.update(
            _history_answer_fields(template, serialized_answer)
        )
        state["history"].append(history_entry)
        evaluation = {
            "template_id": template_id,
            "concept_ids": list(template["concept_ids"]),
            "score": raw["score"],
            "passed": raw["passed"],
            "attempts_used": attempt_number,
            "max_attempts": self._max_attempts,
            "remaining_attempts": self._max_attempts - attempt_number,
            "assisted": assisted,
            "assistance_level": assistance_level,
            "assistance_source": assistance_source,
            "misconception_ids": list(raw["misconception_ids"]),
            "feedback": list(raw["feedback"]),
        }
        advance = raw["passed"]
        if advance:
            state["step_index"] += 1
            state["attempt_in_step"] = 0
        else:
            state["attempt_in_step"] = attempt_number
        # A pending hint applies to exactly one later attempt of the same
        # template. Consume an existing marker before possibly creating the
        # one that corresponds to this newly displayed hint.
        state.pop("pending_assistance", None)
        if not advance and attempt_number < self._max_attempts:
            state["interaction_state"] = "retry_ready"
        elif not advance:
            state["interaction_state"] = "revealing"
            state["reveal"] = _reveal_state(
                template_id=template_id, reason="attempts_exhausted"
            )
        if state["step_index"] == len(state["template_ids"]):
            state["status"] = "completed"
            return {
                "purpose": "mastery_verification",
                "evidence_eligible": True,
                "status": "completed",
                "session": state,
                "question": None,
                "evaluation": evaluation,
                "summary": self._build_summary(state),
            }
        if advance:
            state["current_template_id"] = state["template_ids"][state["step_index"]]
            state["interaction_state"] = "answering"
        return self._in_progress_result(state, evaluation=evaluation)

    def choose_hint_retry(self, *, session: dict[str, Any], template_id: str) -> dict[str, Any]:
        """Mark exactly the next retry as deterministic-hint-assisted."""
        state = deepcopy(session)
        self._validate_session(state)
        self._validate_current_template_id(state, template_id)
        if state["interaction_state"] != "retry_ready":
            raise VerificationDiagnosticError("hint retry is not available in the current interaction state.")
        state["pending_assistance"] = {
            "level": "hint",
            "source": "deterministic_feedback",
            "template_id": template_id,
        }
        state["interaction_state"] = "answering"
        return self._in_progress_result(state, evaluation=None)

    def request_reveal(self, *, session: dict[str, Any], template_id: str) -> dict[str, Any]:
        """Reveal reviewed answer material without manufacturing an observation."""
        state = deepcopy(session)
        self._validate_session(state)
        self._validate_current_template_id(state, template_id)
        if state["interaction_state"] not in {"answering", "retry_ready"}:
            raise VerificationDiagnosticError("answer reveal is not available in the current interaction state.")
        reason = (
            "requested_before_attempt"
            if state["attempt_in_step"] == 0
            else "requested_after_wrong"
        )
        state.pop("pending_assistance", None)
        state["interaction_state"] = "revealing"
        state["reveal"] = _reveal_state(template_id=template_id, reason=reason)
        return self._in_progress_result(state, evaluation=None)

    def acknowledge_reveal(self, *, session: dict[str, Any], template_id: str) -> dict[str, Any]:
        """Advance only after the learner explicitly acknowledges the reveal."""
        state = deepcopy(session)
        self._validate_session(state)
        self._validate_current_template_id(state, template_id)
        if state["interaction_state"] != "revealing":
            raise VerificationDiagnosticError("reveal acknowledgement is not available in the current interaction state.")
        state.pop("reveal", None)
        acknowledged = list(state.get("acknowledged_reveal_steps", []))
        acknowledged.append(state["step_index"])
        state["acknowledged_reveal_steps"] = acknowledged
        state["step_index"] += 1
        state["attempt_in_step"] = 0
        if state["step_index"] == len(state["template_ids"]):
            state["status"] = "completed"
            return {
                "purpose": "mastery_verification",
                "evidence_eligible": True,
                "status": "completed",
                "session": state,
                "question": None,
                "evaluation": None,
                "summary": self._build_summary(state),
            }
        state["current_template_id"] = state["template_ids"][state["step_index"]]
        state["interaction_state"] = "answering"
        return self._in_progress_result(state, evaluation=None)

    def current_question(self, *, session: dict[str, Any]) -> dict[str, Any]:
        state = deepcopy(session)
        self._validate_session(state)
        template_id = state["template_ids"][state["step_index"]]
        return self._student_question(
            template_id,
            step_number=state["step_index"] + 1,
            attempt_number=state["attempt_in_step"] + 1,
            total_steps=len(state["template_ids"]),
        )

    def current_reveal(self, *, session: dict[str, Any]) -> dict[str, Any]:
        """Return only reviewed student-facing answer material for a reveal state."""
        state = deepcopy(session)
        self._validate_session(state)
        if state["interaction_state"] != "revealing":
            raise VerificationDiagnosticError("current verification step is not revealing an answer.")
        reveal = state["reveal"]
        template = self._templates[state["current_template_id"]]
        answer_text = _reviewed_answer_text(template)
        return {
            "template_id": template["id"],
            "correct_choice_text": answer_text,
            "explanation": template["teaching_support"]["explanation"],
            "reveal_reason": reveal["reveal_reason"],
            "assistance_level": reveal["assistance_level"],
            "assistance_source": reveal["assistance_source"],
        }

    def _validate_template_ids(self, template_ids: Any) -> list[str]:
        if not isinstance(template_ids, list) or not template_ids:
            raise VerificationDiagnosticError("template_ids must be a non-empty list.")
        if len(template_ids) != len(set(template_ids)):
            raise VerificationDiagnosticError("template_ids must not contain duplicates.")
        result = []
        for template_id in template_ids:
            if not isinstance(template_id, str) or not template_id.strip() or template_id not in self._templates:
                raise VerificationDiagnosticError(f"Unknown verification template: {template_id}")
            result.append(template_id)
        return result

    def _validate_session(self, session: Any) -> None:
        if not isinstance(session, dict):
            raise VerificationDiagnosticError("session must be an object.")
        expected = {
            "purpose", "status", "template_ids", "step_index",
            "attempt_in_step", "current_template_id", "interaction_state", "history",
        }
        allowed = expected | {"pending_assistance", "reveal", "acknowledged_reveal_steps"}
        if not (expected <= set(session) <= allowed) or session["purpose"] != "mastery_verification":
            raise VerificationDiagnosticError("session has an invalid schema.")
        if session["status"] != "in_progress":
            raise VerificationDiagnosticError("Only an in-progress verification session can be submitted.")
        template_ids = self._validate_template_ids(session["template_ids"])
        if isinstance(session["step_index"], bool) or not isinstance(session["step_index"], int) or not 0 <= session["step_index"] < len(template_ids):
            raise VerificationDiagnosticError("session.step_index is out of range.")
        if session["current_template_id"] != template_ids[session["step_index"]]:
            raise VerificationDiagnosticError(
                "session.current_template_id does not match the current verification step."
            )
        if isinstance(session["attempt_in_step"], bool) or not isinstance(session["attempt_in_step"], int) or not 0 <= session["attempt_in_step"] <= self._max_attempts:
            raise VerificationDiagnosticError("session.attempt_in_step is out of range.")
        if not isinstance(session["history"], list):
            raise VerificationDiagnosticError("session.history must be a list.")
        _validate_acknowledged_reveal_steps(session, template_ids)
        _validate_history(
            session["history"], template_ids, self._templates, self._max_attempts,
            session["step_index"], session["attempt_in_step"], session["interaction_state"],
            session.get("acknowledged_reveal_steps", []), self._scorers,
        )
        interaction_state = session["interaction_state"]
        if interaction_state not in {"answering", "retry_ready", "revealing"}:
            raise VerificationDiagnosticError("session.interaction_state is invalid.")
        if interaction_state != "revealing" and session["attempt_in_step"] >= self._max_attempts:
            raise VerificationDiagnosticError("only reveal state may retain exhausted attempts.")
        if interaction_state == "retry_ready":
            if "pending_assistance" in session or "reveal" in session:
                raise VerificationDiagnosticError("retry_ready session has invalid auxiliary state.")
            _validate_retry_ready(session)
        elif interaction_state == "revealing":
            if "pending_assistance" in session or "reveal" not in session:
                raise VerificationDiagnosticError("revealing session has invalid auxiliary state.")
            _validate_reveal_state(session["reveal"], session=session)
        elif "reveal" in session:
            raise VerificationDiagnosticError("answering session cannot contain reveal state.")
        if "pending_assistance" in session:
            if interaction_state != "answering":
                raise VerificationDiagnosticError("pending assistance requires answering state.")
            current_template_id = template_ids[session["step_index"]]
            _validate_pending_assistance(
                session["pending_assistance"], template_id=current_template_id,
                attempt_in_step=session["attempt_in_step"], max_attempts=self._max_attempts,
            )

    def _validate_current_template_id(self, state: dict[str, Any], template_id: Any) -> None:
        if not isinstance(template_id, str) or template_id != state["current_template_id"]:
            raise VerificationDiagnosticError(
                "submitted template does not match the current verification step."
            )

    def _in_progress_result(self, state: dict[str, Any], *, evaluation: dict[str, Any] | None) -> dict[str, Any]:
        template_id = state["current_template_id"]
        return {
            "purpose": "mastery_verification",
            "evidence_eligible": True,
            "status": "in_progress",
            "session": state,
            "question": self._student_question(
                template_id,
                step_number=state["step_index"] + 1,
                attempt_number=state["attempt_in_step"] + 1,
                total_steps=len(state["template_ids"]),
            ),
            "evaluation": evaluation,
            "summary": None,
        }

    def _student_question(self, template_id: str, *, step_number: int, attempt_number: int, total_steps: int) -> dict[str, Any]:
        template = self._templates[template_id]
        return {
            "id": template_id,
            "template_id": template_id,
            "prompt": template["prompt"],
            "choices": deepcopy(template["choices"]),
            "concept_ids": list(template["concept_ids"]),
            "question_type": template["question_type"],
            "deterministic_scorer": template["deterministic_scorer"],
            "step_number": step_number,
            "total_steps": total_steps,
            "attempt_number": attempt_number,
            "max_attempts": self._max_attempts,
        }

    def _build_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        observations: dict[str, list[float]] = {}
        assistance: dict[str, list[bool]] = {}
        levels: dict[str, list[str]] = {}
        sources: dict[str, list[str | None]] = {}
        misconceptions: list[str] = []
        observation_records: list[dict[str, Any]] = []
        step_results: list[dict[str, Any]] = []
        for step_index, template_id in enumerate(state["template_ids"]):
            entries = [item for item in state["history"] if item["step_index"] == step_index]
            for entry in entries:
                record = {
                    "step_index": entry["step_index"],
                    "template_id": entry["template_id"],
                    "concept_ids": list(entry["concept_ids"]),
                    "score": entry["score"],
                    "passed": entry["passed"],
                    "assisted": entry["assisted"],
                    "assistance_level": entry["assistance_level"],
                    "assistance_source": entry["assistance_source"],
                }
                record.update(_observation_answer_fields(entry))
                observation_records.append(record)
                for concept_id in entry["concept_ids"]:
                    observations.setdefault(concept_id, []).append(entry["score"])
                    assistance.setdefault(concept_id, []).append(entry["assisted"])
                    levels.setdefault(concept_id, []).append(entry["assistance_level"])
                    sources.setdefault(concept_id, []).append(entry["assistance_source"])
                for misconception_id in entry["misconception_ids"]:
                    if misconception_id not in misconceptions:
                        misconceptions.append(misconception_id)
            step_results.append({
                "question_id": template_id,
                "status": "passed" if any(item["passed"] for item in entries) else "unresolved",
                "best_score": max((item["score"] for item in entries), default=0.0),
                "attempts": len(entries),
                "attempt_assistance": [item["assisted"] for item in entries],
                "attempt_assistance_levels": [
                    item["assistance_level"] for item in entries
                ],
                "attempt_assistance_sources": [
                    item["assistance_source"] for item in entries
                ],
                "final_attempt_assisted": entries[-1]["assisted"] if entries else False,
                "final_attempt_assistance_level": entries[-1]["assistance_level"] if entries else "none",
                "final_attempt_assistance_source": entries[-1]["assistance_source"] if entries else None,
            })
        passed_steps = sum(item["status"] == "passed" for item in step_results)
        unobserved_concept_ids: list[str] = []
        for template_id in state["template_ids"]:
            for concept_id in self._templates[template_id]["concept_ids"]:
                if concept_id not in observations and concept_id not in unobserved_concept_ids:
                    unobserved_concept_ids.append(concept_id)
        summary = {
            "status": "completed",
            "purpose": "mastery_verification",
            "evidence_eligible": True,
            "track_id": "reviewed_template_verification",
            "total_steps": len(state["template_ids"]),
            "passed_steps": passed_steps,
            "unresolved_steps": len(state["template_ids"]) - passed_steps,
            "concept_observations": observations,
            "concept_observation_assistance": assistance,
            "concept_observation_assistance_levels": levels,
            "concept_observation_assistance_sources": sources,
            "unobserved_concept_ids": unobserved_concept_ids,
            "misconception_ids": misconceptions,
            "observation_records": observation_records,
            "step_results": step_results,
        }
        if not observations:
            summary["no_observation_reason"] = "all_revealed"
        return summary


def _index_templates(templates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in templates:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise VerificationDiagnosticError("templates contain an invalid id.")
        if item["id"] in indexed:
            raise VerificationDiagnosticError(f"Duplicate verification template: {item['id']}")
        if item.get("purpose") != "mastery_verification" or item.get("review_status") != "human_verified":
            raise VerificationDiagnosticError("Verification templates must be reviewed mastery templates.")
        indexed[item["id"]] = deepcopy(item)
    return indexed


def _score_single_choice(template: dict[str, Any], answer: str) -> dict[str, Any]:
    if not isinstance(answer, str) or not answer.strip():
        raise VerificationDiagnosticError("answer must be a non-empty string.")
    choice_ids = {item["id"] for item in template["choices"]}
    if answer not in choice_ids:
        raise VerificationDiagnosticError("answer must be one of the displayed choice IDs.")
    passed = answer == template["expected_answer"]["choice_id"]
    misconception_ids = [
        rule["misconception_id"] for rule in template["misconception_rules"] if rule["choice_id"] == answer
    ]
    feedback = []
    if not passed:
        feedback.append(template["teaching_support"]["hint"])
    return {"score": 1.0 if passed else 0.0, "passed": passed, "misconception_ids": misconception_ids, "feedback": feedback}


def _score_multiple_choice(
    template: dict[str, Any], answer: Any
) -> dict[str, Any]:
    choice_ids = _runtime_choice_ids(template)
    submitted = _submitted_id_list(
        answer, valid_ids=choice_ids, answer_name="multiple-choice answer"
    )
    expected = _expected_id_list(
        template,
        field="choice_ids",
        valid_ids=choice_ids,
    )
    passed = set(submitted) == set(expected)
    return _binary_score(template, passed=passed)


def _score_numeric_answer(
    template: dict[str, Any], answer: Any
) -> dict[str, Any]:
    expected, tolerance = _numeric_expected(template)
    submitted = _student_decimal(answer)
    passed = abs(submitted - expected) <= tolerance
    return _binary_score(template, passed=passed)


def _score_ordering(template: dict[str, Any], answer: Any) -> dict[str, Any]:
    choice_ids = _runtime_choice_ids(template)
    submitted = _submitted_id_list(
        answer, valid_ids=choice_ids, answer_name="ordering answer"
    )
    expected = _expected_id_list(
        template,
        field="ordered_choice_ids",
        valid_ids=choice_ids,
    )
    passed = submitted == expected
    return _binary_score(template, passed=passed)


DEFAULT_SCORERS: dict[
    str, Callable[[dict[str, Any], Any], dict[str, Any]]
] = {
    "single_choice_v1": _score_single_choice,
    "multiple_choice_v1": _score_multiple_choice,
    "numeric_answer_v1": _score_numeric_answer,
    "ordering_v1": _score_ordering,
}


def score_verification_answer(
    *, template: dict[str, Any], answer: Any
) -> dict[str, Any]:
    """Score one contract-valid answer without creating a session or evidence."""
    if not isinstance(template, dict):
        raise VerificationDiagnosticError("template must be an object.")
    scorer_name = template.get("deterministic_scorer")
    scorer = DEFAULT_SCORERS.get(scorer_name)
    if scorer is None:
        raise VerificationDiagnosticError(
            "Unsupported deterministic scorer: " + str(scorer_name)
        )
    result = scorer(deepcopy(template), _json_safe_copy(answer))
    _validate_score_result(result)
    return deepcopy(result)


def _binary_score(
    template: dict[str, Any], *, passed: bool
) -> dict[str, Any]:
    feedback = [] if passed else [template["teaching_support"]["hint"]]
    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "misconception_ids": [],
        "feedback": feedback,
    }


def _runtime_choice_ids(template: dict[str, Any]) -> set[str]:
    choices = template.get("choices")
    if not isinstance(choices, list) or len(choices) < 2:
        raise VerificationDiagnosticError(
            "deterministic scorer received invalid template choices."
        )
    ids: list[str] = []
    for choice in choices:
        if (
            not isinstance(choice, dict)
            or set(choice) != {"id", "text"}
            or not isinstance(choice["id"], str)
            or not choice["id"].strip()
        ):
            raise VerificationDiagnosticError(
                "deterministic scorer received invalid template choices."
            )
        ids.append(choice["id"])
    if len(ids) != len(set(ids)):
        raise VerificationDiagnosticError(
            "deterministic scorer received duplicate template choice IDs."
        )
    return set(ids)


def _submitted_id_list(
    answer: Any, *, valid_ids: set[str], answer_name: str
) -> list[str]:
    if not isinstance(answer, list) or not answer:
        raise VerificationDiagnosticError(
            f"{answer_name} must be a non-empty list of IDs."
        )
    if not all(isinstance(item, str) and item.strip() for item in answer):
        raise VerificationDiagnosticError(
            f"{answer_name} must contain non-empty string IDs."
        )
    if len(answer) != len(set(answer)):
        raise VerificationDiagnosticError(
            f"{answer_name} must not contain duplicate IDs."
        )
    unknown = sorted(set(answer) - valid_ids)
    if unknown:
        raise VerificationDiagnosticError(
            f"{answer_name} contains unknown IDs: {', '.join(unknown)}."
        )
    return list(answer)


def _expected_id_list(
    template: dict[str, Any],
    *,
    field: str,
    valid_ids: set[str],
) -> list[str]:
    expected = template.get("expected_answer")
    if not isinstance(expected, dict) or set(expected) != {field}:
        raise VerificationDiagnosticError(
            "deterministic scorer received invalid expected_answer."
        )
    values = expected[field]
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(item, str) and item in valid_ids for item in values)
        or len(values) != len(set(values))
    ):
        raise VerificationDiagnosticError(
            "deterministic scorer received invalid expected_answer."
        )
    return list(values)


_DECIMAL_TEXT = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def _student_decimal(answer: Any) -> Decimal:
    if isinstance(answer, bool):
        raise VerificationDiagnosticError(
            "numeric answer must be a finite number or decimal string."
        )
    if isinstance(answer, int):
        return Decimal(answer)
    if isinstance(answer, float):
        if not math.isfinite(answer):
            raise VerificationDiagnosticError("numeric answer must be finite.")
        return Decimal(str(answer))
    if isinstance(answer, str):
        text = answer.strip()
        if not text or _DECIMAL_TEXT.fullmatch(text) is None:
            raise VerificationDiagnosticError(
                "numeric answer must be a plain decimal string."
            )
        try:
            value = Decimal(text)
        except InvalidOperation:  # pragma: no cover - guarded by the regex
            raise VerificationDiagnosticError(
                "numeric answer must be a plain decimal string."
            ) from None
        if not value.is_finite():
            raise VerificationDiagnosticError("numeric answer must be finite.")
        return value
    raise VerificationDiagnosticError(
        "numeric answer must be a finite number or decimal string."
    )


def _numeric_expected(template: dict[str, Any]) -> tuple[Decimal, Decimal]:
    expected = template.get("expected_answer")
    if not isinstance(expected, dict) or set(expected) not in (
        {"value"},
        {"value", "absolute_tolerance"},
    ):
        raise VerificationDiagnosticError(
            "numeric scorer received invalid expected_answer."
        )
    value = _configured_decimal(expected.get("value"), name="expected value")
    tolerance = _configured_decimal(
        expected.get("absolute_tolerance", 0), name="absolute_tolerance"
    )
    if tolerance < 0:
        raise VerificationDiagnosticError(
            "numeric scorer absolute_tolerance must be non-negative."
        )
    return value, tolerance


def _configured_decimal(value: Any, *, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VerificationDiagnosticError(
            f"numeric scorer {name} must be a finite JSON number."
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationDiagnosticError(
            f"numeric scorer {name} must be finite."
        )
    return Decimal(str(value))


def _validate_score_result(result: Any) -> None:
    if not isinstance(result, dict) or set(result) != {"score", "passed", "misconception_ids", "feedback"}:
        raise VerificationDiagnosticError("deterministic scorer returned an invalid result.")
    if result["score"] not in (0.0, 1.0) or not isinstance(result["passed"], bool) or result["passed"] != (result["score"] == 1.0):
        raise VerificationDiagnosticError("deterministic scorer returned inconsistent score data.")
    if not isinstance(result["misconception_ids"], list) or not all(isinstance(item, str) and item for item in result["misconception_ids"]):
        raise VerificationDiagnosticError("deterministic scorer returned invalid misconception IDs.")
    if not isinstance(result["feedback"], list) or not all(isinstance(item, str) and item for item in result["feedback"]):
        raise VerificationDiagnosticError("deterministic scorer returned invalid feedback.")


def _json_safe_copy(value: Any) -> Any:
    copied = deepcopy(value)
    try:
        json.dumps(copied, allow_nan=False)
    except (TypeError, ValueError):
        raise VerificationDiagnosticError(
            "answer must be JSON serializable and contain only finite numbers."
        ) from None
    return copied


def _history_answer_fields(
    template: dict[str, Any], submitted_answer: Any
) -> dict[str, Any]:
    if template["deterministic_scorer"] == "single_choice_v1":
        return {
            "selected_choice_id": submitted_answer,
            "expected_choice_id": template["expected_answer"]["choice_id"],
        }
    return {
        "submitted_answer": deepcopy(submitted_answer),
        "expected_answer": deepcopy(template["expected_answer"]),
    }


def _observation_answer_fields(entry: dict[str, Any]) -> dict[str, Any]:
    if "selected_choice_id" in entry:
        return {
            "selected_choice_id": entry["selected_choice_id"],
            "expected_choice_id": entry["expected_choice_id"],
        }
    return {
        "submitted_answer": deepcopy(entry["submitted_answer"]),
        "expected_answer": deepcopy(entry["expected_answer"]),
    }


def _reviewed_answer_text(template: dict[str, Any]) -> str:
    scorer_name = template["deterministic_scorer"]
    expected = template["expected_answer"]
    if scorer_name == "numeric_answer_v1":
        return str(expected["value"])
    choice_text = {
        choice["id"]: choice["text"] for choice in template["choices"]
    }
    if scorer_name == "single_choice_v1":
        return choice_text[expected["choice_id"]]
    field = (
        "choice_ids"
        if scorer_name == "multiple_choice_v1"
        else "ordered_choice_ids"
    )
    separator = "、" if scorer_name == "multiple_choice_v1" else " → "
    return separator.join(choice_text[item] for item in expected[field])


def _validate_history(
    history: list[Any],
    template_ids: list[str],
    templates: dict[str, dict[str, Any]],
    max_attempts: int,
    step_index: int,
    attempt_in_step: int,
    interaction_state: str,
    acknowledged_reveal_steps: list[int],
    scorers: dict[str, Callable[[dict[str, Any], Any], dict[str, Any]]],
) -> None:
    expected_step = 0
    attempts = 0
    history_steps = {entry.get("step_index") for entry in history if isinstance(entry, dict)}
    acknowledged = set(acknowledged_reveal_steps)
    for index, entry in enumerate(history):
        while expected_step in acknowledged and expected_step not in history_steps:
            expected_step += 1
        if expected_step >= len(template_ids):
            raise VerificationDiagnosticError("session.history has entries after completion.")
        if not isinstance(entry, dict):
            raise VerificationDiagnosticError("session.history has an invalid entry schema.")
        template_id = entry.get("template_id")
        if template_id != template_ids[expected_step] or template_id not in templates:
            raise VerificationDiagnosticError("session.history does not follow the selected templates.")
        template = templates[template_id]
        common_fields = {
            "template_id", "concept_ids", "step_index", "attempt_number",
            "score", "passed", "assisted", "assistance_level",
            "assistance_source", "misconception_ids",
        }
        answer_fields = (
            {"selected_choice_id", "expected_choice_id"}
            if template["deterministic_scorer"] == "single_choice_v1"
            else {"submitted_answer", "expected_answer"}
        )
        if set(entry) != common_fields | answer_fields:
            raise VerificationDiagnosticError("session.history has an invalid entry schema.")
        if (
            entry["step_index"] != expected_step
            or entry["concept_ids"] != template["concept_ids"]
        ):
            raise VerificationDiagnosticError("session.history does not follow the selected templates.")
        if template["deterministic_scorer"] == "single_choice_v1":
            submitted_answer = entry["selected_choice_id"]
            if entry["expected_choice_id"] != template["expected_answer"]["choice_id"]:
                raise VerificationDiagnosticError(
                    "session.history has invalid template answer evidence."
                )
        else:
            submitted_answer = entry["submitted_answer"]
            if entry["expected_answer"] != template["expected_answer"]:
                raise VerificationDiagnosticError(
                    "session.history has invalid template answer evidence."
                )
        try:
            raw = scorers[template["deterministic_scorer"]](
                deepcopy(template), deepcopy(submitted_answer)
            )
        except KeyError:
            raise VerificationDiagnosticError(
                "session.history references an unsupported deterministic scorer."
            ) from None
        _validate_score_result(raw)
        if (
            entry["score"] != raw["score"]
            or entry["passed"] != raw["passed"]
            or entry["misconception_ids"] != raw["misconception_ids"]
        ):
            raise VerificationDiagnosticError(
                "session.history has inconsistent deterministic scoring evidence."
            )
        attempts += 1
        if entry["attempt_number"] != attempts:
            raise VerificationDiagnosticError("session.history has invalid scoring data.")
        _validate_history_assistance(entry)
        if entry["assisted"] != (entry["assistance_level"] != "none"):
            raise VerificationDiagnosticError("verification history has invalid assistance provenance.")
        is_last_for_step = (
            index + 1 == len(history)
            or not isinstance(history[index + 1], dict)
            or history[index + 1].get("step_index") != expected_step
        )
        if expected_step in acknowledged and is_last_for_step:
            expected_step += 1
            attempts = 0
        elif entry["passed"]:
            expected_step += 1
            attempts = 0
        elif attempts == max_attempts:
            if interaction_state == "revealing" and expected_step == step_index:
                continue
            expected_step += 1
            attempts = 0
    while expected_step in acknowledged and expected_step not in history_steps:
        expected_step += 1
    if expected_step != step_index or attempts != attempt_in_step:
        raise VerificationDiagnosticError("session state does not match history.")


def _pending_assistance(
    session: dict[str, Any], *, template_id: str, max_attempts: int
) -> tuple[str, str | None]:
    pending = session.get("pending_assistance")
    if pending is None:
        return "none", None
    _validate_pending_assistance(
        pending,
        template_id=template_id,
        attempt_in_step=session["attempt_in_step"],
        max_attempts=max_attempts,
    )
    return pending["level"], pending["source"]


def _validate_pending_assistance(
    value: Any, *, template_id: str, attempt_in_step: int, max_attempts: int
) -> None:
    if not isinstance(value, dict) or set(value) != {"level", "source", "template_id"}:
        raise VerificationDiagnosticError("session.pending_assistance has an invalid schema.")
    if value["level"] != "hint" or value["source"] != "deterministic_feedback":
        raise VerificationDiagnosticError("session.pending_assistance has invalid provenance.")
    if value["template_id"] != template_id:
        raise VerificationDiagnosticError("session.pending_assistance template does not match current step.")
    if attempt_in_step < 1 or attempt_in_step >= max_attempts:
        raise VerificationDiagnosticError("session.pending_assistance is not attached to a retry.")


def _validate_history_assistance(entry: dict[str, Any]) -> None:
    if not isinstance(entry["assisted"], bool):
        raise VerificationDiagnosticError("verification history has invalid assistance provenance.")
    level = entry["assistance_level"]
    source = entry["assistance_source"]
    if level == "none" and source is None:
        return
    if level == "hint" and source == "deterministic_feedback":
        return
    raise VerificationDiagnosticError("verification history has invalid assistance provenance.")


def _reveal_state(*, template_id: str, reason: str) -> dict[str, Any]:
    return {
        "template_id": template_id,
        "reveal_reason": reason,
        "assistance_level": "reveal",
        "assistance_source": "model_answer",
        "acknowledged": False,
    }


def _validate_retry_ready(session: dict[str, Any]) -> None:
    if session["attempt_in_step"] != 1 or not session["history"]:
        raise VerificationDiagnosticError("retry_ready session is inconsistent with its attempt history.")
    previous = session["history"][-1]
    if (
        previous["step_index"] != session["step_index"]
        or previous["attempt_number"] != 1
        or previous["passed"]
        or previous["assisted"]
    ):
        raise VerificationDiagnosticError("retry_ready session is inconsistent with its attempt history.")


def _validate_reveal_state(value: Any, *, session: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != {
        "template_id", "reveal_reason", "assistance_level", "assistance_source", "acknowledged"
    }:
        raise VerificationDiagnosticError("session.reveal has an invalid schema.")
    if value["template_id"] != session["current_template_id"]:
        raise VerificationDiagnosticError("session.reveal template does not match current step.")
    if value["reveal_reason"] not in {
        "requested_before_attempt", "requested_after_wrong", "attempts_exhausted"
    }:
        raise VerificationDiagnosticError("session.reveal has an invalid reason.")
    if value["assistance_level"] != "reveal" or value["assistance_source"] != "model_answer":
        raise VerificationDiagnosticError("session.reveal has invalid assistance provenance.")
    if value["acknowledged"] is not False:
        raise VerificationDiagnosticError("session.reveal acknowledgement state is invalid.")
    attempts = session["attempt_in_step"]
    history = session["history"]
    if value["reveal_reason"] == "requested_before_attempt" and attempts != 0:
        raise VerificationDiagnosticError("session.reveal reason is inconsistent with attempts.")
    if value["reveal_reason"] == "requested_after_wrong" and attempts != 1:
        raise VerificationDiagnosticError("session.reveal reason is inconsistent with attempts.")
    if value["reveal_reason"] == "attempts_exhausted" and attempts != 2:
        raise VerificationDiagnosticError("session.reveal reason is inconsistent with attempts.")
    if attempts and (not history or history[-1]["passed"]):
        raise VerificationDiagnosticError("session.reveal cannot follow a passed attempt.")


def _validate_acknowledged_reveal_steps(session: dict[str, Any], template_ids: list[str]) -> None:
    steps = session.get("acknowledged_reveal_steps")
    if steps is None:
        return
    if not isinstance(steps, list) or any(
        isinstance(step, bool) or not isinstance(step, int) or not 0 <= step < len(template_ids)
        for step in steps
    ):
        raise VerificationDiagnosticError("session.acknowledged_reveal_steps is invalid.")
    if steps != sorted(set(steps)) or any(step >= session["step_index"] for step in steps):
        raise VerificationDiagnosticError("session.acknowledged_reveal_steps is inconsistent.")
