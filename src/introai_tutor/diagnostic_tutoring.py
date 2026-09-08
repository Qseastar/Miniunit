"""Deterministic, data-driven diagnostic tutoring sessions.

This module deliberately stops at scoring and a serializable session summary.
It does not load files, call a model, or modify learner state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from introai_tutor.assessment import assess_structured_answer, validate_structured_assessment
from introai_tutor.diagnostic_feedback import validate_teaching_support


ASSISTANCE_LEVELS = {"none", "hint", "scaffold", "clarification", "reveal"}
ASSISTANCE_SOURCES = {
    "hint": "deterministic_feedback",
    "scaffold": "deterministic_feedback",
    "clarification": "semantic_advisory",
    "reveal": "model_answer",
}


class DiagnosticTutorError(ValueError):
    """Raised when diagnostic tutoring data or session state is invalid."""


class DiagnosticTutorService:
    """Run deterministic retries for data-defined diagnostic tracks."""

    def __init__(
        self,
        *,
        questions_data: dict,
        tracks_data: dict,
        valid_concept_ids: set[str] | list[str] | tuple[str, ...],
        max_attempts_per_step: int = 2,
        semantic_adjudicator: Any | None = None,
    ) -> None:
        self._valid_concept_ids = _validate_concept_catalog(valid_concept_ids)
        if isinstance(max_attempts_per_step, bool) or not isinstance(max_attempts_per_step, int):
            raise DiagnosticTutorError("max_attempts_per_step must be a positive integer.")
        if max_attempts_per_step <= 0:
            raise DiagnosticTutorError("max_attempts_per_step must be a positive integer.")
        self._max_attempts = max_attempts_per_step
        if semantic_adjudicator is not None and not callable(
            getattr(semantic_adjudicator, "adjudicate", None)
        ):
            raise DiagnosticTutorError(
                "semantic_adjudicator must provide a callable adjudicate method."
            )
        self._semantic_adjudicator = semantic_adjudicator
        self._questions = _validate_questions(questions_data, self._valid_concept_ids)
        self._tracks = _validate_tracks(tracks_data, self._questions, self._valid_concept_ids)

    def start(
        self, *, track_id: str = "bfs_equal_cost_ucs", variant_round: int = 0
    ) -> dict[str, Any]:
        """Start a new serializable diagnostic session for ``track_id``."""
        track = self._get_track(track_id)
        _validate_variant_round(variant_round)
        session = {
            "track_id": track_id,
            "status": "in_progress",
            "step_index": 0,
            "attempt_in_step": 0,
            "history": [],
        }
        if _track_has_prompt_variants(track):
            session["variant_round"] = variant_round
            session["selected_prompt_ids"] = _select_prompt_ids(track, variant_round)
        return {
            "status": "in_progress",
            "session": session,
            "question": self._student_question(
                track,
                step_index=0,
                attempt_number=1,
                selected_prompt_ids=session.get("selected_prompt_ids"),
            ),
            "evaluation": None,
            "summary": None,
        }

    def submit(self, *, session: dict, answer: str) -> dict[str, Any]:
        """Score one answer and deterministically advance or retry the session."""
        if not isinstance(answer, str) or not answer.strip():
            raise DiagnosticTutorError("answer must be a non-empty string.")
        state = deepcopy(session)
        track = self._validate_session(state)
        step_index = state["step_index"]
        step = track["steps"][step_index]
        question = self._questions[step["question_id"]]
        attempt_number = state["attempt_in_step"] + 1
        question_context = self._student_question(
            track,
            step_index=step_index,
            attempt_number=attempt_number,
            selected_prompt_ids=state.get("selected_prompt_ids"),
        )["prompt"]
        score_result = assess_structured_answer(
            answer,
            question["assessment"],
            semantic_adjudicator=self._semantic_adjudator_for(question),
            question_context=question_context,
        )
        assistance_level, assistance_source = _pending_assistance(state)
        assisted = assistance_level != "none"
        history_entry = {
            "question_id": question["id"],
            "concept_ids": list(step["concept_ids"]),
            "step_index": step_index,
            "attempt_number": attempt_number,
            "score": score_result["mastery_score"],
            "coverage_score": score_result["coverage_score"],
            "passed": score_result["passed"],
            "assisted": assisted,
            "assistance_level": assistance_level,
            "assistance_source": assistance_source,
            "misconception_ids": list(score_result["misconception_ids"]),
        }
        state["history"].append(history_entry)
        evaluation = {
            "question_id": question["id"],
            "concept_ids": list(step["concept_ids"]),
            "score": score_result["mastery_score"],
            "coverage_score": score_result["coverage_score"],
            "mastery_score": score_result["mastery_score"],
            "passed": score_result["passed"],
            "assisted": assisted,
            "assistance_level": assistance_level,
            "assistance_source": assistance_source,
            "attempts_used": attempt_number,
            "max_attempts": self._max_attempts,
            "matched_group_ids": [
                *score_result["matched_required_group_ids"],
                *score_result["matched_optional_group_ids"],
            ],
            "missing_group_ids": list(score_result["missing_required_group_ids"]),
            "misconception_ids": list(score_result["misconception_ids"]),
            "feedback": list(score_result["feedback_items"]),
            "matched_labels": list(score_result["matched_labels"]),
            "missing_labels": list(score_result["missing_labels"]),
            "misconception_feedback": list(score_result["misconception_feedback"]),
            "semantic_uncertain": score_result["semantic_uncertain"],
            "semantic_used": score_result["semantic_used"],
            "semantic_applied": score_result["semantic_applied"],
            "semantic_authority_applied": score_result["semantic_authority_applied"],
            "semantic_confidence": score_result["semantic_confidence"],
            "semantic_abstained": score_result["semantic_abstained"],
            "semantic_abstain_reason": score_result["semantic_abstain_reason"],
            "semantic_rejection_reason": score_result["semantic_rejection_reason"],
            "semantic_status": score_result["semantic_status"],
            "semantic_supported_group_ids": list(
                score_result["semantic_supported_group_ids"]
            ),
            "semantic_supported_labels": list(score_result["semantic_supported_labels"]),
            "needs_clarification": score_result["needs_clarification"],
            "clarifying_question": score_result["clarifying_question"],
            "semantic_trigger_eligible": score_result["semantic_trigger_eligible"],
            "semantic_eligibility_reason": score_result["semantic_eligibility_reason"],
            "semantic_trigger_reason": score_result["semantic_trigger_reason"],
            "semantic_judgments": deepcopy(score_result["semantic_judgments"]),
        }

        should_advance = score_result["passed"] or attempt_number >= self._max_attempts
        if should_advance:
            state["step_index"] += 1
            state["attempt_in_step"] = 0
        else:
            state["attempt_in_step"] = attempt_number
        # The optional marker applies to exactly the attempt just submitted.
        # Omit it again so legacy sessions keep their original shape.
        state.pop("full_answer_revealed", None)
        state.pop("pending_assistance", None)

        if state["step_index"] == len(track["steps"]):
            state["status"] = "completed"
            return {
                "status": "completed",
                "session": state,
                "question": None,
                "evaluation": evaluation,
                "summary": self._build_summary(
                    track,
                    state["history"],
                    skipped_steps=state.get("skipped_steps"),
                ),
            }

        return {
            "status": "in_progress",
            "session": state,
            "question": self._student_question(
                track,
                step_index=state["step_index"],
                attempt_number=state["attempt_in_step"] + 1,
                selected_prompt_ids=state.get("selected_prompt_ids"),
            ),
            "evaluation": evaluation,
            "summary": None,
        }

    def skip_current(self, *, session: dict) -> dict[str, Any]:
        """Advance one formative prompt without inventing an assessment observation.

        The dual-track UI uses this only for optional formative work.  It is
        deliberately distinct from ``submit``: no answer is scored and no
        history entry is created for the skipped prompt.
        """
        state = deepcopy(session)
        track = self._validate_session(state)
        skipped_steps = list(state.get("skipped_steps", []))
        skipped_steps.append(state["step_index"])
        state["skipped_steps"] = skipped_steps
        state["step_index"] += 1
        state["attempt_in_step"] = 0
        state.pop("full_answer_revealed", None)
        state.pop("pending_assistance", None)
        if state["step_index"] == len(track["steps"]):
            state["status"] = "completed"
            return {
                "status": "completed",
                "session": state,
                "question": None,
                "evaluation": None,
                "summary": self._build_summary(
                    track, state["history"], skipped_steps=state["skipped_steps"]
                ),
            }
        return {
            "status": "in_progress",
            "session": state,
            "question": self._student_question(
                track,
                step_index=state["step_index"],
                attempt_number=1,
                selected_prompt_ids=state.get("selected_prompt_ids"),
            ),
            "evaluation": None,
            "summary": None,
        }

    def current_question(self, *, session: dict) -> dict[str, Any]:
        """Recover the sole current student question from an in-progress session."""
        state = deepcopy(session)
        track = self._validate_session(state)
        return self._student_question(
            track,
            step_index=state["step_index"],
            attempt_number=state["attempt_in_step"] + 1,
            selected_prompt_ids=state.get("selected_prompt_ids"),
        )

    def _semantic_adjudator_for(self, question: dict[str, Any]) -> Any | None:
        """Keep legacy questions offline unless they have a structured rubric."""
        return self._semantic_adjudicator if "assessment" in question else None

    def get_teaching_support(self, *, question_id: str) -> dict[str, str] | None:
        """Return a copy of optional human-authored support for one canonical question."""
        if not isinstance(question_id, str) or not question_id.strip():
            raise DiagnosticTutorError("question_id must be a non-empty string.")
        try:
            teaching_support = self._questions[question_id].get("teaching_support")
        except KeyError as error:
            raise DiagnosticTutorError(f"Unknown diagnostic question: {question_id}") from error
        return deepcopy(teaching_support) if teaching_support is not None else None

    def _get_track(self, track_id: str) -> dict[str, Any]:
        if not isinstance(track_id, str) or not track_id.strip():
            raise DiagnosticTutorError("track_id must be a non-empty string.")
        try:
            return self._tracks[track_id]
        except KeyError as error:
            raise DiagnosticTutorError(f"Unknown diagnostic track: {track_id}") from error

    def _student_question(
        self,
        track: dict[str, Any],
        *,
        step_index: int,
        attempt_number: int,
        selected_prompt_ids: list[str] | None,
    ) -> dict[str, Any]:
        step = track["steps"][step_index]
        question = self._questions[step["question_id"]]
        prompt = question["question_text"]
        prompt_id = question["id"]
        if selected_prompt_ids is not None:
            prompt_id = selected_prompt_ids[step_index]
            prompt = _selected_prompt(
                step=step,
                question=question,
                selected_prompt_id=selected_prompt_ids[step_index],
            )
        return {
            "id": question["id"],
            "prompt_id": prompt_id,
            "prompt": prompt,
            "concept_ids": list(step["concept_ids"]),
            "step_number": step_index + 1,
            "total_steps": len(track["steps"]),
            "attempt_number": attempt_number,
            "max_attempts": self._max_attempts,
        }

    def _validate_session(self, session: Any) -> dict[str, Any]:
        if not isinstance(session, dict):
            raise DiagnosticTutorError("session must be an object.")
        required = {"track_id", "status", "step_index", "attempt_in_step", "history"}
        if not required <= set(session):
            raise DiagnosticTutorError("session has an invalid schema.")
        track = self._get_track(session["track_id"])
        variant_fields = {"variant_round", "selected_prompt_ids"}
        optional_fields = {"full_answer_revealed", "pending_assistance", "skipped_steps"}
        if _track_has_prompt_variants(track):
            if not (
                required | variant_fields <= set(session)
                and set(session) <= required | variant_fields | optional_fields
            ):
                raise DiagnosticTutorError("variant session has an invalid schema.")
            _validate_variant_round(session["variant_round"])
            expected_prompt_ids = _select_prompt_ids(track, session["variant_round"])
            selected_prompt_ids = session["selected_prompt_ids"]
            if not isinstance(selected_prompt_ids, list) or not all(
                isinstance(prompt_id, str) and prompt_id
                for prompt_id in selected_prompt_ids
            ):
                raise DiagnosticTutorError(
                    "session.selected_prompt_ids must be a list of non-empty strings."
                )
            if selected_prompt_ids != expected_prompt_ids:
                raise DiagnosticTutorError(
                    "session.selected_prompt_ids does not match the track and variant_round."
                )
        elif not (required <= set(session) and set(session) <= required | optional_fields):
            raise DiagnosticTutorError("session has an invalid schema.")
        if session["status"] != "in_progress":
            raise DiagnosticTutorError("Only an in-progress session can be submitted.")
        for field in ("step_index", "attempt_in_step"):
            if isinstance(session[field], bool) or not isinstance(session[field], int):
                raise DiagnosticTutorError(f"session.{field} must be an integer.")
        if not isinstance(session["history"], list):
            raise DiagnosticTutorError("session.history must be a list.")
        _validate_skipped_steps(track, session)
        if not 0 <= session["step_index"] < len(track["steps"]):
            raise DiagnosticTutorError("session.step_index is out of range for an in-progress session.")
        if not 0 <= session["attempt_in_step"] < self._max_attempts:
            raise DiagnosticTutorError("session.attempt_in_step is out of range.")
        self._validate_history(track, session)
        self._validate_assistance_state(session)
        return track

    def _validate_assistance_state(self, session: dict[str, Any]) -> None:
        """Validate one pending retry-assistance marker without requiring old sessions."""
        revealed = session.get("full_answer_revealed", False)
        if not isinstance(revealed, bool):
            raise DiagnosticTutorError("session.full_answer_revealed must be a bool.")
        pending = session.get("pending_assistance")
        if revealed and pending is not None:
            raise DiagnosticTutorError("session has conflicting pending assistance markers.")
        if not revealed and pending is None:
            return
        if pending is not None:
            _validate_pending_assistance(pending)
        if session["attempt_in_step"] != 1 or not session["history"]:
            raise DiagnosticTutorError(
                "session pending assistance is inconsistent with the current attempt."
            )
        previous = session["history"][-1]
        if (
            previous["step_index"] != session["step_index"]
            or previous["attempt_number"] != 1
            or previous["passed"]
            or previous.get("assisted", False)
        ):
            raise DiagnosticTutorError(
                "session pending assistance is inconsistent with session.history."
            )

    def _validate_history(self, track: dict[str, Any], session: dict[str, Any]) -> None:
        skipped_steps = set(session.get("skipped_steps", []))
        expected_step = 0
        expected_attempt = 1
        current_attempts = 0
        previous_entry: dict[str, Any] | None = None
        for entry in session["history"]:
            while expected_step in skipped_steps:
                expected_step += 1
            _validate_history_entry(entry)
            if expected_step >= len(track["steps"]):
                raise DiagnosticTutorError("session.history has entries after completion.")
            step = track["steps"][expected_step]
            if entry["question_id"] != step["question_id"]:
                raise DiagnosticTutorError("session.history does not follow the track order.")
            if entry["concept_ids"] != step["concept_ids"]:
                raise DiagnosticTutorError("session.history has forged concept ids.")
            if entry["step_index"] != expected_step or entry["attempt_number"] != expected_attempt:
                raise DiagnosticTutorError("session.history has invalid step or attempt numbering.")
            if entry.get("assisted", False):
                if current_attempts == 0 or previous_entry is None or previous_entry.get(
                    "assisted", False
                ):
                    raise DiagnosticTutorError(
                        "session.history has inconsistent assisted attempt state."
                    )
            current_attempts += 1
            if entry["passed"] or current_attempts == self._max_attempts:
                expected_step += 1
                while expected_step in skipped_steps:
                    expected_step += 1
                expected_attempt = 1
                current_attempts = 0
            else:
                expected_attempt += 1
            previous_entry = entry
        while expected_step in skipped_steps:
            expected_step += 1
        if session["step_index"] != expected_step:
            raise DiagnosticTutorError("session.step_index does not match session.history.")
        if session["attempt_in_step"] != current_attempts:
            raise DiagnosticTutorError("session.attempt_in_step does not match session.history.")

    def _build_summary(
        self,
        track: dict[str, Any],
        history: list[dict[str, Any]],
        *,
        skipped_steps: list[int] | None = None,
    ) -> dict[str, Any]:
        observations: dict[str, list[float]] = {}
        coverage_observations: dict[str, list[float]] = {}
        observation_assistance: dict[str, list[bool]] = {}
        observation_assistance_levels: dict[str, list[str]] = {}
        observation_assistance_sources: dict[str, list[str | None]] = {}
        misconceptions: list[str] = []
        step_results: list[dict[str, Any]] = []
        skipped = set(skipped_steps or [])
        for step_index, step in enumerate(track["steps"]):
            entries = [entry for entry in history if entry["step_index"] == step_index]
            for entry in entries:
                for concept_id in entry["concept_ids"]:
                    observations.setdefault(concept_id, []).append(entry["score"])
                    coverage_observations.setdefault(concept_id, []).append(
                        entry.get("coverage_score", entry["score"])
                    )
                    observation_assistance.setdefault(concept_id, []).append(
                        entry.get("assisted", False)
                    )
                    observation_assistance_levels.setdefault(concept_id, []).append(
                        entry.get("assistance_level", "none")
                    )
                    observation_assistance_sources.setdefault(concept_id, []).append(
                        entry.get("assistance_source")
                    )
                for misconception_id in entry["misconception_ids"]:
                    if misconception_id not in misconceptions:
                        misconceptions.append(misconception_id)
            passed = any(entry["passed"] for entry in entries)
            if not entries:
                step_results.append(
                    {
                        "question_id": step["question_id"],
                        "status": "skipped" if step_index in skipped else "unresolved",
                        "best_score": 0.0,
                        "best_coverage_score": 0.0,
                        "attempts": 0,
                        "attempt_assistance": [],
                        "attempt_assistance_levels": [],
                        "attempt_assistance_sources": [],
                        "final_attempt_assisted": False,
                        "final_attempt_assistance_level": "none",
                        "final_attempt_assistance_source": None,
                    }
                )
                continue
            step_results.append(
                {
                    "question_id": step["question_id"],
                    "status": "passed" if passed else "unresolved",
                    "best_score": max(entry["score"] for entry in entries),
                    "best_coverage_score": max(
                        entry.get("coverage_score", entry["score"])
                        for entry in entries
                    ),
                    "attempts": len(entries),
                    "attempt_assistance": [
                        entry.get("assisted", False) for entry in entries
                    ],
                    "attempt_assistance_levels": [
                        entry.get("assistance_level", "none") for entry in entries
                    ],
                    "attempt_assistance_sources": [
                        entry.get("assistance_source") for entry in entries
                    ],
                    "final_attempt_assisted": entries[-1].get("assisted", False),
                    "final_attempt_assistance_level": entries[-1].get(
                        "assistance_level", "none"
                    ),
                    "final_attempt_assistance_source": entries[-1].get(
                        "assistance_source"
                    ),
                }
            )
        passed_steps = sum(result["status"] == "passed" for result in step_results)
        return {
            "track_id": track["id"],
            "total_steps": len(track["steps"]),
            "passed_steps": passed_steps,
            "unresolved_steps": len(track["steps"]) - passed_steps,
            "concept_observations": observations,
            "concept_coverage_observations": coverage_observations,
            "concept_observation_assistance": observation_assistance,
            "concept_observation_assistance_levels": observation_assistance_levels,
            "concept_observation_assistance_sources": observation_assistance_sources,
            "misconception_ids": misconceptions,
            "step_results": step_results,
        }


def _validate_concept_catalog(value: Any) -> set[str]:
    if not isinstance(value, (set, list, tuple)) or not value:
        raise DiagnosticTutorError("valid_concept_ids must be a non-empty set, list, or tuple.")
    result: set[str] = set()
    for concept_id in value:
        if not isinstance(concept_id, str) or not concept_id.strip():
            raise DiagnosticTutorError("valid_concept_ids must contain non-empty strings.")
        result.add(concept_id)
    return result


def _validate_questions(questions_data: Any, valid_concept_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(questions_data, dict) or not isinstance(
        questions_data.get("diagnostic_questions"), list
    ):
        raise DiagnosticTutorError("questions_data must contain a diagnostic_questions list.")
    questions: dict[str, dict[str, Any]] = {}
    required = {"id", "concept_ids", "question_text", "expected_answer", "rubric", "difficulty"}
    for index, question in enumerate(questions_data["diagnostic_questions"]):
        if not isinstance(question, dict) or required - question.keys():
            raise DiagnosticTutorError(f"Diagnostic question at index {index} has an invalid schema.")
        question_id = question["id"]
        if not isinstance(question_id, str) or not question_id.strip():
            raise DiagnosticTutorError(f"Diagnostic question at index {index} has an invalid id.")
        if question_id in questions:
            raise DiagnosticTutorError(f"Duplicate diagnostic question id: {question_id}")
        for field in ("question_text", "expected_answer", "rubric"):
            if not isinstance(question[field], str) or not question[field].strip():
                raise DiagnosticTutorError(f"Diagnostic question '{question_id}' has invalid {field}.")
        if question["difficulty"] not in {"easy", "medium", "hard"}:
            raise DiagnosticTutorError(f"Diagnostic question '{question_id}' has invalid difficulty.")
        _validate_concept_ids(question["concept_ids"], valid_concept_ids, f"question '{question_id}'")
        if "assessment" in question:
            try:
                validate_structured_assessment(question["assessment"])
            except ValueError as error:
                raise DiagnosticTutorError(
                    f"Diagnostic question '{question_id}' has invalid assessment: {error}"
                ) from None
        if "teaching_support" in question:
            try:
                validate_teaching_support(question["teaching_support"])
            except ValueError as error:
                raise DiagnosticTutorError(
                    f"Diagnostic question '{question_id}' has invalid teaching_support: {error}"
                ) from None
        questions[question_id] = question
    if not questions:
        raise DiagnosticTutorError("questions_data must contain at least one diagnostic question.")
    return questions


def _validate_tracks(
    tracks_data: Any, questions: dict[str, dict[str, Any]], valid_concept_ids: set[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(tracks_data, dict) or not isinstance(tracks_data.get("tracks"), list):
        raise DiagnosticTutorError("tracks_data must contain a tracks list.")
    version = tracks_data.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise DiagnosticTutorError("tracks_data.version must be a positive integer.")
    tracks: dict[str, dict[str, Any]] = {}
    prompt_ids: set[str] = set()
    for index, track in enumerate(tracks_data["tracks"]):
        if not isinstance(track, dict):
            raise DiagnosticTutorError(f"Diagnostic track at index {index} must be an object.")
        if not isinstance(track.get("id"), str) or not track["id"].strip():
            raise DiagnosticTutorError(f"Diagnostic track at index {index} has an invalid id.")
        if track["id"] in tracks:
            raise DiagnosticTutorError(f"Duplicate diagnostic track id: {track['id']}")
        if not isinstance(track.get("title"), str) or not track["title"].strip():
            raise DiagnosticTutorError(f"Diagnostic track '{track['id']}' has an invalid title.")
        steps = track.get("steps")
        if not isinstance(steps, list) or not steps:
            raise DiagnosticTutorError(f"Diagnostic track '{track['id']}' must have non-empty steps.")
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict) or not {"question_id", "concept_ids"} <= set(step) or (
                set(step) - {"question_id", "concept_ids", "prompt_variants"}
            ):
                raise DiagnosticTutorError(
                    f"Diagnostic track '{track['id']}' step {step_index} has an invalid schema."
                )
            question_id = step["question_id"]
            if not isinstance(question_id, str) or question_id not in questions:
                raise DiagnosticTutorError(
                    f"Diagnostic track '{track['id']}' references unknown question id: {question_id}"
                )
            _validate_concept_ids(step["concept_ids"], valid_concept_ids, f"track '{track['id']}' step {step_index}")
            if "assessment" not in questions[question_id]:
                raise DiagnosticTutorError(
                    f"Diagnostic track '{track['id']}' question '{question_id}' needs an assessment rubric."
                )
            if "prompt_variants" in step:
                _validate_prompt_variants(
                    step["prompt_variants"],
                    questions=questions,
                    seen_prompt_ids=prompt_ids,
                    location=f"track '{track['id']}' step {step_index}",
                )
        tracks[track["id"]] = track
    if not tracks:
        raise DiagnosticTutorError("tracks_data must contain at least one diagnostic track.")
    return tracks


def _validate_prompt_variants(
    variants: Any,
    *,
    questions: dict[str, dict],
    seen_prompt_ids: set[str],
    location: str,
) -> None:
    if not isinstance(variants, list) or not variants:
        raise DiagnosticTutorError(f"{location} prompt_variants must be a non-empty list.")
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict) or set(variant) != {
            "id",
            "prompt",
            "review_status",
        }:
            raise DiagnosticTutorError(
                f"{location} prompt_variants[{index}] has an invalid schema."
            )
        prompt_id = variant["id"]
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise DiagnosticTutorError(
                f"{location} prompt_variants[{index}] has an invalid id."
            )
        if prompt_id in questions or prompt_id in seen_prompt_ids:
            raise DiagnosticTutorError(f"Duplicate prompt id: {prompt_id}")
        prompt = variant["prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise DiagnosticTutorError(
                f"{location} prompt_variants[{index}] has an invalid prompt."
            )
        if variant["review_status"] != "human_verified":
            raise DiagnosticTutorError(
                f"{location} prompt_variants[{index}] must be human_verified."
            )
        seen_prompt_ids.add(prompt_id)


def _track_has_prompt_variants(track: dict[str, Any]) -> bool:
    return any("prompt_variants" in step for step in track["steps"])


def _validate_variant_round(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DiagnosticTutorError("variant_round must be a non-negative integer.")


def _select_prompt_ids(track: dict[str, Any], variant_round: int) -> list[str]:
    """Select one stable prompt ID per step without randomness or global state."""
    _validate_variant_round(variant_round)
    selected_prompt_ids: list[str] = []
    for step in track["steps"]:
        candidates = [step["question_id"], *(variant["id"] for variant in step.get("prompt_variants", []))]
        selected_prompt_ids.append(candidates[variant_round % len(candidates)])
    return selected_prompt_ids


def _selected_prompt(
    *, step: dict[str, Any], question: dict[str, Any], selected_prompt_id: str
) -> str:
    if selected_prompt_id == question["id"]:
        return question["question_text"]
    for variant in step.get("prompt_variants", []):
        if variant["id"] == selected_prompt_id:
            return variant["prompt"]
    raise DiagnosticTutorError("Selected prompt id is not available for this track step.")


def _validate_concept_ids(value: Any, valid_concept_ids: set[str], location: str) -> None:
    if not isinstance(value, list) or not value:
        raise DiagnosticTutorError(f"{location} must have a non-empty concept_ids list.")
    if len(value) != len(set(value)):
        raise DiagnosticTutorError(f"{location} has duplicate concept ids.")
    for concept_id in value:
        if not isinstance(concept_id, str) or not concept_id.strip() or concept_id not in valid_concept_ids:
            raise DiagnosticTutorError(f"{location} has unknown or invalid concept id: {concept_id}")


def _validate_skipped_steps(track: dict[str, Any], session: dict[str, Any]) -> None:
    """Validate optional formative-only skips without creating fake evidence."""
    skipped = session.get("skipped_steps")
    if skipped is None:
        return
    if not isinstance(skipped, list) or any(
        isinstance(step, bool)
        or not isinstance(step, int)
        or not 0 <= step < len(track["steps"])
        for step in skipped
    ):
        raise DiagnosticTutorError("session.skipped_steps must contain valid step indices.")
    if skipped != sorted(set(skipped)):
        raise DiagnosticTutorError("session.skipped_steps must be sorted and unique.")
    if any(step >= session["step_index"] for step in skipped):
        raise DiagnosticTutorError("session.skipped_steps cannot include the current step.")


def _validate_history_entry(entry: Any) -> None:
    required = {
        "question_id",
        "concept_ids",
        "step_index",
        "attempt_number",
        "score",
        "passed",
        "misconception_ids",
    }
    allowed_fields = required | {
        "assisted",
        "coverage_score",
        "assistance_level",
        "assistance_source",
    }
    if not isinstance(entry, dict) or not required <= set(entry) or not set(entry) <= allowed_fields:
        raise DiagnosticTutorError("session.history has an invalid entry schema.")
    if not isinstance(entry["question_id"], str):
        raise DiagnosticTutorError("session.history has an invalid question id.")
    if not isinstance(entry["concept_ids"], list) or not all(isinstance(x, str) for x in entry["concept_ids"]):
        raise DiagnosticTutorError("session.history has invalid concept ids.")
    for field in ("step_index", "attempt_number"):
        if isinstance(entry[field], bool) or not isinstance(entry[field], int) or entry[field] < 0:
            raise DiagnosticTutorError(f"session.history has invalid {field}.")
    score = entry["score"]
    if isinstance(score, bool) or not isinstance(score, int | float) or not 0.0 <= score <= 1.0:
        raise DiagnosticTutorError("session.history has an invalid score.")
    if "coverage_score" in entry:
        coverage_score = entry["coverage_score"]
        if (
            isinstance(coverage_score, bool)
            or not isinstance(coverage_score, int | float)
            or not 0.0 <= coverage_score <= 1.0
        ):
            raise DiagnosticTutorError("session.history has an invalid coverage_score.")
    if not isinstance(entry["passed"], bool):
        raise DiagnosticTutorError("session.history has an invalid passed value.")
    if "assisted" in entry and not isinstance(entry["assisted"], bool):
        raise DiagnosticTutorError("session.history has an invalid assisted value.")
    has_level = "assistance_level" in entry
    has_source = "assistance_source" in entry
    if has_level != has_source:
        raise DiagnosticTutorError("session.history has incomplete assistance provenance.")
    if has_level:
        _validate_assistance_provenance(
            level=entry["assistance_level"], source=entry["assistance_source"]
        )
        if "assisted" not in entry or entry["assisted"] != (
            entry["assistance_level"] != "none"
        ):
            raise DiagnosticTutorError("session.history has inconsistent assistance provenance.")
    if not isinstance(entry["misconception_ids"], list) or not all(
        isinstance(item, str) and item for item in entry["misconception_ids"]
    ):
        raise DiagnosticTutorError("session.history has invalid misconception ids.")


def _pending_assistance(session: dict[str, Any]) -> tuple[str, str | None]:
    """Return the provenance applying to exactly the current submitted retry."""
    pending = session.get("pending_assistance")
    if pending is not None:
        _validate_pending_assistance(pending)
        return pending["level"], pending["source"]
    # Keep sessions produced before pending_assistance backward compatible.
    if session.get("full_answer_revealed", False):
        return "reveal", "model_answer"
    return "none", None


def _validate_pending_assistance(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"level", "source"}:
        raise DiagnosticTutorError(
            "session.pending_assistance must contain exactly level and source."
        )
    _validate_assistance_provenance(level=value["level"], source=value["source"])
    if value["level"] == "none":
        raise DiagnosticTutorError("session.pending_assistance cannot use level none.")


def _validate_assistance_provenance(*, level: Any, source: Any) -> None:
    if not isinstance(level, str) or level not in ASSISTANCE_LEVELS:
        raise DiagnosticTutorError("assistance_level is invalid.")
    if level == "none":
        if source is not None:
            raise DiagnosticTutorError("assistance_source must be null when assistance_level is none.")
        return
    if source != ASSISTANCE_SOURCES[level]:
        raise DiagnosticTutorError("assistance_source is invalid for assistance_level.")
