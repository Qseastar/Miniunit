"""Persistent, per-template exposure policy for reviewed verification.

This policy deliberately distinguishes a reviewed template's first formal
measurement from later practice.  It never scores an answer or changes
mastery itself; callers use its decision before the P5B integration boundary.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from introai_tutor.learner_state_repository import LearnerStatePersistenceError


EXPOSURE_REASONS = frozenset(
    {
        "formal_answer_submitted",
        "hint_used",
        "answer_revealed",
        "migrated_existing_evidence",
    }
)


class ReviewedTemplateExposureError(ValueError):
    """Raised when a template exposure request violates the policy contract."""


class ReviewedTemplateExposurePolicy:
    """Classify reviewed templates as first-formal or practice-only.

    The injected persistence service is the cross-refresh authority.  A small
    per-process fallback cache retains a conservative practice-only decision
    for the current service lifetime if SQLite is temporarily unavailable.
    """

    def __init__(self, *, persistence_service: Any, valid_template_ids: set[str]) -> None:
        required = ("reviewed_template_exposures", "claim_template_exposure")
        if not all(callable(getattr(persistence_service, name, None)) for name in required):
            raise ReviewedTemplateExposureError(
                "persistence_service must provide reviewed-template exposure methods."
            )
        if not isinstance(valid_template_ids, set) or not valid_template_ids or not all(
            isinstance(item, str) and item for item in valid_template_ids
        ):
            raise ReviewedTemplateExposureError("valid_template_ids must be a non-empty string set.")
        self._persistence_service = persistence_service
        self._valid_template_ids = set(valid_template_ids)
        self._fallback_exposures: dict[str, set[str]] = {}

    def classify(self, *, learner_id: str, template_ids: list[str]) -> dict[str, Any]:
        """Return deterministic per-template modes without writing exposure."""
        learner = _learner_id(learner_id)
        templates = _template_ids(template_ids, self._valid_template_ids)
        persisted, degraded = self._load(learner)
        exposed = persisted | self._fallback_exposures.get(learner, set())
        decisions = [_decision(template_id, template_id in exposed) for template_id in templates]
        return {
            "template_decisions": decisions,
            "persistence_degraded": degraded,
        }

    def claim(
        self, *, learner_id: str, template_id: str, reason: str
    ) -> dict[str, Any]:
        """Atomically reserve first exposure, or report an existing exposure.

        A fresh formal session retains its mode after its first claim; this
        method is also safe against a concurrent/new session claiming the same
        template before its own first answer.
        """
        learner = _learner_id(learner_id)
        template = _template_ids([template_id], self._valid_template_ids)[0]
        if reason not in EXPOSURE_REASONS - {"migrated_existing_evidence"}:
            raise ReviewedTemplateExposureError("exposure reason is invalid.")
        cached = self._fallback_exposures.setdefault(learner, set())
        if template in cached:
            return {**_decision(template, True), "persistence_degraded": False}
        try:
            already_exposed = self._persistence_service.claim_template_exposure(
                learner_id=learner, template_id=template, reason=reason
            )
        except LearnerStatePersistenceError:
            cached.add(template)
            return {**_decision(template, False), "persistence_degraded": True}
        if not isinstance(already_exposed, bool):
            raise ReviewedTemplateExposureError("exposure persistence returned an invalid result.")
        cached.add(template)
        return {**_decision(template, already_exposed), "persistence_degraded": False}

    def _load(self, learner_id: str) -> tuple[set[str], bool]:
        try:
            data = self._persistence_service.reviewed_template_exposures(
                learner_id=learner_id
            )
        except LearnerStatePersistenceError:
            return set(), True
        if not isinstance(data, dict) or not all(
            isinstance(template_id, str) and template_id in self._valid_template_ids
            and isinstance(value, dict)
            for template_id, value in data.items()
        ):
            raise ReviewedTemplateExposureError("exposure persistence returned invalid data.")
        return set(data), False


def _decision(template_id: str, exposed_before_attempt: bool) -> dict[str, Any]:
    practice_only = bool(exposed_before_attempt)
    return {
        "template_id": template_id,
        "attempt_mode": "practice_only" if practice_only else "formal",
        "mastery_eligible": not practice_only,
        "practice_only": practice_only,
        "template_exposed_before_attempt": practice_only,
        "eligibility_reason": (
            "template_previously_exposed" if practice_only else "template_not_previously_exposed"
        ),
    }


def _learner_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64:
        raise ReviewedTemplateExposureError("learner_id is invalid.")
    return value.strip()


def _template_ids(value: Any, valid_template_ids: set[str]) -> list[str]:
    if not isinstance(value, list) or not value or len(value) != len(set(value)):
        raise ReviewedTemplateExposureError("template_ids must be a non-empty unique list.")
    normalized: list[str] = []
    for template_id in value:
        if not isinstance(template_id, str) or not template_id.strip():
            raise ReviewedTemplateExposureError("template_ids must contain non-empty strings.")
        if template_id not in valid_template_ids:
            raise ReviewedTemplateExposureError("template_ids contains an unknown reviewed template.")
        normalized.append(template_id)
    return normalized
