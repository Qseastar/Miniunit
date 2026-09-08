"""Deterministic next-action recommendation over the knowledge graph.

Mastery remains a numeric learner-state estimate. This module additionally
distinguishes a low score with a remaining reviewed formal-evidence opportunity
from a low score whose currently available formal evidence is exhausted. The
distinction is about the next executable action; it never changes mastery.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from introai_tutor.knowledge import validate_knowledge_points


MASTERY_WEAKNESS_THRESHOLD = 0.6

_EVIDENCE_STATUS_FORMAL_AVAILABLE = "formal_evidence_available"
_EVIDENCE_STATUS_EXHAUSTED_STRONG = "evidence_exhausted_strong"
_EVIDENCE_STATUS_EXHAUSTED_REVIEW = "evidence_exhausted_review"
_EVIDENCE_STATUS_UNRESOLVED_MISCONCEPTION = "unresolved_misconception"
_EVIDENCE_STATUS_NO_TEMPLATE = "no_formal_template"


def _normalize_knowledge_data(knowledge_data: Any) -> dict[str, dict[str, Any]]:
    """Convert supported knowledge-data shapes into an ID-to-point mapping."""
    if isinstance(knowledge_data, dict) and "knowledge_points" in knowledge_data:
        validate_knowledge_points(knowledge_data)
        return _points_to_mapping(knowledge_data["knowledge_points"])
    if isinstance(knowledge_data, list):
        return _points_to_mapping(knowledge_data)
    if isinstance(knowledge_data, dict):
        for concept_id, point in knowledge_data.items():
            if not isinstance(concept_id, str) or not concept_id.strip():
                raise ValueError("Knowledge point mapping keys must be non-empty strings.")
            _validate_point(point, concept_id)
            if point["id"] != concept_id:
                raise ValueError(
                    "Knowledge point mapping key must match the point's 'id': "
                    f"{concept_id!r}."
                )
        return knowledge_data
    raise ValueError(
        "knowledge_data must be a knowledge document, a list of knowledge points, "
        "or an ID-to-knowledge-point mapping."
    )


def _points_to_mapping(points: list[Any]) -> dict[str, dict[str, Any]]:
    """Build an ID-to-point mapping while preserving the list order."""
    knowledge_dict = {}
    for index, point in enumerate(points):
        _validate_point(point, f"index {index}")
        point_id = point["id"]
        if point_id in knowledge_dict:
            raise ValueError(f"Duplicate knowledge point id: {point_id}")
        knowledge_dict[point_id] = point
    return knowledge_dict


def _validate_point(point: Any, location: str) -> None:
    if not isinstance(point, dict):
        raise ValueError(f"Knowledge point at {location} must be an object.")
    point_id = point.get("id")
    if not isinstance(point_id, str) or not point_id.strip():
        raise ValueError(f"Knowledge point at {location} must have a non-empty string id.")
    if not isinstance(point.get("prerequisites"), list):
        raise ValueError(f"Knowledge point '{point_id}' must have a prerequisites list.")


class ReviewedEvidenceCatalog:
    """Read-only map from concepts to reviewed formal template opportunities."""

    def __init__(self, *, templates: list[dict[str, Any]]) -> None:
        if not isinstance(templates, list) or not templates:
            raise ValueError("reviewed templates must be a non-empty list.")
        by_concept: dict[str, set[str]] = {}
        misconception_concepts: dict[str, set[str]] = {}
        template_ids: set[str] = set()
        for index, template in enumerate(templates):
            if not isinstance(template, dict):
                raise ValueError(f"reviewed template at index {index} must be an object.")
            template_id = template.get("id")
            concept_ids = template.get("concept_ids")
            if (
                not isinstance(template_id, str)
                or not template_id.strip()
                or template_id in template_ids
                or not isinstance(concept_ids, list)
                or not concept_ids
                or not all(isinstance(item, str) and item.strip() for item in concept_ids)
            ):
                raise ValueError("reviewed template catalog is invalid.")
            template_ids.add(template_id)
            for concept_id in concept_ids:
                by_concept.setdefault(concept_id, set()).add(template_id)
            rules = template.get("misconception_rules", [])
            if not isinstance(rules, list):
                raise ValueError("reviewed template misconception rules are invalid.")
            for rule in rules:
                if not isinstance(rule, dict):
                    raise ValueError("reviewed template misconception rule is invalid.")
                misconception_id = rule.get("misconception_id")
                if not isinstance(misconception_id, str) or not misconception_id.strip():
                    raise ValueError("reviewed template misconception rule is invalid.")
                for concept_id in concept_ids:
                    misconception_concepts.setdefault(concept_id, set()).add(
                        misconception_id
                    )
        self._template_ids_by_concept = {
            concept_id: frozenset(ids) for concept_id, ids in by_concept.items()
        }
        self._misconception_ids_by_concept = {
            concept_id: frozenset(ids)
            for concept_id, ids in misconception_concepts.items()
        }

    def evidence_status(self, *, concept_id: str, learner_state: dict[str, Any]) -> dict[str, Any]:
        """Describe formal-evidence actionability without modifying learner state."""
        if not isinstance(concept_id, str) or not concept_id.strip():
            raise ValueError("concept_id must be a non-empty string.")
        if not isinstance(learner_state, dict):
            raise ValueError("learner_state must be an object.")
        available = self._template_ids_by_concept.get(concept_id, frozenset())
        if not available:
            return {
                "status": _EVIDENCE_STATUS_NO_TEMPLATE,
                "template_ids": [],
                "used_template_ids": [],
                "remaining_formal_evidence_opportunities": 0,
                "actionable": True,
            }
        outcomes = _formal_template_outcomes(learner_state)
        used = sorted(available.intersection(outcomes))
        remaining = sorted(available - set(used))
        if remaining:
            return {
                "status": _EVIDENCE_STATUS_FORMAL_AVAILABLE,
                "template_ids": sorted(available),
                "used_template_ids": used,
                "remaining_formal_evidence_opportunities": len(remaining),
                "actionable": True,
            }
        unresolved = _unresolved_misconceptions(learner_state)
        related = self._misconception_ids_by_concept.get(concept_id, frozenset())
        if unresolved.intersection(related):
            status = _EVIDENCE_STATUS_UNRESOLVED_MISCONCEPTION
        elif all(_is_independent_pass(outcomes[template_id]) for template_id in available):
            status = _EVIDENCE_STATUS_EXHAUSTED_STRONG
        else:
            status = _EVIDENCE_STATUS_EXHAUSTED_REVIEW
        return {
            "status": status,
            "template_ids": sorted(available),
            "used_template_ids": used,
            "remaining_formal_evidence_opportunities": 0,
            "actionable": status != _EVIDENCE_STATUS_EXHAUSTED_STRONG,
        }


def build_evidence_aware_recommendation(
    *, templates: list[dict[str, Any]]
) -> Callable[[Any, dict[str, Any]], dict[str, Any]]:
    """Build the production recommender while preserving the two-argument API."""
    catalog = ReviewedEvidenceCatalog(templates=deepcopy(templates))

    def recommendation(knowledge_data: Any, learner_state: dict[str, Any]) -> dict[str, Any]:
        return recommend_next_concept(
            knowledge_data, learner_state, reviewed_evidence_catalog=catalog
        )

    return recommendation


def recommend_next_concept(
    knowledge_data: Any,
    learner_state: dict[str, Any],
    *,
    reviewed_evidence_catalog: ReviewedEvidenceCatalog | None = None,
) -> dict[str, Any]:
    """Recommend the next honest, executable learning action.

    Without a catalog this preserves legacy registry-order behavior. Production
    composition injects a catalog so exhausted independent-correct evidence
    cannot indefinitely block the next available reviewed action.
    """
    knowledge_dict = _normalize_knowledge_data(knowledge_data)
    if not isinstance(learner_state, dict):
        raise ValueError("learner_state must be an object.")
    if reviewed_evidence_catalog is not None and not isinstance(
        reviewed_evidence_catalog, ReviewedEvidenceCatalog
    ):
        raise ValueError("reviewed_evidence_catalog must be ReviewedEvidenceCatalog.")
    mastery_data = learner_state.get("mastery", {})
    if not isinstance(mastery_data, dict):
        raise ValueError("learner_state.mastery must be an object.")

    statuses = {
        concept_id: _concept_actionability(
            concept_id=concept_id,
            learner_state=learner_state,
            catalog=reviewed_evidence_catalog,
        )
        for concept_id in knowledge_dict
    }
    weak_concepts = [
        concept_id
        for concept_id in knowledge_dict
        if _mastery_score(mastery_data, concept_id) < MASTERY_WEAKNESS_THRESHOLD
    ]
    actionable_weak_concepts = [
        concept_id for concept_id in weak_concepts if statuses[concept_id]["actionable"]
    ]
    if not actionable_weak_concepts:
        if weak_concepts and reviewed_evidence_catalog is not None:
            return {
                "concept_id": None,
                "reason": (
                    "当前仍有低于掌握度阈值的知识点，但其现有审核正式证据已全部"
                    "独立完成；系统不会把重复作答伪装成新的掌握度证据。"
                ),
                "actionability": "no_actionable_formal_evidence",
                "remaining_formal_evidence_opportunities": 0,
            }
        return {"concept_id": None, "reason": "太棒了！你已经掌握了当前所有的核心知识点。"}

    target_concept = actionable_weak_concepts[0]
    while True:
        weak_prereq_found = False
        for prereq in knowledge_dict[target_concept].get("prerequisites", []):
            if prereq not in knowledge_dict:
                raise ValueError(f"Unknown prerequisite concept id: {prereq}")
            if (
                _mastery_score(mastery_data, prereq) < MASTERY_WEAKNESS_THRESHOLD
                and statuses[prereq]["actionable"]
            ):
                target_concept = prereq
                weak_prereq_found = True
                break
        if not weak_prereq_found:
            break
    return _recommendation_result(concept_id=target_concept, status=statuses[target_concept])


def _concept_actionability(
    *, concept_id: str, learner_state: dict[str, Any], catalog: ReviewedEvidenceCatalog | None
) -> dict[str, Any]:
    if catalog is None:
        return {
            "status": "legacy_mastery_only",
            "remaining_formal_evidence_opportunities": None,
            "actionable": True,
        }
    return catalog.evidence_status(concept_id=concept_id, learner_state=learner_state)


def _recommendation_result(*, concept_id: str, status: dict[str, Any]) -> dict[str, Any]:
    evidence_status = status["status"]
    remaining = status["remaining_formal_evidence_opportunities"]
    if evidence_status == _EVIDENCE_STATUS_EXHAUSTED_REVIEW:
        reason = (
            f"系统检测到你对 '{concept_id}' 的掌握度偏低，且当前审核正式题已用完但"
            "尚未形成充分的独立正向证据。建议先复习课程材料并进行现有练习；"
            "新的正式掌握度更新需要后续人工审核的新题。"
        )
        actionability = "review_practice"
    elif evidence_status == _EVIDENCE_STATUS_UNRESOLVED_MISCONCEPTION:
        reason = (
            f"系统检测到你对 '{concept_id}' 仍有需要纠正的误解。请先复习课程材料和"
            "现有练习；系统不会把重复作答当作新的独立掌握度证据。"
        )
        actionability = "review_practice"
    elif evidence_status == _EVIDENCE_STATUS_NO_TEMPLATE:
        reason = (
            f"系统检测到你对 '{concept_id}' 的掌握度偏低，但当前没有可用于该知识点的"
            "审核正式验证题。建议结合课程材料复习。"
        )
        actionability = "review_without_formal_evidence"
    else:
        reason = (
            f"系统检测到你对 '{concept_id}' 的掌握度偏低。在进行后续学习前，"
            "我们需要先夯实这个基础。"
        )
        actionability = "formal_evidence_available"
    result = {"concept_id": concept_id, "reason": reason}
    if evidence_status != "legacy_mastery_only":
        result.update(
            {
                "actionability": actionability,
                "evidence_status": evidence_status,
                "remaining_formal_evidence_opportunities": remaining,
            }
        )
    return result


def _formal_template_outcomes(learner_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return one fail-closed outcome per formally persisted template."""
    evidence = learner_state.get("learning_evidence", [])
    if not isinstance(evidence, list):
        return {}
    outcomes: dict[str, dict[str, Any]] = {}
    for event in evidence:
        if not isinstance(event, dict) or event.get("evidence_eligible") is not True:
            continue
        template_ids = event.get("template_ids")
        if isinstance(template_ids, list):
            for template_id in template_ids:
                if isinstance(template_id, str) and template_id.strip():
                    # Older compact evidence has the consumed template ID but
                    # no per-template outcome. Treat it as exhausted review,
                    # never as an unseen formal opportunity or a strong pass.
                    outcomes.setdefault(
                        template_id,
                        {
                            "status": "unknown",
                            "final_attempt_assistance_level": "unknown",
                        },
                    )
        raw_outcomes = event.get("template_outcomes")
        if not isinstance(raw_outcomes, list):
            continue
        for raw in raw_outcomes:
            if not isinstance(raw, dict):
                continue
            template_id = raw.get("template_id")
            status = raw.get("status")
            level = raw.get("final_attempt_assistance_level")
            if (
                isinstance(template_id, str)
                and template_id.strip()
                and status in {"passed", "unresolved"}
                and level in {"none", "hint", "scaffold", "clarification", "reveal"}
            ):
                outcomes[template_id] = {
                    "status": status,
                    "final_attempt_assistance_level": level,
                }
    return outcomes


def _is_independent_pass(outcome: dict[str, Any]) -> bool:
    return outcome.get("status") == "passed" and outcome.get("final_attempt_assistance_level") == "none"


def _unresolved_misconceptions(learner_state: dict[str, Any]) -> set[str]:
    values = learner_state.get("misconceptions", [])
    if not isinstance(values, list):
        return set()
    result: set[str] = set()
    for item in values:
        if isinstance(item, str) and item.strip():
            result.add(item)
        elif isinstance(item, dict):
            value = item.get("misconception_id")
            if isinstance(value, str) and value.strip():
                result.add(value)
    return result


def _mastery_score(mastery_data: dict[str, Any], concept_id: str) -> float:
    value = mastery_data.get(concept_id, 0.0)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Mastery score for '{concept_id}' must be a number.")
    score = float(value)
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Mastery score for '{concept_id}' must be between 0 and 1.")
    return score
