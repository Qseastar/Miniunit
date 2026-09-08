"""Apply completed deterministic diagnostic observations to learner state.

The service is intentionally an application boundary only: callers inject the
completed P5A summary and recommendation function. It performs no file I/O,
model calls, persistence, or diagnostic session execution.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Callable

from introai_tutor.knowledge import validate_knowledge_points
from introai_tutor.learner import validate_learner_state
from introai_tutor.recommend import recommend_next_concept


_ASSISTANCE_SOURCES = {
    "hint": "deterministic_feedback",
    "scaffold": "deterministic_feedback",
    "clarification": "semantic_advisory",
    "reveal": "model_answer",
}


class DiagnosticStateIntegrationError(ValueError):
    """Raised when a diagnostic summary or learner state is invalid."""


class DiagnosticStateIntegrationService:
    """Write a completed diagnostic summary into an isolated learner state copy."""

    def __init__(
        self,
        *,
        knowledge_data: dict,
        recommendation_fn: Callable[[Any, dict], Any] | None = None,
        observation_weight: float = 0.35,
    ) -> None:
        try:
            validate_knowledge_points(knowledge_data)
        except ValueError as error:
            raise DiagnosticStateIntegrationError(
                f"Invalid knowledge data: {error}"
            ) from None
        if recommendation_fn is not None and not callable(recommendation_fn):
            raise DiagnosticStateIntegrationError("recommendation_fn must be callable.")
        if isinstance(observation_weight, bool) or not isinstance(
            observation_weight, int | float
        ):
            raise DiagnosticStateIntegrationError(
                "observation_weight must be a number between 0 and 1."
            )
        if not math.isfinite(float(observation_weight)) or not 0.0 <= observation_weight <= 1.0:
            raise DiagnosticStateIntegrationError(
                "observation_weight must be a number between 0 and 1."
            )

        self._knowledge_data = deepcopy(knowledge_data)
        self._recommendation_fn = recommendation_fn or recommend_next_concept
        self._observation_weight = float(observation_weight)

    def apply(self, *, learner_state: dict, diagnostic_summary: dict) -> dict[str, Any]:
        """Apply a validated completed summary and recommend exactly once.

        The input state and summary remain untouched. All updates happen on a
        deep copy; the recommendation function receives separate deep copies,
        so an injected implementation cannot mutate the state returned here.
        The selected signal is the last unassisted observation for each
        concept. Raw assisted observations remain in the trace, but cannot
        stand in for independent mastery evidence. When no unassisted signal
        exists, the conservative fallback leaves that concept unchanged.
        Applied updates use ``clamp((1-w)*old + w*selected, 0, 1)``.
        """
        try:
            validate_learner_state(learner_state, self._knowledge_data)
        except (TypeError, ValueError) as error:
            raise DiagnosticStateIntegrationError(
                f"Invalid learner state: {error}"
            ) from None
        concept_ids = {
            point["id"] for point in self._knowledge_data["knowledge_points"]
        }
        normalized_summary = _validate_completed_summary(diagnostic_summary, concept_ids)

        updated_state = deepcopy(learner_state)
        # Older valid states may omit this optional collection. Normalize only
        # the copy, leaving the caller's legacy object unchanged.
        updated_state.setdefault("misconceptions", [])
        updates: list[dict[str, Any]] = []
        skipped_updates: list[dict[str, Any]] = []
        mastery = updated_state["mastery"]
        weight = self._observation_weight
        for concept_id, observations in normalized_summary["concept_observations"].items():
            old_mastery = float(mastery.get(concept_id, 0.0))
            assistance = normalized_summary["concept_observation_assistance"][
                concept_id
            ]
            assistance_levels = normalized_summary[
                "concept_observation_assistance_levels"
            ][concept_id]
            assistance_sources = normalized_summary[
                "concept_observation_assistance_sources"
            ][concept_id]
            unassisted_scores = [
                score for score, assisted in zip(observations, assistance) if not assisted
            ]
            if unassisted_scores:
                selected_signal: float | None = unassisted_scores[-1]
                selection_reason = "last_unassisted_observation"
                new_mastery = max(
                    0.0,
                    min(
                        1.0,
                        (1.0 - weight) * old_mastery + weight * selected_signal,
                    ),
                )
            else:
                selected_signal = None
                selection_reason = "no_unassisted_observation_no_mastery_update"
                new_mastery = old_mastery
            mastery[concept_id] = new_mastery
            updates.append(
                {
                    "concept_id": concept_id,
                    "old_mastery": old_mastery,
                    "observation_scores": list(observations),
                    "observation_assistance": list(assistance),
                    "observation_assistance_levels": list(assistance_levels),
                    "observation_assistance_sources": list(assistance_sources),
                    "selected_signal": selected_signal,
                    "selection_reason": selection_reason,
                    "new_mastery": new_mastery,
                }
            )

        for concept_id in normalized_summary["unobserved_concept_ids"]:
            old_mastery = float(mastery.get(concept_id, 0.0))
            skipped_updates.append(
                {
                    "concept_id": concept_id,
                    "old_mastery": old_mastery,
                    "selected_signal": None,
                    "update_applied": False,
                    "selection_reason": "no_independent_observation",
                    "new_mastery": old_mastery,
                }
            )

        added_misconception_ids = _append_misconceptions(
            updated_state, normalized_summary["misconception_ids"]
        )

        # Keep a completed summary with an actual observation visible in the
        # returned in-memory state before asynchronous persistence runs. A
        # reveal-only summary intentionally remains observation-free under
        # existing P5B semantics, so it is used only as transient
        # recommendation context below.
        evidence_context = _recommendation_evidence_context(normalized_summary)
        if normalized_summary["concept_observations"]:
            updated_state["learning_evidence"] = list(
                updated_state.get("learning_evidence", [])
            ) + [evidence_context]

        # Validate the complete candidate before crossing the recommendation
        # boundary. A recommendation exception propagates and returns nothing.
        validate_learner_state(updated_state, self._knowledge_data)
        recommendation_state = deepcopy(updated_state)
        if not normalized_summary["concept_observations"]:
            recommendation_state["learning_evidence"] = list(
                recommendation_state.get("learning_evidence", [])
            ) + [evidence_context]
        recommendation = self._recommendation_fn(
            deepcopy(self._knowledge_data), recommendation_state
        )
        return {
            "learner_state": updated_state,
            "updates": updates,
            "skipped_updates": skipped_updates,
            "added_misconception_ids": added_misconception_ids,
            "recommendation": recommendation,
        }


def _validate_completed_summary(
    summary: Any, valid_concept_ids: set[str]
) -> dict[str, Any]:
    if not isinstance(summary, dict):
        raise DiagnosticStateIntegrationError("diagnostic_summary must be an object.")
    if summary.get("purpose") != "mastery_verification":
        raise DiagnosticStateIntegrationError(
            "diagnostic_summary must have purpose mastery_verification."
        )
    if summary.get("evidence_eligible") is not True:
        raise DiagnosticStateIntegrationError(
            "diagnostic_summary must be explicitly evidence_eligible."
        )
    if summary.get("status") not in (None, "completed"):
        raise DiagnosticStateIntegrationError(
            "diagnostic_summary must represent a completed diagnostic."
        )
    required = {
        "track_id",
        "total_steps",
        "passed_steps",
        "unresolved_steps",
        "concept_observations",
        "misconception_ids",
        "step_results",
    }
    missing = sorted(required - summary.keys())
    if missing:
        raise DiagnosticStateIntegrationError(
            "diagnostic_summary is missing fields: " + ", ".join(missing)
        )

    track_id = summary["track_id"]
    if not isinstance(track_id, str) or not track_id.strip():
        raise DiagnosticStateIntegrationError("summary.track_id must be a non-empty string.")
    total_steps = _positive_int(summary["total_steps"], "summary.total_steps")
    passed_steps = _non_negative_int(summary["passed_steps"], "summary.passed_steps")
    unresolved_steps = _non_negative_int(
        summary["unresolved_steps"], "summary.unresolved_steps"
    )
    if passed_steps + unresolved_steps != total_steps:
        raise DiagnosticStateIntegrationError(
            "summary step counts must add up to total_steps."
        )

    observations = summary["concept_observations"]
    if not isinstance(observations, dict):
        raise DiagnosticStateIntegrationError(
            "summary.concept_observations must be an object."
        )
    if not observations and summary.get("no_observation_reason") != "all_revealed":
        raise DiagnosticStateIntegrationError(
            "empty concept observations require all_revealed provenance."
        )
    normalized_observations: dict[str, list[float]] = {}
    for concept_id, scores in observations.items():
        if not isinstance(concept_id, str) or not concept_id.strip():
            raise DiagnosticStateIntegrationError(
                "summary concept IDs must be non-empty strings."
            )
        if concept_id not in valid_concept_ids:
            raise DiagnosticStateIntegrationError(
                f"Unknown summary concept id: {concept_id}"
            )
        if not isinstance(scores, list) or not scores:
            raise DiagnosticStateIntegrationError(
                f"Observations for '{concept_id}' must be a non-empty list."
            )
        normalized_scores: list[float] = []
        for score in scores:
            if isinstance(score, bool) or not isinstance(score, int | float):
                raise DiagnosticStateIntegrationError(
                    f"Observation score for '{concept_id}' must be a number."
                )
            if not math.isfinite(float(score)) or not 0.0 <= score <= 1.0:
                raise DiagnosticStateIntegrationError(
                    f"Observation score for '{concept_id}' must be between 0 and 1."
                )
            normalized_scores.append(float(score))
        normalized_observations[concept_id] = normalized_scores

    unobserved_data = summary.get("unobserved_concept_ids", [])
    if not isinstance(unobserved_data, list):
        raise DiagnosticStateIntegrationError(
            "summary.unobserved_concept_ids must be a list."
        )
    normalized_unobserved: list[str] = []
    for concept_id in unobserved_data:
        if not isinstance(concept_id, str) or not concept_id.strip():
            raise DiagnosticStateIntegrationError(
                "summary.unobserved_concept_ids must contain non-empty strings."
            )
        normalized_id = concept_id.strip()
        if normalized_id not in valid_concept_ids:
            raise DiagnosticStateIntegrationError(
                f"Unknown unobserved concept id: {normalized_id}"
            )
        if normalized_id in normalized_observations:
            raise DiagnosticStateIntegrationError(
                "unobserved concept IDs must not also have observations."
            )
        if normalized_id in normalized_unobserved:
            raise DiagnosticStateIntegrationError(
                "summary.unobserved_concept_ids must not contain duplicates."
            )
        normalized_unobserved.append(normalized_id)

    assistance_data = summary.get("concept_observation_assistance")
    normalized_assistance: dict[str, list[bool]] = {}
    if assistance_data is None:
        normalized_assistance = {
            concept_id: [False] * len(scores)
            for concept_id, scores in normalized_observations.items()
        }
    else:
        if not isinstance(assistance_data, dict) or set(assistance_data) != set(
            normalized_observations
        ):
            raise DiagnosticStateIntegrationError(
                "summary.concept_observation_assistance must match concept observations."
            )
        for concept_id, flags in assistance_data.items():
            scores = normalized_observations[concept_id]
            if not isinstance(flags, list) or len(flags) != len(scores):
                raise DiagnosticStateIntegrationError(
                    f"Assistance metadata for '{concept_id}' must align with observations."
                )
            if not all(isinstance(flag, bool) for flag in flags):
                raise DiagnosticStateIntegrationError(
                    f"Assistance metadata for '{concept_id}' must contain bool values."
                )
            normalized_assistance[concept_id] = list(flags)

    levels_data = summary.get("concept_observation_assistance_levels")
    sources_data = summary.get("concept_observation_assistance_sources")
    normalized_levels, normalized_sources = _normalize_assistance_provenance(
        levels_data=levels_data,
        sources_data=sources_data,
        assistance=normalized_assistance,
    )

    misconception_ids = summary["misconception_ids"]
    if not isinstance(misconception_ids, list):
        raise DiagnosticStateIntegrationError("summary.misconception_ids must be a list.")
    normalized_misconceptions: list[str] = []
    for misconception_id in misconception_ids:
        if not isinstance(misconception_id, str) or not misconception_id.strip():
            raise DiagnosticStateIntegrationError(
                "summary misconception IDs must be non-empty strings."
            )
        normalized_id = misconception_id.strip()
        if normalized_id not in normalized_misconceptions:
            normalized_misconceptions.append(normalized_id)

    step_results = summary["step_results"]
    if not isinstance(step_results, list) or len(step_results) != total_steps:
        raise DiagnosticStateIntegrationError(
            "summary.step_results must contain exactly total_steps entries."
        )
    statuses: list[str] = []
    seen_question_ids: set[str] = set()
    for index, result in enumerate(step_results):
        if not isinstance(result, dict):
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}] must be an object."
            )
        fields = {"question_id", "status", "best_score", "attempts"}
        missing_fields = sorted(fields - result.keys())
        if missing_fields:
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}] is missing fields: "
                + ", ".join(missing_fields)
            )
        question_id = result["question_id"]
        if not isinstance(question_id, str) or not question_id.strip():
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}].question_id must be non-empty."
            )
        if question_id in seen_question_ids:
            raise DiagnosticStateIntegrationError(
                "summary.step_results question IDs must be unique."
            )
        seen_question_ids.add(question_id)
        status = result["status"]
        if status not in {"passed", "unresolved"}:
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}].status is invalid."
            )
        statuses.append(status)
        best_score = result["best_score"]
        if isinstance(best_score, bool) or not isinstance(best_score, int | float):
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}].best_score must be a number."
            )
        if not math.isfinite(float(best_score)) or not 0.0 <= best_score <= 1.0:
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}].best_score must be between 0 and 1."
            )
        _non_negative_int(result["attempts"], f"summary.step_results[{index}].attempts")
        _validate_step_assistance(result, index)

    if statuses.count("passed") != passed_steps or statuses.count("unresolved") != unresolved_steps:
        raise DiagnosticStateIntegrationError(
            "summary step counts do not match step_results statuses."
        )

    return {
        "track_id": track_id.strip(),
        "total_steps": total_steps,
        "passed_steps": passed_steps,
        "unresolved_steps": unresolved_steps,
        "concept_observations": normalized_observations,
        "unobserved_concept_ids": normalized_unobserved,
        "concept_observation_assistance": normalized_assistance,
        "concept_observation_assistance_levels": normalized_levels,
        "concept_observation_assistance_sources": normalized_sources,
        "misconception_ids": normalized_misconceptions,
        "step_results": step_results,
    }


def _recommendation_evidence_context(summary: dict[str, Any]) -> dict[str, Any]:
    """Project current completed evidence for recommendation actionability only.

    This compact object contains no answer text, rubric terms, or model data.
    It is deliberately not appended to the returned learner state: persistence
    remains the owner of durable learning-evidence entries.
    """
    outcomes: list[dict[str, Any]] = []
    for step in summary["step_results"]:
        level = step.get("final_attempt_assistance_level")
        if level not in {"none", "hint", "scaffold", "clarification", "reveal"}:
            # Legacy summaries have no per-step provenance. Do not infer an
            # independent pass from incomplete metadata.
            level = "unknown"
        outcomes.append(
            {
                "template_id": step["question_id"],
                "status": step["status"],
                "final_attempt_assistance_level": level,
            }
        )
    return {
        "evidence_eligible": True,
        "template_ids": [item["template_id"] for item in outcomes],
        "template_outcomes": outcomes,
    }


def _validate_step_assistance(result: dict[str, Any], index: int) -> None:
    """Validate optional per-step assistance metadata from newer summaries."""
    has_attempts = "attempt_assistance" in result
    has_final = "final_attempt_assisted" in result
    if not has_attempts and not has_final:
        return
    if not has_attempts or not has_final:
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}] has incomplete assistance metadata."
        )
    assistance = result["attempt_assistance"]
    if not isinstance(assistance, list) or len(assistance) != result["attempts"]:
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}].attempt_assistance must align with attempts."
        )
    if not all(isinstance(flag, bool) for flag in assistance):
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}].attempt_assistance must contain bool values."
        )
    if result["attempts"] == 0:
        if result["final_attempt_assisted"] is not False:
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}] empty attempts need false final assistance."
            )
        return
    if (
        not isinstance(result["final_attempt_assisted"], bool)
        or result["final_attempt_assisted"] != assistance[-1]
    ):
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}].final_attempt_assisted is inconsistent."
        )
    provenance_fields = {
        "attempt_assistance_levels",
        "attempt_assistance_sources",
        "final_attempt_assistance_level",
        "final_attempt_assistance_source",
    }
    present = provenance_fields & set(result)
    if not present:
        return
    if present != provenance_fields:
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}] has incomplete assistance provenance."
        )
    levels = result["attempt_assistance_levels"]
    sources = result["attempt_assistance_sources"]
    if (
        not isinstance(levels, list)
        or not isinstance(sources, list)
        or len(levels) != result["attempts"]
        or len(sources) != result["attempts"]
    ):
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}] assistance provenance must align with attempts."
        )
    for assisted, level, source in zip(assistance, levels, sources):
        _validate_assistance_provenance(level=level, source=source)
        if assisted != (level != "none"):
            raise DiagnosticStateIntegrationError(
                f"summary.step_results[{index}] assistance provenance is inconsistent."
            )
    if (
        result["final_attempt_assistance_level"] != levels[-1]
        or result["final_attempt_assistance_source"] != sources[-1]
    ):
        raise DiagnosticStateIntegrationError(
            f"summary.step_results[{index}] final assistance provenance is inconsistent."
        )


def _normalize_assistance_provenance(
    *,
    levels_data: Any,
    sources_data: Any,
    assistance: dict[str, list[bool]],
) -> tuple[dict[str, list[str]], dict[str, list[str | None]]]:
    """Validate richer metadata, or derive safe values for legacy summaries."""
    if levels_data is None and sources_data is None:
        return (
            {
                concept_id: ["reveal" if flag else "none" for flag in flags]
                for concept_id, flags in assistance.items()
            },
            {
                concept_id: ["model_answer" if flag else None for flag in flags]
                for concept_id, flags in assistance.items()
            },
        )
    if levels_data is None or sources_data is None:
        raise DiagnosticStateIntegrationError(
            "summary assistance provenance requires both levels and sources."
        )
    if not isinstance(levels_data, dict) or not isinstance(sources_data, dict):
        raise DiagnosticStateIntegrationError("summary assistance provenance must be objects.")
    if set(levels_data) != set(assistance) or set(sources_data) != set(assistance):
        raise DiagnosticStateIntegrationError(
            "summary assistance provenance must match concept observations."
        )
    normalized_levels: dict[str, list[str]] = {}
    normalized_sources: dict[str, list[str | None]] = {}
    for concept_id, flags in assistance.items():
        levels = levels_data[concept_id]
        sources = sources_data[concept_id]
        if (
            not isinstance(levels, list)
            or not isinstance(sources, list)
            or len(levels) != len(flags)
            or len(sources) != len(flags)
        ):
            raise DiagnosticStateIntegrationError(
                f"Assistance provenance for '{concept_id}' must align with observations."
            )
        normalized_levels[concept_id] = []
        normalized_sources[concept_id] = []
        for flag, level, source in zip(flags, levels, sources):
            _validate_assistance_provenance(level=level, source=source)
            if flag != (level != "none"):
                raise DiagnosticStateIntegrationError(
                    f"Assistance provenance for '{concept_id}' is inconsistent."
                )
            normalized_levels[concept_id].append(level)
            normalized_sources[concept_id].append(source)
    return normalized_levels, normalized_sources


def _validate_assistance_provenance(*, level: Any, source: Any) -> None:
    if not isinstance(level, str) or level not in {"none", *_ASSISTANCE_SOURCES}:
        raise DiagnosticStateIntegrationError("Assistance level is invalid.")
    if level == "none":
        if source is not None:
            raise DiagnosticStateIntegrationError(
                "Assistance source must be null when level is none."
            )
    elif source != _ASSISTANCE_SOURCES[level]:
        raise DiagnosticStateIntegrationError("Assistance source is invalid for level.")


def _append_misconceptions(learner_state: dict[str, Any], misconception_ids: list[str]) -> list[str]:
    records = learner_state.setdefault("misconceptions", [])
    existing_ids: set[str] = set()
    for record in records:
        if isinstance(record, str) and record.strip():
            existing_ids.add(record.strip())
            continue
        if isinstance(record, dict):
            for field in ("misconception_id", "id"):
                value = record.get(field)
                if isinstance(value, str) and value.strip():
                    existing_ids.add(value.strip())
            description = record.get("description")
            if isinstance(description, str) and description.strip():
                existing_ids.add(description.strip())

    added: list[str] = []
    for misconception_id in misconception_ids:
        if misconception_id in existing_ids:
            continue
        records.append(
            {
                "misconception_id": misconception_id,
                "description": misconception_id,
            }
        )
        existing_ids.add(misconception_id)
        added.append(misconception_id)
    return added


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DiagnosticStateIntegrationError(f"{name} must be a positive integer.")
    return value


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DiagnosticStateIntegrationError(
            f"{name} must be a non-negative integer."
        )
    return value
