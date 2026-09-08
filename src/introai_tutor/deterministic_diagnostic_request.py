"""Fail-closed parsing for explicit reviewed-diagnostic requests.

This is intentionally not a general natural-language understanding layer.  It
only recognises a small set of explicit diagnostic-request phrases together
with exact, controlled course names or established course abbreviations.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from introai_tutor.knowledge import KnowledgeValidationError, validate_knowledge_points


_MAX_QUESTION_LENGTH = 4000
_STRONG_INTENT_PATTERNS = (
    re.compile(r"审核\s*诊断(?:题)?"),
    re.compile(r"诊断题\s*(?:测试|测验|检验|考察|测)"),
    re.compile(r"用\s*诊断题\s*(?:测试|测验|检验|考察|测)"),
    re.compile(r"(?:测试|测验|检验|考察)\s*(?:我对|对).{1,80}(?:理解|掌握)"),
    re.compile(r"对.{1,80}(?:进行)?诊断"),
)

# These are stable abbreviations that already occur across the reviewed Search
# Algorithms materials and templates.  The mapping is deliberately small: it
# is not a fuzzy synonym dictionary.
_CONTROLLED_ALIASES = {
    "breadth_first_search": ("bfs",),
    "depth_first_search": ("dfs",),
    "uniform_cost_search": ("ucs",),
    "iterative_deepening_search": ("iddfs",),
    "a_star_search": ("a-star", "a star"),
}


class DiagnosticRequestParseError(ValueError):
    """Raised only for invalid parser inputs or invalid course data."""


class DeterministicDiagnosticRequestParser:
    """Resolve explicit diagnostic requests into a safe understanding shape."""

    def __init__(self, *, knowledge_data: dict[str, Any]) -> None:
        try:
            validate_knowledge_points(knowledge_data)
        except (KnowledgeValidationError, TypeError, KeyError, AttributeError):
            raise DiagnosticRequestParseError(
                "knowledge_data is not a valid knowledge document."
            ) from None

        aliases: dict[str, tuple[str, ...]] = {}
        ordered_ids: list[str] = []
        for point in knowledge_data["knowledge_points"]:
            concept_id = point["id"]
            ordered_ids.append(concept_id)
            candidates = [point["title_zh"], point["title_en"], *_CONTROLLED_ALIASES.get(concept_id, ())]
            aliases[concept_id] = tuple(
                alias
                for alias in (_normalise_text(candidate) for candidate in candidates)
                if alias
            )
        self._aliases = aliases
        self._ordered_ids = tuple(ordered_ids)

    def parse(self, question: str) -> dict[str, Any] | None:
        """Return a controlled diagnostic understanding, or ``None`` fail-closed."""
        normalized_question = _normalise_question(question)
        if not _has_strong_diagnostic_intent(normalized_question):
            return None

        matched_aliases = {
            concept_id: tuple(
                alias
                for alias in aliases
                if _contains_alias(normalized_question, alias)
            )
            for concept_id, aliases in self._aliases.items()
        }
        # A longer controlled title (IDDFS) can contain the exact title of a
        # different concept (DFS).  Prefer that explicit longer title rather
        # than silently upgrading one direct request into a multi-concept plan.
        matched = [
            concept_id
            for concept_id in self._ordered_ids
            if matched_aliases[concept_id]
            and not _only_matched_inside_longer_concept_alias(
                concept_id, matched_aliases
            )
        ]
        if not matched:
            return None
        return {
            "in_scope": True,
            "intent": "diagnostic_request",
            "topic_ids": list(matched),
            "diagnostic_topic_ids": list(matched),
            "supporting_topic_ids": [],
            "search_terms": [],
            "needs_clarification": False,
            "clarifying_question": None,
            "confidence": 1.0,
        }


def _normalise_question(question: Any) -> str:
    if not isinstance(question, str):
        raise DiagnosticRequestParseError("question must be a string.")
    normalized = _normalise_text(question)
    if not normalized:
        raise DiagnosticRequestParseError("question must not be empty.")
    if len(normalized) > _MAX_QUESTION_LENGTH:
        raise DiagnosticRequestParseError(
            f"question must be at most {_MAX_QUESTION_LENGTH} characters."
        )
    return normalized


def _normalise_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _has_strong_diagnostic_intent(question: str) -> bool:
    return any(pattern.search(question) for pattern in _STRONG_INTENT_PATTERNS)


def _contains_alias(question: str, alias: str) -> bool:
    """Match CJK aliases directly and Latin aliases at safe word boundaries."""
    if not alias:
        return False
    if re.search(r"[a-z0-9*]", alias):
        return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", question) is not None
    return alias in question


def _only_matched_inside_longer_concept_alias(
    concept_id: str, matched_aliases: dict[str, tuple[str, ...]]
) -> bool:
    aliases = matched_aliases[concept_id]
    for alias in aliases:
        if not any(
            len(other_alias) > len(alias) and alias in other_alias
            for other_concept, other_aliases in matched_aliases.items()
            if other_concept != concept_id
            for other_alias in other_aliases
        ):
            return False
    return True
